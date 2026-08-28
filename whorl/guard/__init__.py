"""
whorl.guard
───────────
Service management abstraction. Routes systemd operations through a
single interface so callers (overseer_daemon, CLI, fire_drill) never
touch systemctl directly.

Every operation is logged to the Whorl DB for audit trail and the
guard_unit_state table tracks last-known status per unit.

Usage from external repos (e.g. MikeySwarm/overseer_daemon.py):
    import sys; sys.path.insert(0, str(Path.home() / "Whorl"))
    from whorl.guard import check_units, restart_unit, unit_state

Usage from Whorl CLI:
    whorl guard status
    whorl guard restart <unit>
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from whorl.core import db


# ── Core Operations ──────────────────────────────────────────────────────

def check_units(units: List[str], bus: str = "") -> Dict[str, str]:
    """Check systemd unit statuses via `is-active`.

    Args:
        units: list of unit names (e.g. ["memguard", "dvm-worker"])
        bus: "" for user bus (default), "--system" for system bus

    Returns:
        {unit_name: status_string} e.g. {"memguard": "active"}
    """
    if not units:
        return {}
    bus_args = [bus] if bus else []
    try:
        proc = subprocess.run(
            ["systemctl", *bus_args, "is-active", *units],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    statuses = proc.stdout.split()
    result = dict(zip(units, statuses))
    # Persist to DB
    _update_state(result, bus)
    return result


def restart_unit(unit: str, bus: str = "--user") -> Tuple[bool, int, str]:
    """Restart a systemd unit.

    Args:
        unit: unit name (e.g. "memguard")
        bus: "--user" (default) or "--system"

    Returns:
        (success, returncode, stderr_or_error)
    """
    try:
        proc = subprocess.run(
            ["systemctl", bus, "restart", unit],
            capture_output=True, text=True, timeout=20,
        )
        success = proc.returncode == 0
        _record_action(unit, "restart", success, proc.returncode, proc.stderr)
        return success, proc.returncode, proc.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        _record_action(unit, "restart", False, -1, str(exc))
        return False, -1, str(exc)


def stop_unit(unit: str, bus: str = "--user") -> Tuple[bool, int, str]:
    """Stop a systemd unit."""
    try:
        proc = subprocess.run(
            ["systemctl", bus, "stop", unit],
            capture_output=True, text=True, timeout=20,
        )
        success = proc.returncode == 0
        _record_action(unit, "stop", success, proc.returncode, proc.stderr)
        return success, proc.returncode, proc.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        _record_action(unit, "stop", False, -1, str(exc))
        return False, -1, str(exc)


def start_unit(unit: str, bus: str = "--user") -> Tuple[bool, int, str]:
    """Start a systemd unit."""
    try:
        proc = subprocess.run(
            ["systemctl", bus, "start", unit],
            capture_output=True, text=True, timeout=20,
        )
        success = proc.returncode == 0
        _record_action(unit, "start", success, proc.returncode, proc.stderr)
        return success, proc.returncode, proc.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        _record_action(unit, "start", False, -1, str(exc))
        return False, -1, str(exc)


def is_active(unit: str, bus: str = "") -> bool:
    """Quick check: is this unit active?"""
    result = check_units([unit], bus=bus)
    return result.get(unit) == "active"


# ── State Tracking ───────────────────────────────────────────────────────

def unit_state(unit: str) -> Optional[dict]:
    """Get last-known state for a unit from the DB."""
    rows = db.fetch("guard_unit_state", where="unit = ?",
                     params=(unit,), limit=1)
    return rows[0] if rows else None


def all_unit_states() -> List[dict]:
    """Get all tracked unit states."""
    return db.fetch("guard_unit_state", limit=50)


def _update_state(statuses: Dict[str, str], bus: str) -> None:
    """Upsert unit statuses into guard_unit_state."""
    now = datetime.now(timezone.utc).isoformat()
    for unit, status in statuses.items():
        db.insert("guard_unit_state", {
            "unit": unit,
            "status": status,
            "bus": "user" if not bus else bus.replace("--", ""),
            "last_checked": now,
        })


def _record_action(unit: str, action: str, success: bool,
                   rc: int, stderr: str) -> None:
    """Log an action to guard_actions."""
    db.insert("guard_actions", {
        "unit": unit,
        "action": action,
        "success": int(success),
        "returncode": rc,
        "stderr": stderr[:500] if stderr else "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Report ───────────────────────────────────────────────────────────────

def status_report() -> str:
    """Human-readable status of all tracked units."""
    states = all_unit_states()
    if not states:
        return "  [guard] No unit states tracked yet. Run check_units() first."

    lines = ["\n  WHORL GUARD — UNIT STATUS\n"]
    lines.append(f"  {'Unit':<25} {'Status':<12} {'Bus':<8} {'Last Checked'}")
    lines.append(f"  {'-'*65}")
    for s in sorted(states, key=lambda x: x["unit"]):
        icon = "✅" if s["status"] == "active" else "❌"
        lines.append(
            f"  {icon} {s['unit']:<23} {s['status']:<12} "
            f"{s.get('bus','?'):<8} {s.get('last_checked','')[:19]}"
        )
    lines.append("")
    return "\n".join(lines)
