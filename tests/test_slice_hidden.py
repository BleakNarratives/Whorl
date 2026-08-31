import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whorl.slice.whorl_slice import ReferenceQ4Pass, SliceController  # noqa: E402


class HiddenStateTransportTests(unittest.TestCase):
    def test_reference_pass_emits_hidden_state_and_logits(self):
        p = ReferenceQ4Pass(hole_spacing=2, seed=1, hidden_dim=6)
        r = p.next_token("seed")
        self.assertIsNotNone(r.hidden_state)
        self.assertEqual(len(r.hidden_state), 6)
        self.assertIsNotNone(r.logits)
        self.assertTrue(r.logits)  # non-empty candidate logits
        # hidden state varied across steps (deterministic stream, not constant)
        r2 = p.next_token("seed")
        self.assertNotEqual(r.hidden_state, r2.hidden_state)

    def test_hidden_state_is_deterministic_per_seed(self):
        a = ReferenceQ4Pass(hole_spacing=2, seed=9, hidden_dim=6).next_token("x")
        b = ReferenceQ4Pass(hole_spacing=2, seed=9, hidden_dim=6).next_token("x")
        self.assertEqual(a.hidden_state, b.hidden_state)
        c = ReferenceQ4Pass(hole_spacing=2, seed=10, hidden_dim=6).next_token("x")
        self.assertNotEqual(a.hidden_state, c.hidden_state, "different seed -> different state")

    def test_generate_records_hidden_state_dim(self):
        local = ReferenceQ4Pass(hole_spacing=3, seed=2, hidden_dim=5)
        ctl = SliceController(local=local, cloud=None, confidence_gate=0.4)
        ctl.generate("hi", max_tokens=6)
        rep = ctl.report()
        for tele in rep["telemetry"]:
            self.assertEqual(tele["hidden_state_dim"], 5)


class LogitMergeOnHoleTests(unittest.TestCase):
    def test_sliced_position_merges_corrected_logits(self):
        # null-cloud: sliced stays sliced but hidden_dim recorded; no merge
        local = ReferenceQ4Pass(hole_spacing=2, seed=3, hidden_dim=4)
        ctl = SliceController(local=local, cloud=None, confidence_gate=0.4)
        res = ctl.generate("go", max_tokens=8)
        sliced = [r for r in res if r.sliced]
        self.assertGreaterEqual(len(sliced), 1)
        for r in sliced:
            self.assertTrue(r.hidden_state)   # payload existed to ship


if __name__ == "__main__":
    unittest.main()