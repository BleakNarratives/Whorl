import unittest
from pathlib import Path

sys_path = str(Path(__file__).resolve().parent.parent)
if sys_path not in __import__("sys").path:
    import sys as _sys
    _sys.path.insert(0, sys_path)

from whorl.glint.spectra import SpectraTracker, _require_cv2  # noqa: E402
from whorl.glint.vane import VaneMapper  # noqa: E402

try:
    import cv2  # noqa: F401

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class GlintImportTests(unittest.TestCase):
    def test_package_imports_without_cv2(self):
        import whorl.glint

        self.assertIn("SpectraTracker", whorl.glint.__all__)
        self.assertIn("VaneMapper", whorl.glint.__all__)

    def test_lazy_cv2_returns_module_or_raises_actionable(self):
        try:
            mod = _require_cv2()
        except ImportError as exc:
            self.assertIn("opencv-python-headless", str(exc))
        else:
            self.assertTrue(hasattr(mod, "cvtColor"))


@unittest.skipUnless(HAS_CV2, "OpenCV not installed on this machine")
class GlintTrackingTests(unittest.TestCase):
    def test_track_finds_bright_marker(self):
        import numpy as np

        cv2 = _require_cv2()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 5, (0, 255, 0), -1)
        tracker = SpectraTracker({"thumb": {"lower": [40, 100, 100], "upper": [80, 255, 255]}})
        result = tracker.track(frame)
        self.assertIn("thumb", result)

    def test_track_returns_empty_on_blank_frame(self):
        import numpy as np

        tracker = SpectraTracker({"thumb": {"lower": [40, 100, 100], "upper": [80, 255, 255]}})
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertEqual(tracker.track(blank), {})


class VaneMapperTests(unittest.TestCase):
    def test_center_maps_to_zero(self):
        vane = VaneMapper(640, 480)
        bearing = vane.map_to_bearing((320, 240))
        self.assertAlmostEqual(bearing["r"], 0.0)
        self.assertAlmostEqual(bearing["theta"], 0.0)

    def test_bearing_radius_bounded(self):
        vane = VaneMapper(640, 480)
        bearing = vane.map_to_bearing((0, 0))
        self.assertLessEqual(bearing["r"], 1.5)
        self.assertGreaterEqual(bearing["r"], 0.0)


if __name__ == "__main__":
    unittest.main()
