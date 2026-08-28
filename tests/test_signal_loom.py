import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whorl import bus
from whorl.signal_loom import (
    LIFECYCLE_EVENTS,
    Hotspot,
    lifecycle_event,
    make_hotspot,
    publish_lifecycle,
    rank_hotspots,
)


class SignalLoomTests(unittest.TestCase):
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
        bus.register("signal_loom", "test-v1")

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def hotspot(self, hotspot_id, impact, confidence, leverage, reversibility=1.0):
        return make_hotspot(
            "repeated service friction",
            hotspot_id=hotspot_id,
            category="reliability",
            source="test",
            impact=impact,
            confidence=confidence,
            leverage=leverage,
            reversibility=reversibility,
            rollback_plan="restore prior configuration",
        )

    def test_priority_and_deterministic_ranking(self):
        first = self.hotspot("b", 0.9, 0.9, 0.9)
        second = self.hotspot("a", 0.9, 0.9, 0.9)
        third = self.hotspot("c", 0.5, 0.9, 0.9)
        self.assertAlmostEqual(first.priority, 0.729)
        self.assertEqual([h.id for h in rank_hotspots([first, third, second])], ["a", "b", "c"])

    def test_schema_requires_rollback_and_valid_values(self):
        with self.assertRaises(ValueError):
            Hotspot("x", "reliability", "signal", rollback_plan="")
        with self.assertRaises(ValueError):
            self.hotspot("x", 1.2, 0.5, 0.5)

    def test_lifecycle_event_has_correlation_and_allowed_name(self):
        hotspot = self.hotspot("h1", 0.8, 0.8, 0.8)
        record = lifecycle_event("hotspot.ranked", hotspot)
        self.assertIn(record["event"], LIFECYCLE_EVENTS)
        self.assertEqual(record["correlation_id"], "h1")
        with self.assertRaises(ValueError):
            lifecycle_event("target.locked", hotspot)

    def test_publish_lifecycle_is_bus_audit_only(self):
        hotspot = self.hotspot("h2", 0.8, 0.8, 0.8)
        result = publish_lifecycle("signal.detected", hotspot)
        self.assertTrue(result["message_id"].startswith("msg_"))
        inbox = list((self.paths["INBOX_DIR"] / "broadcast").glob("*.json"))
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0].read_text().count("signal.detected"), 2)


if __name__ == "__main__":
    unittest.main()
