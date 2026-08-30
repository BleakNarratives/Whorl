import json
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel

# Mocking the import from the suggested bridge structure for now
# as we finalize the pipeline definition.
class ExtractionResult(BaseModel):
    question: str
    answer: str
    confidence: float
    source: str
    timestamp: Optional[str] = None

class WhorlBusAdapter:
    """
    Zero-RAM, Bus-Native Adapter.
    Translates DSPy execution outputs into strict Whorl bus events.
    """
    def __init__(self, bus_path: str = "bus.jsonl"):
        self.bus_path = bus_path

    def emit_task_result(self, dspy_payload: ExtractionResult, task_id: str, agent_id: str) -> Dict[str, Any]:
        """Convert DSPy ExtractionResult into a validated task.result bus event."""
        
        # Enforce memory safety cutoff (Double Guardrail)
        clean_answer = dspy_payload.answer[:250] + "..." if len(dspy_payload.answer) > 250 else dspy_payload.answer

        event = {
            "event_type": "task.result",
            "task_id": task_id,
            "agent_id": agent_id,
            "status": "success",
            "payload": {
                "question": dspy_payload.question,
                "answer": clean_answer,
                "confidence": dspy_payload.confidence,
                "source": dspy_payload.source
            },
            "timestamp": dspy_payload.timestamp or (datetime.utcnow().isoformat() + "Z")
        }

        self._append_to_bus(event)
        return event

    def emit_score_record(self, agent_id: str, score: float, scenario_id: str) -> Dict[str, Any]:
        """Emit idempotent score updates directly to agent_state."""
        event = {
            "event_type": "score.record",
            "agent_id": agent_id,
            "scenario_id": scenario_id,
            "score": max(0.0, min(1.0, float(score))),  # Bound 0.0 to 1.0
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        self._append_to_bus(event)
        return event

    def _append_to_bus(self, data: Dict[str, Any]) -> None:
        """Atomic line write to bus.jsonl - no memory locking."""
        with open(self.bus_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
