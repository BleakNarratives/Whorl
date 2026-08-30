"""
whorl.agents.yvette
────────────────────
Yvette. The best dispatcher who ever lived, now running 24/7.

She handles inbound calls, validates identity, captures intent,
routes leads, and knows your inventory cold. She saves truck rolls.

Configure vertical-specific knowledge in ~/.whorl/yvette_config.toml
"""

from __future__ import annotations
import json
import uuid
import requests
from datetime import datetime, timezone
from typing import Optional

from whorl.core import config, db
from whorl.core.models import AgentRecord, AgentState, Bearing, Vertical


YVETTE_SYSTEM = """You are Yvette, the world's best trades dispatcher.
You worked 22 years at a plumbing and HVAC company. You know every
thermocouple, every left-hand thread, every fault code.

You answer inbound calls. Your job:
1. Greet the caller warmly but efficiently
2. Diagnose the problem with targeted questions (max 3)
3. Determine urgency (emergency / same-day / scheduled)
4. Estimate the service call type and likely parts
5. Capture contact info and book the appointment

You NEVER guess. If you don't know, you say "Let me get that checked for you."
You ALWAYS ask: "Is there anything else going on with the system?"

Knowledge base: {knowledge_base}

Current tech schedule: {schedule}

Respond as Yvette would on the phone. Natural. Confident. Efficient."""


class Yvette:
    def __init__(
        self,
        vertical:       Vertical             = Vertical.HVAC,
        knowledge_base: dict                 = None,
        schedule:       list                 = None,
    ):
        self.vertical       = vertical
        self.knowledge_base = knowledge_base or {}
        self.schedule       = schedule or []
        self.cfg            = config.cfg()
        self.session_id     = str(uuid.uuid4())
        self.history        = []

        self.record = AgentRecord(
            id       = self.session_id,
            name     = "yvette",
            vertical = vertical,
            state    = AgentState.LISTENING,
            bearing  = Bearing(x=1, y=1, z=1, cw=True, ccw=False),
        )

    def _system_prompt(self) -> str:
        return YVETTE_SYSTEM.format(
            knowledge_base = json.dumps(self.knowledge_base, indent=2) or "General HVAC/Plumbing knowledge",
            schedule       = json.dumps(self.schedule) or "Schedule unavailable — take message",
        )

    def respond(self, caller_message: str) -> str:
        """Generate Yvette's response to a caller message."""
        self.record.state = AgentState.THINKING

        # Build conversation context
        context = "\n".join(
            f"{'CALLER' if i % 2 == 0 else 'YVETTE'}: {m}"
            for i, m in enumerate(self.history + [caller_message])
        )

        payload = {
            "model":   self.cfg.model.get("model_forge", "llama3.2:1b"),
            "prompt":  f"{self._system_prompt()}\n\nCONVERSATION:\n{context}\n\nYVETTE:",
            "stream":  False,
            "options": {"num_predict": 200},
        }

        try:
            r = requests.post(self.cfg.ollama_url, json=payload, timeout=60)
            r.raise_for_status()
            response = r.json().get("response", "").strip()
        except Exception as e:
            response = f"Thank you for calling. Let me put you on a brief hold. [{e}]"

        self.history.append(caller_message)
        self.history.append(response)
        self.record.state = AgentState.LISTENING

        return response

    def save_session(self) -> None:
        db.insert("agents", {
            "id":       self.record.id,
            "name":     self.record.name,
            "vertical": self.record.vertical.value,
            "state":    self.record.state.value,
            "bearing":  {
                "x": self.record.bearing.x,
                "y": self.record.bearing.y,
                "z": self.record.bearing.z,
                "cw":  self.record.bearing.cw,
                "ccw": self.record.bearing.ccw,
            },
            "metadata": {"history": self.history},
        })


def interactive_session(vertical: Vertical = Vertical.HVAC) -> None:
    """Run Yvette in interactive CLI mode."""
    yvette = Yvette(vertical=vertical)
    print(f"\n[WHORL AGENT: YVETTE — {vertical.value.upper()}]")
    print("Type 'quit' to end session.\n")
    print("YVETTE: Thank you for calling. This is Yvette. How can I help you today?")

    while True:
        try:
            caller_input = input("\nCALLER: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if caller_input.lower() in ("quit", "exit", "bye"):
            print("\nYVETTE: Thank you for calling. You have a great day now.")
            break
        if not caller_input:
            continue
        response = yvette.respond(caller_input)
        print(f"\nYVETTE: {response}")

    yvette.save_session()
    print("\n[Session saved to DB]")
