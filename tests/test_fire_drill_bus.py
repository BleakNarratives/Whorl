import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whorl import bus
from whorl.fire_drill.bus_adapter import dispatch_offline


class FireDrillBusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = {
            "BUS_DIR": root / "bus",
            "INBOX_DIR": root / "bus" / "inbox",
            "OUTBOX_DIR": root / "bus" / "outbox",
            "DEAD_DIR": root / "bus" / "dead",
            "LOG_DIR": root / "bus" / "log",
            "LOG_FILE": root / "bus" / "log" / "bus.jsonl",
            "REGISTRY_FILE": root / "bus" / "registry.json",
            "CLOCK_FILE": root / "bus" / "clock",
        }
        self.patches = [patch.object(bus, name, value) for name, value in self.paths.items()]
        for patcher in self.patches:
            patcher.start()
        bus.register("offline-agent", "test-v1")
        self.scenario = {"id": "scenario-1", "prompt": "Answer offline."}

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def test_dispatch_routes_task_and_result(self):
        result = dispatch_offline(
            self.scenario,
            "offline-agent",
            responder=lambda agent, prompt: ("offline response", 0.01),
        )
        self.assertEqual(result["response"], "offline response")
        self.assertEqual(result["dispatch_id"].startswith("msg_"), True)
        messages = list((self.paths["INBOX_DIR"] / "fire_drill").glob("*.json"))
        self.assertEqual(len(messages), 1)
        delivered = json.loads(messages[0].read_text())
        self.assertEqual(delivered["type"], "task.result")
        self.assertEqual(delivered["payload"]["task_id"], result["task_id"])

    def test_bus_failure_uses_direct_fallback(self):
        fallback = lambda: {"run_id": "direct-1", "composite": 0.75}
        with patch.object(bus, "send", side_effect=OSError("bus unavailable")):
            result = dispatch_offline(
                self.scenario,
                "offline-agent",
                responder=lambda _agent, _prompt: "never reached",
                fallback=fallback,
            )
        self.assertEqual(result["transport"], "direct_fallback")
        self.assertEqual(result["run_id"], "direct-1")


if __name__ == "__main__":
    unittest.main()
