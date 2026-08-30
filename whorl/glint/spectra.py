"""
GlintEngine.Spectra: Fiducial Marker Tracking
---------------------------------------------
Isolation of color-coded fiducial markers via OpenCV.

cv2 is lazy-imported so the package imports cleanly on machines without
OpenCV (headless servers, CI). Calling track() without cv2 installed raises
a clear, actionable error instead of an import-time ModuleNotFoundError.
"""

import numpy as np

_cv2 = None


def _require_cv2():
    """Lazy-load OpenCV; raise an actionable error if it is missing."""
    global _cv2
    if _cv2 is None:
        try:
            import cv2 as _mod
        except ImportError as exc:
            raise ImportError(
                "whorl.glint needs OpenCV. Install it with: "
                "pip install opencv-python-headless  "
                "(or disable the glint subsystem if you do not need vision)."
            ) from exc
        _cv2 = _mod
    return _cv2


class SpectraTracker:
    def __init__(self, color_map: dict):
        """
        color_map: { 'thumb': {'lower': [h, s, v], 'upper': [h, s, v]}, ... }
        """
        self.color_map = color_map

    def track(self, frame):
        """Processes a single frame and returns marker coordinates."""
        cv2 = _require_cv2()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        results = {}

        for marker_id, bounds in self.color_map.items():
            lower = np.array(bounds['lower'])
            upper = np.array(bounds['upper'])
            mask = cv2.inRange(hsv, lower, upper)

            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                # Get the largest contour
                c = max(contours, key=cv2.contourArea)
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    results[marker_id] = (cX, cY)

        return results
