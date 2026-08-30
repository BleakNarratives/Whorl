import cv2
import numpy as np
from whorl.glint import SpectraTracker, VaneMapper

# 1. Setup simulated frame (black, with a white square)
frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.rectangle(frame, (100, 100), (150, 150), (255, 255, 255), -1)

# 2. Setup tracker/mapper
color_map = {'marker1': {'lower': [0, 0, 200], 'upper': [180, 50, 255]}}
tracker = SpectraTracker(color_map)
mapper = VaneMapper(640, 480)

# 3. Test
found = tracker.track(frame)
print(f"Detected: {found}")

if 'marker1' in found:
    bearing = mapper.map_to_bearing(found['marker1'])
    print(f"Bearing: {bearing}")
else:
    print("Marker not detected.")
