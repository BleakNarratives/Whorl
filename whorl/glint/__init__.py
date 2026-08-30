"""
GlintEngine: Fiducial-Marker Gesture Navigation
==============================================
Spectra (Tracking) + Vane (Mapping)

Both submodules import cleanly without OpenCV installed; cv2 is only
required when SpectraTracker.track() is actually called.
"""

from .spectra import SpectraTracker
from .vane import VaneMapper

__all__ = ["SpectraTracker", "VaneMapper"]
