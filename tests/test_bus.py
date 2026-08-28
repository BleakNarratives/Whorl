import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whorl import bus


class BusTests(unittest.TestCase):
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

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def test_send_delivers_atomic_envelope(self):
        bus.register("agent-a", "v1", capabilities=["respond"])
        message = bus.send("tester", "agent-a", "task.dispatch", {"task_id": "t1"})
        inbox = list((self.paths["INBOX_DIR"] / "agent-a").glob("*.json"))
        self.assertEqual(len(inbox), 1)
        self.assertEqual(json.loads(inbox[0].read_text())["id"], message["id"])
        self.assertEqual(bus.read("agent-a")[0]["type"], "task.dispatch")
        self.assertEqual(message["clock"], 1)

    def test_unknown_recipient_is_dead_lettered(self):
        bus.send("tester", "missing", "task.dispatch", {})
        dead = list(self.paths["DEAD_DIR"].glob("*.json"))
        self.assertEqual(len(dead), 1)
        record = json.loads(dead[0].read_text())
        self.assertEqual(record["reason"], "recipient_not_registered")
        self.assertEqual(bus.status()["dead_letters"], 1)

    def test_broadcast_delivery(self):
        bus.register("agent-a", "v1")
        message = bus.send("tester", "broadcast", "system.ping", {})
        self.assertEqual(bus.read("broadcast")[0]["id"], message["id"])

    def test_heartbeat_requires_registration(self):
        with self.assertRaisesRegex(ValueError, "not registered"):
            bus.heartbeat("missing")
        bus.register("agent-a", "v1")
        entry = bus.heartbeat("agent-a", status="busy", uptime_s=4.5, last_task="t1")
        self.assertEqual(entry["status"], "busy")
        self.assertEqual(entry["last_task"], "t1")

    def test_registry_status_marks_active(self):
        bus.register("agent-a", "v1", heartbeat_s=1)
        registry = bus.registry_status()
        self.assertEqual(registry["agent-a"]["status"], "active")

    def test_duplicate_message_id_is_idempotent(self):
        bus.register("agent-a", "v1")
        first = bus.send("tester", "agent-a", "task.dispatch", {}, message_id="fixed")
        second = bus.send("tester", "agent-a", "task.dispatch", {}, message_id="fixed")
        self.assertEqual(first, second)
        self.assertEqual(len(list((self.paths["INBOX_DIR"] / "agent-a").glob("*.json"))), 1)

    def test_acknowledge_archives_message(self):
        bus.register("agent-a", "v1")
        message = bus.send("tester", "agent-a", "system.ping", {})
        self.assertTrue(bus.acknowledge("agent-a", message["id"]))
        self.assertEqual(bus.read("agent-a"), [])
        self.assertGreaterEqual(bus.status()["archived"], 1)

    def test_expire_moves_old_message_to_dead_letters(self):
        bus.register("agent-a", "v1")
        message = bus.send("tester", "agent-a", "task.dispatch", {}, ttl_s=0)
        with patch.object(bus, "_expired", return_value=True):
            expired = bus.expire("agent-a")
        self.assertEqual([item["id"] for item in expired], [message["id"]])
        self.assertEqual(bus.dead_letters(reason="ttl_expired")[0]["message"]["id"], message["id"])

    def test_atomic_temp_files_are_not_read_as_messages(self):
        bus.register("agent-a", "v1")
        inbox = self.paths["INBOX_DIR"] / "agent-a"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / ".partial.tmp").write_text("{")
        self.assertEqual(bus.read("agent-a"), [])


if __name__ == "__main__":
    unittest.main()
