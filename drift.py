"""
whorl.drift
───────────
THE ORBIT VANE — the helical language, read backward.

whorl's premise: YOU express intent as a bearing, and the machine executes
it. The Orbit Vane flips the telescope. It reads your ACTUAL artifacts —
SharedState records, loom scans, sync-bus queues, state-file touches — and
computes the bearing you *really* expressed over the last N days.

Every artifact is an event carrying a bearing:

    state write         ⟳·⟳  READ · · WEAVE          (generic fallback)
    scout recon         ⟳⟲⟳  READ · WILDCARD · WEAVE (field reconnaissance)
    committee delib     ⟳⟲⟳  READ · WILDCARD · WEAVE (bicameral deliberation)
    loom scan           ⟳⟲⟲  READ · WILDCARD · ANALYSE (topology analysis)
    tailor fitting      ⟳·⟳  READ · · WEAVE          (cognitive shadow)
    context drive       ⟳⟳⟳  READ · SPECIFIC · WEAVE (memory drive work)
    gate reflection     ⟳·⟲  READ · · UNRAVEL        (weight-vest self-check)
    sync send           ⟳⟳⟳  READ · SPECIFIC · WEAVE (outgoing communication)
    legal surveillance  ⟳·⟲  READ · · UNRAVEL        (compliance monitoring)
    domain monitoring   ⟳·⟳  READ · · WEAVE          (pattern watching)

The day's events are aggregated by per-axis majority vote into a single
dominant bearing — the orbit you were actually in. The report also
detects stasis (long idle gaps) and drift (how today's orbit differs from
yesterday's), so the machine that executes your intent can finally tell
you what intent you actually had.

Read-only by default; the only writes are explicit `--snapshot` records
into ~/.whorl/drift.json.
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from whorl.core.bearing import Bearing, Rotation


# ─── events ───────────────────────────────────────────────────────────────

@dataclass
class Event:
    at: float
    bearing: Bearing
    label: str


# Namespace → intent mapping for SharedState records.
# Order matters: more specific prefixes must come BEFORE broader ones
# since _bearing_for_key matches the first hit.
_KEY_BEARINGS: list[tuple[str, Bearing, str]] = [
    # ── scout swarm → drive keys (must precede "memory:") ──────────
    # Finding: the scout gathered broadly and synthesised.
    ("memory:drive:scouts:finding:",
     Bearing(x=Rotation.CW, y=Rotation.CCW, z=Rotation.CW, speed=7),
     "scout reconnaissance"),
    # Legal: focused surveillance — watching for compliance cracks.
    ("memory:drive:scouts:legal:",
     Bearing(x=Rotation.CW, y=Rotation.STATIC, z=Rotation.CCW, speed=6),
     "legal surveillance"),
    # Domain: monitoring a specific domain for patterns.
    ("memory:drive:scouts:domain:",
     Bearing(x=Rotation.CW, y=Rotation.STATIC, z=Rotation.CW, speed=5),
     "domain monitoring"),
    # ── general memory drive (fallback for summaries, compressions, …) ──
    ("memory:", Bearing(x=Rotation.CW, y=Rotation.CW, z=Rotation.CW, speed=6),
     "context drive"),
    ("loom:", Bearing(x=Rotation.CW, y=Rotation.CCW, z=Rotation.CCW, speed=7),
     "topology analysis"),
    ("agent:", Bearing(x=Rotation.CW, y=Rotation.CW, z=Rotation.STATIC, speed=5),
     "agent observation"),
    ("gate:", Bearing(x=Rotation.CW, y=Rotation.STATIC, z=Rotation.CCW, speed=4),
     "gate reflection"),
    ("drift:", Bearing(x=Rotation.STATIC, y=Rotation.CCW, z=Rotation.CCW, speed=3),
     "self-telemetry"),
    ("bicameral:", Bearing(x=Rotation.CW, y=Rotation.CCW, z=Rotation.CW, speed=8),
     "committee deliberation"),
    ("tailor:", Bearing(x=Rotation.CW, y=Rotation.STATIC, z=Rotation.CW, speed=6),
     "tailor fitting"),
]
_DEFAULT_WRITE = Bearing(x=Rotation.CW, y=Rotation.STATIC, z=Rotation.CW, speed=5)

LOOM_BEARING = Bearing(x=Rotation.CW, y=Rotation.CCW, z=Rotation.CCW, speed=7)
SYNC_BEARING = Bearing(x=Rotation.CW, y=Rotation.CW, z=Rotation.CW, speed=8)
TOUCH_BEARING = Bearing(x=Rotation.CW, y=Rotation.STATIC, z=Rotation.STATIC, speed=2)


def _bearing_for_key(key: str) -> tuple[Bearing, str]:
    for prefix, bearing, label in _KEY_BEARINGS:
        if key.startswith(prefix):
            return bearing, label
    return _DEFAULT_WRITE, "state write"


# ─── collectors (all read-only, bounded) ─────────────────────────────────

def collect_state_events(
    state_dir: str = "~/.whorl",
    since: float = 0.0,
    max_files: int = 32,
) -> list[Event]:
    """SharedState records created/updated in the window, plus file mtimes."""
    events: list[Event] = []
    state_dir = os.path.expanduser(state_dir)
    if not os.path.isdir(state_dir):
        return events

    files = sorted(
        f for f in os.listdir(state_dir) if f.endswith(".json")
    )[:max_files]

    for name in files:
        path = os.path.join(state_dir, name)
        try:
            with open(path, "r") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                continue
        except (json.JSONDecodeError, OSError):
            # Not a valid store — count the file touch itself.
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime >= since:
                events.append(Event(at=mtime, bearing=TOUCH_BEARING,
                                    label=f"state file touched: {name}"))
            continue

        # Valid SharedState store — records carry timestamps.
        for key, rec in raw.items():
            if not isinstance(rec, dict):
                continue
            created = rec.get("created_at") or 0
            updated = rec.get("updated_at") or created
            bearing, label = _bearing_for_key(key)
            for at in (created, updated):
                if at and at >= since:
                    events.append(Event(at=at, bearing=bearing, label=label))

    return events


def collect_loom_events(since: float = 0.0, limit: int = 50) -> list[Event]:
    """Scan records from the loom history ledger."""
    events: list[Event] = []
    try:
        from whorl.loom import history
        for rec in history(limit=limit):
            at = rec.get("timestamp") or 0
            if at >= since:
                events.append(Event(at=at, bearing=LOOM_BEARING,
                                    label="loom scan"))
    except Exception:
        pass
    return events


def collect_sync_events(
    sync_dirs: Optional[list[str]] = None,
    since: float = 0.0,
    max_files: int = 300,
) -> list[Event]:
    """Queue dirs (hermes_outbox, penguin_r18, hermes_arc, ...) with
    messages touched in the window = outgoing communication."""
    if sync_dirs is None:
        sync_dirs = [
            os.path.expanduser("~/sync_bus/hermes_outbox"),
            os.path.expanduser("~/sync_bus/penguin_r18"),
            os.path.expanduser("~/sync_bus/hermes_arc"),
        ]
    events: list[Event] = []
    for d in sync_dirs:
        if not os.path.isdir(d):
            continue
        newest = 0.0
        count = 0
        for root, _dirs, files in os.walk(d):
            for f in files:
                if f.startswith("."):
                    continue
                count += 1
                if count > max_files:
                    break
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(root, f)))
                except OSError:
                    continue
            if count > max_files:
                break
        if newest >= since and newest > 0:
            events.append(Event(at=newest, bearing=SYNC_BEARING,
                                label=f"sync: {os.path.basename(d)}"))
    return events


# ─── aggregation ──────────────────────────────────────────────────────────

def aggregate_bearings(events: list[Event]) -> Bearing:
    """Per-axis majority vote across the day's events (ties → STATIC)."""
    def _majority(vals: list[int]) -> Rotation:
        if not vals:
            return Rotation.STATIC
        cw = vals.count(1)
        ccw = vals.count(-1)
        if cw > ccw:
            return Rotation.CW
        if ccw > cw:
            return Rotation.CCW
        return Rotation.STATIC

    xs = [e.bearing.x.value for e in events if e.bearing.x != Rotation.STATIC]
    ys = [e.bearing.y.value for e in events if e.bearing.y != Rotation.STATIC]
    zs = [e.bearing.z.value for e in events if e.bearing.z != Rotation.STATIC]

    speed = 1
    if events:
        speed = int(round(sum(e.bearing.speed for e in events) / len(events)))
        speed = max(1, min(10, speed))

    return Bearing(_majority(xs), _majority(ys), _majority(zs), speed)


