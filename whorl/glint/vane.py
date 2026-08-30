"""
GlintEngine.Vane: Coordinate Mapping
------------------------------------
Translates marker positions into Whorl Bearing vectors.
"""

class VaneMapper:
    def __init__(self, frame_width: int, frame_height: int):
        self.width = frame_width
        self.height = frame_height

    def map_to_bearing(self, coord: tuple):
        """
        Maps (x, y) coordinates to an Agent Bearing Vector.
        Returns: {r, theta, z} where:
          r: distance from center (0-1)
          theta: angle in radians (-pi to pi)
          z: normalized position (unused for now, maybe depth)
        """
        x, y = coord
        
        # Center coordinates
        cx = x - (self.width / 2)
        cy = y - (self.height / 2)
        
        # Distance from center
        r = ( (cx**2 + cy**2)**0.5 ) / ( (self.width/2)**2 + (self.height/2)**2 )**0.5
        
        # Angle
        import math
        theta = math.atan2(cy, cx)
        
        return {"r": round(r, 3), "theta": round(theta, 3), "z": 0.0}
