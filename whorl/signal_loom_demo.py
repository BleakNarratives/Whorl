"""Bounded, offline Signal Loom demonstration.

The demo uses synthetic records only. It does not read live telemetry, publish to
the bus, execute interventions, or mutate agent state.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from whorl.signal_loom import Hotspot, lifecycle_event, rank_hotspots
from whorl.signal_loom_adapters import adapt_memguard, adapt_overseer


SYNTHETIC_MEMGUARD: List[Dict[str, Any]] = [
    {"ts": "2030-01-01T00:00:01Z", "event": "state_change",
     "detail": {"from": "NOMINAL", "to": "PRESSURE"},
     "avail_mb": 720, "psi_some_avg10": 2.1},
    {"ts": "2030-01-01T00:00:02Z", "event": "controlled_sacrifice",
     "detail": {"pid": 42, "rss_mb": 24}, "avail_mb": 390,
     "psi_some_avg10": 12.4},
]

SYNTHETIC_OVERSEER: List[Dict[str, Any]] = [
    {"ts": "2030-01-01T00:00:03Z", "event": "pressure_enter",
     "severity": "high", "queue_depth": 0},
    {"ts": "2030-01-01T00:00:04Z", "event": "cycle",
     "severity": "moderate", "guard_actions": []},
]


def build_demo() -> Dict[str, Any]:
    """Return ranked synthetic hotspots and non-executing lifecycle events."""
    hotspots: List[Hotspot] = [
        *filter(None, (adapt_memguard(record) for record in SYNTHETIC_MEMGUARD)),
        *filter(None, (adapt_overseer(record) for record in SYNTHETIC_OVERSEER)),
    ]
    ranked = rank_hotspots(hotspots)
    events = [lifecycle_event("signal.detected", hotspot,
                               detail={"demo": True}) for hotspot in ranked]
    events.extend(lifecycle_event("hotspot.ranked", hotspot,
                                  detail={"rank": index + 1, "demo": True})
                  for index, hotspot in enumerate(ranked))
    return {
        "mode": "offline_synthetic",
        "interventions_executed": 0,
        "hotspots": [hotspot.as_dict() for hotspot in ranked],
        "events": events,
    }


def main() -> int:
    print(json.dumps(build_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