def _fmt_gap(seconds: float) -> str:
    if seconds >= 86400:
        return f"{seconds / 86400:.1f}d"
    if seconds >= 3600:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 60:.0f}m"


def _stasis(events: list[Event]) -> Optional[float]:
    """Longest idle gap between consecutive events in the window."""
    if len(events) < 2:
        return None
    times = sorted(e.at for e in events)
    return max(b - a for a, b in zip(times, times[1:]))


# ─── orbit report ─────────────────────────────────────────────────────────

def _roadmap_open_items(path: str) -> int:
    try:
        if not os.path.exists(path):
            return -1
        with open(path, "r") as fh:
            return sum(1 for line in fh if line.strip().startswith("- [ ]"))
    except (OSError, UnicodeDecodeError):
        return -1


def orbit_report(
    days: int = 1,
    *,
    state=None,
    roadmap_path: str = "~/ROADMAP.md",
) -> dict[str, Any]:
    """
    Compute today's orbit. Pure read except for nothing — snapshotting is
    an explicit, separate step so a nightly cron can do both:
        whorl drift && whorl drift --snapshot
    """
    since = time.time() - days * 86400
    events = (
        collect_state_events(since=since)
        + collect_loom_events(since=since)
        + collect_sync_events(since=since)
    )
    events.sort(key=lambda e: e.at)

    bearing = aggregate_bearings(events)

    counts: dict[str, int] = {}
    for e in events:
        counts[e.label] = counts.get(e.label, 0) + 1

    # Drift vs the previous day's snapshot.
    from datetime import date, timedelta
    drift: Optional[dict] = None
    if state is not None:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        prev = state.read(f"drift:history:{yesterday}")
        if isinstance(prev, dict):
            prev_b = Bearing.from_dict(prev)
            changed = []
            for axis, a, b in (("data", prev_b.x, bearing.x),
                               ("scope", prev_b.y, bearing.y),
                               ("transform", prev_b.z, bearing.z)):
                if a != b:
                    changed.append(axis)
            drift = {
                "prev": prev_b.to_dict(),
                "now": bearing.to_dict(),
                "changed_axes": changed,
            }

    gap = _stasis(events)
    open_items = _roadmap_open_items(os.path.expanduser(roadmap_path))

    return {
        "date": time.strftime("%Y-%m-%d", time.localtime()),
        "window_days": days,
        "events": len(events),
        "bearing": bearing.to_dict(),
        "glyph": bearing.glyph(),
        "intent": bearing.summary,
        "speed": bearing.speed,
        "activity": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "stasis_seconds": gap,
        "drift": drift,
        "roadmap_open_items": open_items if open_items >= 0 else None,
    }


