"""Fire Drill score feedback over the Whorl bus.

Opt-in adapter only: the existing Fire Drill runner remains unchanged.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from whorl import agent_state, bus

CONSUMER = "agent_state"


def publish_score(agent: str, scenario: str, composite: float, passed: bool,
                  detail: str = "", *, sender: str = "fire_drill",
                  message_id: Optional[str] = None) -> Dict[str, Any]:
    payload = {
        "agent": agent,
        "scenario": scenario,
        "composite": float(composite),
        "passed": bool(passed),
        "detail": detail,
    }
    return bus.send(sender, CONSUMER, "score.record", payload,
                    reply_to=sender, message_id=message_id)


def consume_scores(*, limit: int = 100, consumer: str = CONSUMER) -> int:
    """Apply pending score records once, acknowledging each after success."""
    applied = 0
    for message in bus.read(consumer, limit=limit):
        if message.get("type") != "score.record":
            continue
        message_id = message["id"]
        if _already_consumed(message_id):
            bus.acknowledge(consumer, message_id)
            continue
        payload = message.get("payload", {})
        agent = payload.get("agent")
        scenario = payload.get("scenario", "unknown")
        if not agent:
            continue
        agent_state.record_score(
            agent,
            source="fire_drill",
            detail=payload.get("detail") or f"{scenario}: {payload.get('composite', 0):.3f}",
            scores_update={
                "last": payload.get("composite", 0.0),
                "passed": payload.get("passed", False),
                "message_id": message_id,
            },
        )
        _mark_consumed(message_id)
        bus.acknowledge(consumer, message_id)
        applied += 1
    return applied


def _consumed_path() -> Any:
    return bus.BUS_DIR / "score_consumed.json"


def _already_consumed(message_id: str) -> bool:
    try:
        import json
        return message_id in json.loads(_consumed_path().read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _mark_consumed(message_id: str) -> None:
    import json
    try:
        ids = json.loads(_consumed_path().read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        ids = []
    if message_id not in ids:
        ids.append(message_id)
    _consumed_path().parent.mkdir(parents=True, exist_ok=True)
    tmp = _consumed_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(ids, sort_keys=True) + "\n")
    tmp.replace(_consumed_path())
