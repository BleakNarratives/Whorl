"""Filesystem-backed local agent bus with crash-safe delivery semantics."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from whorl.core.config import WHORL_DIR

BUS_DIR = WHORL_DIR / "bus"
INBOX_DIR = BUS_DIR / "inbox"
OUTBOX_DIR = BUS_DIR / "outbox"
DEAD_DIR = BUS_DIR / "dead"
ARCHIVE_DIR = BUS_DIR / "archive"
LOG_DIR = BUS_DIR / "log"
LOG_FILE = LOG_DIR / "bus.jsonl"
REGISTRY_FILE = BUS_DIR / "registry.json"
CLOCK_FILE = BUS_DIR / "clock"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _append(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _next_clock() -> int:
    BUS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        value = int(CLOCK_FILE.read_text().strip())
    except (OSError, ValueError):
        value = 0
    value += 1
    _atomic_text(CLOCK_FILE, f"{value}\n")
    return value


def _ensure_dirs() -> None:
    for path in (INBOX_DIR, OUTBOX_DIR, DEAD_DIR, ARCHIVE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def envelope(sender: str, recipient: str, message_type: str,
             payload: Dict[str, Any], *, priority: str = "normal",
             ttl_s: int = 300, reply_to: Optional[str] = None,
             message_id: Optional[str] = None) -> Dict[str, Any]:
    if not sender or not recipient or not message_type:
        raise ValueError("sender, recipient, and message_type are required")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if priority not in {"normal", "urgent"}:
        raise ValueError("priority must be normal or urgent")
    if ttl_s < 0:
        raise ValueError("ttl_s must be non-negative")
    return {
        "id": message_id or f"msg_{uuid.uuid4().hex}",
        "timestamp": _now(),
        "clock": _next_clock(),
        "from": sender,
        "to": recipient,
        "type": message_type,
        "priority": priority,
        "ttl_s": int(ttl_s),
        **({"reply_to": reply_to} if reply_to else {}),
        "payload": payload,
    }


def _message_path(recipient: str, message_id: str) -> Optional[Path]:
    directory = INBOX_DIR / recipient
    try:
        matches = list(directory.glob(f"*_{message_id}.json"))
    except OSError:
        return None
    return matches[0] if matches else None


def send(sender: str, recipient: str, message_type: str,
         payload: Dict[str, Any], *, priority: str = "normal",
         ttl_s: int = 300, reply_to: Optional[str] = None,
         message_id: Optional[str] = None) -> Dict[str, Any]:
    """Create and deliver one message; repeated IDs return the existing message."""
    _ensure_dirs()
    if message_id:
        existing = _find_message(message_id)
        if existing:
            return existing
    msg = envelope(sender, recipient, message_type, payload,
                   priority=priority, ttl_s=ttl_s, reply_to=reply_to,
                   message_id=message_id)
    known = recipient == "broadcast" or recipient in load_registry()
    if not known:
        _dead_letter(msg, "recipient_not_registered")
        return msg
    target = INBOX_DIR / recipient
    target.mkdir(parents=True, exist_ok=True)
    filename = f"{msg['clock']:020d}_{msg['id']}.json"
    _atomic_text(target / filename, json.dumps(msg, sort_keys=True) + "\n")
    _append(LOG_FILE, {"event": "message_delivered", "ts": _now(), "message": msg})
    return msg


def _find_message(message_id: str) -> Optional[Dict[str, Any]]:
    for root in (INBOX_DIR, ARCHIVE_DIR, DEAD_DIR):
        try:
            paths = list(root.glob(f"**/*_{message_id}.json"))
        except OSError:
            continue
        for path in paths:
            try:
                record = json.loads(path.read_text())
                return record.get("message", record) if isinstance(record, dict) else None
            except (OSError, json.JSONDecodeError):
                continue
    return None


def _dead_letter(msg: Dict[str, Any], reason: str) -> None:
    path = DEAD_DIR / f"{msg['clock']:020d}_{msg['id']}.json"
    record = {"reason": reason, "dead_lettered_at": _now(), "message": msg}
    _atomic_text(path, json.dumps(record, sort_keys=True) + "\n")
    _append(LOG_FILE, {"event": "message_dead_lettered", "ts": _now(), **record})


def _expired(msg: Dict[str, Any], now: Optional[float] = None) -> bool:
    ttl = int(msg.get("ttl_s", 300))
    try:
        timestamp = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00")).timestamp()
    except (KeyError, ValueError, TypeError):
        return True
    return (time.time() if now is None else now) > timestamp + ttl


def expire(recipient: Optional[str] = None) -> List[Dict[str, Any]]:
    """Move expired inbox messages to dead letters and return their records."""
    _ensure_dirs()
    roots = [INBOX_DIR / recipient] if recipient else [p for p in INBOX_DIR.iterdir() if p.is_dir()]
    expired = []
    for root in roots:
        try:
            paths = list(root.glob("*.json"))
        except OSError:
            continue
        for path in paths:
            try:
                msg = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if not _expired(msg):
                continue
            _dead_letter(msg, "ttl_expired")
            path.unlink(missing_ok=True)
            expired.append(msg)
    return expired


def read(recipient: str, *, limit: int = 100, include_expired: bool = False) -> List[Dict[str, Any]]:
    """Read inbox messages without deleting or acknowledging them."""
    if limit < 1:
        return []
    if not include_expired:
        expire(recipient)
    directory = INBOX_DIR / recipient
    try:
        paths = sorted(directory.glob("*.json"), key=lambda p: p.name)[:limit]
    except OSError:
        return []
    result = []
    for path in paths:
        try:
            msg = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if include_expired or not _expired(msg):
            result.append(msg)
    return result


def acknowledge(recipient: str, message_id: str) -> bool:
    """Archive one delivered message; archive preserves the full envelope."""
    path = _message_path(recipient, message_id)
    if path is None:
        return False
    target = ARCHIVE_DIR / recipient / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    # Tests and deployments may place inbox/archive on different mounts;
    # copy-then-unlink is the portable fallback when rename cannot cross them.
    try:
        os.replace(path, target)
    except OSError as exc:
        if getattr(exc, "errno", None) != 18:
            raise
        _atomic_text(target, path.read_text())
        path.unlink()
    _append(LOG_FILE, {"event": "message_acknowledged", "ts": _now(),
                       "recipient": recipient, "message_id": message_id})
    return True


def dead_letters(*, reason: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    _ensure_dirs()
    result = []
    for path in sorted(DEAD_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if reason and record.get("reason") != reason:
            continue
        result.append(record)
        if len(result) >= limit:
            break
    return result


def retry_dead_letter(message_id: str) -> Optional[Dict[str, Any]]:
    for path in DEAD_DIR.glob(f"**/*_{message_id}.json"):
        try:
            record = json.loads(path.read_text())
            msg = record["message"]
        except (OSError, KeyError, json.JSONDecodeError):
            continue
        retried = send(msg["from"], msg["to"], msg["type"], msg["payload"],
                       priority=msg.get("priority", "normal"),
                       ttl_s=msg.get("ttl_s", 300), reply_to=msg.get("reply_to"),
                       message_id=f"retry_{message_id}")
        _append(LOG_FILE, {"event": "dead_letter_retried", "ts": _now(),
                           "message_id": message_id, "retry_id": retried["id"]})
        return retried
    return None


def load_registry() -> Dict[str, Dict[str, Any]]:
    try:
        raw = json.loads(REGISTRY_FILE.read_text())
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def register(name: str, version: str, *, config: Optional[Dict[str, Any]] = None,
             capabilities: Optional[List[str]] = None, heartbeat_s: int = 60) -> Dict[str, Any]:
    if not name or heartbeat_s < 1:
        raise ValueError("name is required and heartbeat_s must be positive")
    _ensure_dirs()
    registry = load_registry()
    now = _now()
    entry = registry.get(name, {})
    entry.update({"name": name, "version": version, "config": config or {},
                  "capabilities": capabilities or [], "heartbeat_s": heartbeat_s,
                  "registered_at": entry.get("registered_at", now),
                  "last_heartbeat": now, "status": "active"})
    registry[name] = entry
    _atomic_text(REGISTRY_FILE, json.dumps(registry, indent=2, sort_keys=True) + "\n")
    _append(LOG_FILE, {"event": "agent_register", "ts": now, "agent": entry})
    return entry


def heartbeat(name: str, *, status: str = "active", uptime_s: float = 0,
              last_task: Optional[str] = None) -> Dict[str, Any]:
    registry = load_registry()
    if name not in registry:
        raise ValueError(f"agent not registered: {name}")
    entry = registry[name]
    entry.update({"last_heartbeat": _now(), "status": status, "uptime_s": uptime_s})
    if last_task is not None:
        entry["last_task"] = last_task
    _atomic_text(REGISTRY_FILE, json.dumps(registry, indent=2, sort_keys=True) + "\n")
    _append(LOG_FILE, {"event": "agent_heartbeat", "ts": _now(), "agent": name, "status": status})
    return entry


def registry_status() -> Dict[str, Dict[str, Any]]:
    result = load_registry()
    now = time.time()
    for entry in result.values():
        try:
            age = now - datetime.fromisoformat(entry["last_heartbeat"].replace("Z", "+00:00")).timestamp()
            interval = int(entry.get("heartbeat_s", 60))
        except (KeyError, ValueError, TypeError):
            age, interval = float("inf"), 60
        if age > max(300, interval * 5):
            entry["status"] = "dead"
        elif age > interval * 3:
            entry["status"] = "stale"
    return result


def status() -> Dict[str, Any]:
    _ensure_dirs()
    inboxes = {path.name: len(list(path.glob("*.json"))) for path in INBOX_DIR.iterdir() if path.is_dir()}
    return {"bus_dir": str(BUS_DIR),
            "clock": int(CLOCK_FILE.read_text().strip()) if CLOCK_FILE.exists() else 0,
            "agents": registry_status(), "inboxes": inboxes,
            "dead_letters": len(list(DEAD_DIR.glob("*.json"))),
            "archived": len(list(ARCHIVE_DIR.glob("**/*.json")))}


__all__ = ["send", "read", "register", "heartbeat", "load_registry", "registry_status",
           "status", "envelope", "acknowledge", "expire", "dead_letters",
           "retry_dead_letter"]
