import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whorl.slice.whorl_slice import (  # noqa: E402
    CloudFp16Pass,
    ReferenceQ4Pass,
    SliceController,
)

# Tests run against the deterministic reference backend — no model binary, no
# network. CloudFp16Pass is excluded from these (offline unit tests).


class ReferenceQ4PassTests(unittest.TestCase):
    def test_holes_inject_low_confidence(self):
        p = ReferenceQ4Pass(hole_spacing=3, seed=1)
        confs = [p.next_token("x").confidence for _ in range(9)]
        # positions 3, 6, 9 are holes -> confidence ~0 at those
        hole_positions = [i for i, c in enumerate(confs, start=1) if c < 0.2]
        self.assertIn(3, hole_positions)
        self.assertIn(6, hole_positions)
        # non-hole positions are well above the gate
        self.assertTrue(all(cs >= 0.4 for cs in confs if cs >= 0.2))

    def test_deterministic(self):
        def tokens(seed):
            p = ReferenceQ4Pass(seed=seed)
            return [p.next_token("ignore").top_k for _ in range(5)]
        self.assertEqual(tokens(5), tokens(5))
        self.assertEqual(tokens(11), tokens(11))
        self.assertNotEqual(tokens(5), tokens(11), "different seeds -> different streams")


class SliceControllerTests(unittest.TestCase):
    def test_generates_expected_length(self):
        local = ReferenceQ4Pass(hole_spacing=4, seed=7)
        ctl = SliceController(local=local, cloud=None, confidence_gate=0.4)
        res = ctl.generate("hello", max_tokens=8)
        self.assertEqual(len(res), 8)
        for r in res:
            self.assertTrue(r.token)

    def test_holes_get_sliced_flag(self):
        local = ReferenceQ4Pass(hole_spacing=4, seed=7)
        ctl = SliceController(local=local, cloud=None, confidence_gate=0.4)
        res = ctl.generate("hello", max_tokens=12)
        sliced = [r for r in res if r.sliced]
        self.assertGreaterEqual(len(sliced), 1, "hole_spacing=4 x 12 tokens must slice")
        # sliced positions are exactly the low-confidence ones
        for r in sliced:
            self.assertLess(r.confidence, 0.4)

    def test_no_cloud_means_corrected_stays_none(self):
        local = ReferenceQ4Pass(hole_spacing=3, seed=3)
        ctl = SliceController(local=local, cloud=None, confidence_gate=0.4)
        res = ctl.generate("x", max_tokens=6)
        self.assertTrue(all(r.corrected is None for r in res))

    def test_report_shape(self):
        local = ReferenceQ4Pass(hole_spacing=4, seed=1)
        ctl = SliceController(local=local, cloud=None, confidence_gate=0.4)
        ctl.generate("y", max_tokens=10)
        rep = ctl.report()
        self.assertEqual(rep["positions"], 10)
        self.assertEqual(rep["cloud_present"], False)
        self.assertEqual(len(rep["telemetry"]), 10)
        self.assertGreaterEqual(rep["sliced"], 1)


class CloudFp16PassTests(unittest.TestCase):
    def test_init_without_boardroom_does_not_raise(self):
        # Should degrade to unavailable rather than throwing when router missing.
        try:
            c = CloudFp16Pass()
            self.assertIsInstance(c.available, bool)
        except Exception:  # noqa: BLE001
            self.fail("CloudFp16Pass init should never raise")


if __name__ == "__main__":
    unittest.main()