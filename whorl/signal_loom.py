"""Signal Loom: read-only hotspot detection and bounded intervention planning.

Public vocabulary is intentionally peaceful and operational: signals, hotspots,
interventions, validation, and recovery. This module does not execute actions.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from whorl import bus

CATEGORIES = {"reliability", "memory", "latency", "errors", "security", "revenue", "workflow"}
SEVERITIES = {"informational", "low", "moderate", "high", "critical"}
LIFECYCLE_EVENTS = (
    "signal.detected",
    "hotspot.ranked",
    "intervention.proposed",
    "intervention.simulated",
    "intervention.executed",
    "impact.measured",
    "recovery.verified",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _bounded(value: float, name: str) -> float:
    value = float(value)
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


@dataclass(frozen=True)
class Hotspot:
    """A normalized, non-executable operational hotspot."""

    id: str
    category: str
    signal: str
    severity: str = "informational"
    impact: float = 0.0
    confidence: float = 0.0
    leverage: float = 0.0
    reversibility: float = 1.0
    source: str = "unknown"
    provenance: Dict[str, Any] = field(default_factory=dict)
    recommended_intervention: str = ""
    dry_run: bool = True
    approval_required: bool = True
    rollback_plan: str = ""
    timeout_s: int = 300
    cooldown_s: int = 300
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.id or not self.signal or not self.source:
            raise ValueError("id, signal, and source are required")
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category: {self.category}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity: {self.severity}")
        for name in ("impact", "confidence", "leverage", "reversibility"):
            _bounded(getattr(self, name), name)
        if self.timeout_s < 1 or self.cooldown_s < 0:
            raise ValueError("timeout_s must be positive and cooldown_s non-negative")
        if not self.rollback_plan:
            raise ValueError("rollback_plan is required")

    @property
    def priority(self) -> float:
        return round(self.impact * self.leverage * self.confidence * self.reversibility, 6)

    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["priority"] = self.priority
        return data


def make_hotspot(signal: str, *, category: str, source: str,
                 severity: str = "informational", impact: float = 0.0,
                 confidence: float = 0.0, leverage: float = 0.0,
                 reversibility: float = 1.0, provenance: Optional[Dict[str, Any]] = None,
                 recommended_intervention: str = "", rollback_plan: str,
                 hotspot_id: Optional[str] = None, **kwargs: Any) -> Hotspot:
    return Hotspot(
        id=hotspot_id or f"hotspot_{uuid.uuid4().hex[:12]}",
        category=category,
        signal=signal,
        severity=severity,
        impact=impact,
        confidence=confidence,
        leverage=leverage,
        reversibility=reversibility,
        source=source,
        provenance=provenance or {},
        recommended_intervention=recommended_intervention,
        rollback_plan=rollback_plan,
        **kwargs,
    )


def rank_hotspots(hotspots: Iterable[Hotspot]) -> List[Hotspot]:
    """Return a deterministic priority order; input objects are not mutated."""
    return sorted(
        hotspots,
        key=lambda item: (-item.priority, -item.confidence, -item.reversibility,
                          item.category, item.id),
    )


def lifecycle_event(event: str, hotspot: Hotspot, *, actor: str = "signal_loom",
                    detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if event not in LIFECYCLE_EVENTS:
        raise ValueError(f"unknown lifecycle event: {event}")
    return {
        "event": event,
        "timestamp": _now(),
        "actor": actor,
        "correlation_id": hotspot.id,
        "hotspot": hotspot.as_dict(),
        "detail": detail or {},
    }


def publish_lifecycle(event: str, hotspot: Hotspot, *, recipient: str = "broadcast",
                      detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Publish an auditable lifecycle event; does not execute an intervention."""
    record = lifecycle_event(event, hotspot, detail=detail)
    message = bus.send("signal_loom", recipient, event, record)
    return {"message_id": message["id"], **record}


def dumps(hotspots: Iterable[Hotspot]) -> str:
    return json.dumps([hotspot.as_dict() for hotspot in hotspots], indent=2, sort_keys=True)


__all__ = [
    "Hotspot", "CATEGORIES", "SEVERITIES", "LIFECYCLE_EVENTS", "make_hotspot",
    "rank_hotspots", "lifecycle_event", "publish_lifecycle", "dumps",
]