def format_report(report: dict[str, Any]) -> str:
    """The human-facing orbit report."""
    b = report["bearing"]
    glyph = report["glyph"]
    intent = report["intent"]
    speed = report["speed"]
    lines = [
        f"── ORBIT REPORT · {report['date']} ─{'─' * max(0, 26 - len(report['date']))}",
        f"  dominant bearing   {glyph}  {intent}  (speed {speed}/10)",
    ]

    activity = report["activity"]
    if activity:
        mix = " · ".join(f"{n}× {label}" for label, n in list(activity.items())[:5])
        lines.append(f"  activity           {mix}")
    else:
        lines.append("  activity           none detected — the floor is still.")

    gap = report.get("stasis_seconds")
    if gap and gap > 3600:
        lines.append(f"  stasis             {_fmt_gap(gap)} idle (longest gap)")

    drift = report.get("drift")
    if drift:
        prev = drift["prev"]
        p_glyph = Bearing.from_dict(prev).glyph()
        changed = drift["changed_axes"]
        if changed:
            lines.append(
                f"  drift              {p_glyph} → {glyph}  "
                f"(axes moved: {', '.join(changed)})"
            )
        else:
            lines.append(f"  drift              none — same orbit as yesterday ({glyph})")
    else:
        lines.append("  drift              no previous orbit recorded")

    open_items = report.get("roadmap_open_items")
    if open_items is not None:
        if open_items > 0:
            lines.append(f"  roadmap            {open_items} open item(s) still in orbit")
        else:
            lines.append("  roadmap            clean — nothing open")

    if report["events"] == 0:
        lines.append("  verdict            NULL STASIS. The vane sees no rotation.")
    else:
        lines.append(f"  verdict            you are orbiting {intent.lower()} at speed {speed}.")
    return "\n".join(lines)


# ─── snapshots (explicit, opt-in) ─────────────────────────────────────────

def snapshot(state=None) -> str:
    """Persist today's bearing to SharedState so tomorrow can measure drift."""
    report = orbit_report(1, state=state)
    today = report["date"]
    if state is not None:
        state.write(f"drift:history:{today}", report["bearing"],
                    "whorl.drift")
    return today


def history(state=None, limit: int = 10) -> list[dict]:
    """Most recent daily snapshots, newest first."""
    if state is None:
        return []
    keys = sorted(state.keys_starting_with("drift:history:"), reverse=True)
    out = []
    for key in keys[:limit]:
        rec = state.read(key)
        date_str = key.replace("drift:history:", "")
        if isinstance(rec, dict):
            b = Bearing.from_dict(rec)
            out.append({"date": date_str, "glyph": b.glyph(),
                        "intent": b.summary, "speed": b.speed})
    return out
