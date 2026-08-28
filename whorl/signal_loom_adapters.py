"""Read-only telemetry adapters for Signal Loom.

Adapters normalize JSON records into hotspots. They never execute interventions or
publish to the bus; callers decide whether and where to publish the result.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Iterator, Optional

from whorl.signal_loom import Hotspot, make_hotspot


def _stable_id(source: str, record: Dict[str, Any]) -> str:
    identity = record.get("id") or record.get("event_id") or record.get("ts")
    if identity is None:
        identity = json.dumps(record, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{source}:{identity}".encode()).hexdigest()[:12]
    return f"hotspot_{source}_{digest}"


def _number(record: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return max(0.0, min(1.0, float(value)))
            except (TypeError, ValueError):
                pass
    return default


def _hotspot(source: str, record: Dict[str, Any], *, category: str,
             signal: str, severity: str, impact: float, confidence: float,
             leverage: float = 0.7) -> Hotspot:
    return make_hotspot(
        signal, category=category, source=source, severity=severity,
        impact=impact, confidence=confidence, leverage=leverage,
        reversibility=0.95, hotspot_id=_stable_id(source, record),
        provenance={"adapter": source, "record": record},
        recommended_intervention="review_and_propose_bounded_mitigation",
        rollback_plan="no action taken; discard proposal and retain source record",
    )


def adapt_memguard(record: Dict[str, Any]) -> Optional[Hotspot]:
    """Normalize one MemGuard event; malformed records return None."""
    if not isinstance(record, dict) or not record.get("event"):
        return None
    event = str(record["event"])
    detail = record.get("detail") if isinstance(record.get("detail"), dict) else {}
    state = str(detail.get("to") or detail.get("state") or "").upper()
    severity = "critical" if state == "CRITICAL" or event == "controlled_sacrifice" else (
        "high" if state == "PRESSURE" or event == "victim_marked" else "informational")
    impact = 1.0 if severity == "critical" else (0.75 if severity == "high" else 0.25)
    return _hotspot("memguard", record, category="memory",
                    signal=f"memguard.{event}", severity=severity,
                    impact=impact, confidence=0.95 if record.get("ts") else 0.7)


def adapt_overseer(record: Dict[str, Any]) -> Optional[Hotspot]:
    """Normalize one overseer event; malformed records return None."""
    if not isinstance(record, dict):
        return None
    event = record.get("event") or record.get("action") or record.get("type")
    if not event:
        return None
    event = str(event)
    level = str(record.get("level") or record.get("severity") or "informational").lower()
    severity = level if level in {"informational", "low", "moderate", "high", "critical"} else "moderate"
    return _hotspot("overseer", record, category="reliability",
                    signal=f"overseer.{event}", severity=severity,
                    impact={"critical": 1.0, "high": .8, "moderate": .55,
                            "low": .3, "informational": .1}[severity],
                    confidence=0.9 if record.get("ts") or record.get("timestamp") else .65)


def _adapt(records: Iterable[Dict[str, Any]], adapter) -> Iterator[Hotspot]:
    seen = set()
    for record in records:
        hotspot = adapter(record)
        if hotspot is None or hotspot.id in seen:
            continue
        seen.add(hotspot.id)
        yield hotspot


def adapt_memguard_records(records: Iterable[Dict[str, Any]]) -> Iterator[Hotspot]:
    return _adapt(records, adapt_memguard)


def adapt_overseer_records(records: Iterable[Dict[str, Any]]) -> Iterator[Hotspot]:
    return _adapt(records, adapt_overseer)


def read_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    """Yield valid JSON objects only; malformed telemetry cannot stop a scan."""
    try:
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    yield record
    except OSError:
        return


__all__ = ["adapt_memguard", "adapt_overseer", "adapt_memguard_records",
           "adapt_overseer_records", "read_jsonl"]
