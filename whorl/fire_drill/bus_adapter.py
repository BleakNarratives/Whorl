"""Optional offline Fire Drill transport through the Whorl Agent Bus.

The adapter is deliberately opt-in. Existing ``run_drill`` remains the
canonical direct path; this module provides a bounded integration seam for
proving dispatch/result routing without live model calls.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from whorl import bus


class BusUnavailable(RuntimeError):
    """Raised when a bus dispatch cannot be delivered."""


def dispatch_offline(
    scenario: Dict[str, Any],
    agent_name: str,
    *,
    responder: Callable[[str, str], Any],
    sender: str = "fire_drill",
    fallback: Optional[Callable[[], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Dispatch one offline task, consume its result, or use ``fallback``.

    ``responder`` is injected for offline tests and must return either a
    response string or ``(response, latency_s)``. No model/provider is called
    by this adapter.
    """
    task_id = f"offline_{scenario['id']}_{agent_name}"
    payload = {
        "task_id": task_id,
        "scenario_id": scenario["id"],
        "prompt": scenario["prompt"],
        "timeout_s": 60,
        "offline": True,
    }
    try:
        message = bus.send(sender, agent_name, "task.dispatch", payload,
                           reply_to=sender)
        if not bus.read(agent_name):
            raise BusUnavailable(f"task {task_id} was not delivered")
        started = time.monotonic()
        raw = responder(agent_name, scenario["prompt"])
        if isinstance(raw, tuple):
            response, latency = raw
        else:
            response, latency = raw, round(time.monotonic() - started, 2)
        result = {
            "task_id": task_id,
            "scenario_id": scenario["id"],
            "agent": agent_name,
            "response": str(response).strip(),
            "latency_s": float(latency),
            "offline": True,
            "dispatch_id": message["id"],
        }
        # The recipient must be registered for the result envelope too. The
        # sender is a logical coordinator, so register it transiently when
        # this offline adapter is used in isolation.
        if sender not in bus.load_registry():
            bus.register(sender, "offline-adapter")
        bus.send(agent_name, sender, "task.result", result, reply_to=sender)
        return result
    except (OSError, ValueError, KeyError, TypeError, BusUnavailable):
        if fallback is None:
            raise
        result = fallback()
        result["transport"] = "direct_fallback"
        return result
