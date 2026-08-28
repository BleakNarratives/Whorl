import unittest

from whorl.signal_loom_adapters import (
    adapt_memguard, adapt_memguard_records, adapt_overseer, read_jsonl,
)


class SignalLoomAdapterTests(unittest.TestCase):
    def test_memguard_normalization(self):
        hotspot = adapt_memguard({
            "ts": "2026-08-28T00:00:00Z", "event": "state_change",
            "detail": {"to": "CRITICAL"},
        })
        self.assertEqual(hotspot.category, "memory")
        self.assertEqual(hotspot.severity, "critical")
        self.assertTrue(hotspot.dry_run)
        self.assertTrue(hotspot.approval_required)

    def test_overseer_normalization_and_malformed(self):
        self.assertIsNone(adapt_overseer({}))
        hotspot = adapt_overseer({"event": "guard_alert", "severity": "high"})
        self.assertEqual(hotspot.category, "reliability")
        self.assertEqual(hotspot.severity, "high")

    def test_stable_deduplication(self):
        record = {"ts": "same", "event": "pressure_enter"}
        result = list(adapt_memguard_records([record, dict(record)]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, adapt_memguard(record).id)

    def test_jsonl_skips_malformed_lines(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False) as stream:
            stream.write('{"event":"ok"}\nnot-json\n[]\n')
            path = stream.name
        self.assertEqual(list(read_jsonl(path)), [{"event": "ok"}])


if __name__ == "__main__":
    unittest.main()
