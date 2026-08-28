import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whorl import agent_state, bus
from whorl.fire_drill.score_bus import consume_scores, publish_score


class ScoreBusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = {
            "BUS_DIR": root / "bus",
            "INBOX_DIR": root / "bus" / "inbox",
            "OUTBOX_DIR": root / "bus" / "outbox",
            "DEAD_DIR": root / "bus" / "dead",
            "ARCHIVE_DIR": root / "bus" / "archive",
            "LOG_DIR": root / "bus" / "log",
            "LOG_FILE": root / "bus" / "log" / "bus.jsonl",
            "REGISTRY_FILE": root / "bus" / "registry.json",
            "CLOCK_FILE": root / "bus" / "clock",
        }
        self.patches = [patch.object(bus, name, value) for name, value in self.paths.items()]
        for patcher in self.patches:
            patcher.start()
        bus.register("agent_state", "test-v1")
        patcher = patch.object(agent_state, "AGENTS_DIR", root / "agents")
        patcher.start()
        self.patches.append(patcher)

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def test_publish_and_consume_score(self):
        message = publish_score("yvette", "scenario-1", 0.81, True,
                                "scenario-1 passed", message_id="score-1")
        self.assertEqual(message["type"], "score.record")
        self.assertEqual(consume_scores(), 1)
        state = agent_state.current("yvette")
        self.assertEqual(state["scores"]["fire_drill"]["last"], 0.81)
        self.assertEqual(bus.read("agent_state"), [])
        self.assertEqual(bus.status()["archived"], 1)

    def test_duplicate_score_message_is_idempotent(self):
        publish_score("yvette", "scenario-1", 0.81, True, message_id="score-dup")
        publish_score("yvette", "scenario-1", 0.81, True, message_id="score-dup")
        with patch.object(agent_state, "record_score", wraps=agent_state.record_score) as record:
            self.assertEqual(consume_scores(), 1)
            self.assertEqual(consume_scores(), 0)
            self.assertEqual(record.call_count, 1)

    def test_unknown_agent_state_recipient_is_dead_lettered(self):
        bus.unregister = getattr(bus, "unregister", None)
        bus.REGISTRY_FILE.write_text(json.dumps({}))
        message = publish_score("yvette", "scenario-1", 0.5, False)
        self.assertEqual(message["to"], "agent_state")
        self.assertEqual(len(bus.dead_letters()), 1)


if __name__ == "__main__":
    unittest.main()
