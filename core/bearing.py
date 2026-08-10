"""
whorl.core.bearing — Rotational bearing system.

Each agent expresses intent through its rotational bearing across 3 axes.
The bearing is the fundamental communication primitive of Whorl agents.

Axes:
  X-axis  — DATA direction
    CW  (+1) : READ / COPY / OBSERVE
    CCW (-1) : REMOVE / CONSUME / ENSLAVE
    0        : null stasis on data

  Y-axis  — SCOPE
    CW  (+1) : SPECIFIC / TARGETED / PINPOINT
    CCW (-1) : WILDCARD / VARIABLE / COMBINATORIAL
    0        : default scope

  Z-axis  — TRANSFORM
    CW  (+1) : WEAVE / ENCRYPT / COMPILE / BUILD
    CCW (-1) : UNRAVEL / DECRYPT / DECOMPILE / ANALYSE
    0        : no transform

Speed (temporal bearing):
  Controls how many ticks the agent receives per runtime cycle.
  Higher speed = more frequent observation/action.
  Range: 1 (slow/lazy) to 10 (blazing).

Combined bearing states are the agent's "body language" —
other agents observe the bearing to understand intent without
needing to parse explicit messages.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class Rotation(IntEnum):
    """Rotational direction on a single axis."""
    STATIC = 0      # no rotation — null stasis
    CW     = 1      # clockwise
    CCW    = -1     # counter-clockwise

    @property
    def glyph(self) -> str:
        if self == Rotation.CW:
            return "⟳"
        elif self == Rotation.CCW:
            return "⟲"
        return "·"

    @property
    def label(self) -> str:
        return {Rotation.STATIC: "STASIS", Rotation.CW: "CW", Rotation.CCW: "CCW"}[self]


class Axis(IntEnum):
    """The three axes of rotational bearing."""
    X = 0   # DATA    — read/consume
    Y = 1   # SCOPE   — specific/wildcard
    Z = 2   # TRANSFORM — weave/unravel


# ─── Axis semantic mappings ──────────────────────────────────────────

AXIS_X_CW_INTENT  = "READ / COPY / OBSERVE"
AXIS_X_CCW_INTENT = "REMOVE / CONSUME / ENSLAVE"

AXIS_Y_CW_INTENT  = "SPECIFIC / TARGETED / PINPOINT"
AXIS_Y_CCW_INTENT = "WILDCARD / VARIABLE / COMBINATORIAL"

AXIS_Z_CW_INTENT  = "WEAVE / ENCRYPT / COMPILE / BUILD"
AXIS_Z_CCW_INTENT = "UNRAVEL / DECRYPT / DECOMPILE / ANALYSE"


# ─── Bearing ─────────────────────────────────────────────────────────

@dataclass
class Bearing:
    """
    A 3-axis rotational bearing representing agent intent.

    Each axis holds a Rotation (CW / CCW / STATIC).
    Speed (1-10) controls execution frequency in the runtime loop.

    Examples:
      NULL STASIS          — (0,0,0) — agent is idle/inactive
      OBSERVE a specific   — (CW, CW, STATIC) — read targeted data
      CONSUME wildcard     — (CCW, CCW, STATIC) — remove variable-scope data
      WEAVE a pattern      — (STATIC, CW, CW) — compile/build a specific pattern
      UNRAVEL broadly      — (STATIC, CCW, CCW) — decompile/analyse wildcard scope
    """

    x: Rotation = Rotation.STATIC
    y: Rotation = Rotation.STATIC
    z: Rotation = Rotation.STATIC
    speed: int = 5

    def __post_init__(self):
        if not 1 <= self.speed <= 10:
            raise ValueError(f"Speed must be 1-10, got {self.speed}")

    # ── axis access ──────────────────────────────────────────────────

    @property
    def data(self) -> Rotation:
        """X-axis: data direction (read/consume)."""
        return self.x

    @property
    def scope(self) -> Rotation:
        """Y-axis: scope (specific/wildcard)."""
        return self.y

    @property
    def transform(self) -> Rotation:
        """Z-axis: transform (weave/unravel)."""
        return self.z

    @property
    def is_stasis(self) -> bool:
        """True when all three axes are STATIC (null state)."""
        return self.x == Rotation.STATIC and self.y == Rotation.STATIC and self.z == Rotation.STATIC

    # ── intent interpretation ────────────────────────────────────────

    @property
    def data_intent(self) -> str:
        """Human-readable intent on the DATA axis."""
        if self.x == Rotation.CW:
            return AXIS_X_CW_INTENT
        if self.x == Rotation.CCW:
            return AXIS_X_CCW_INTENT
        return "null stasis (data)"

    @property
    def scope_intent(self) -> str:
        """Human-readable intent on the SCOPE axis."""
        if self.y == Rotation.CW:
            return AXIS_Y_CW_INTENT
        if self.y == Rotation.CCW:
            return AXIS_Y_CCW_INTENT
        return "default scope"

    @property
    def transform_intent(self) -> str:
        """Human-readable intent on the TRANSFORM axis."""
        if self.z == Rotation.CW:
            return AXIS_Z_CW_INTENT
        if self.z == Rotation.CCW:
            return AXIS_Z_CCW_INTENT
        return "null stasis (transform)"

    @property
    def summary(self) -> str:
        """One-line intent summary."""
        parts = []
        if self.x != Rotation.STATIC:
            parts.append(self.data_intent.split(" / ")[0])
        if self.y != Rotation.STATIC:
            parts.append(self.scope_intent.split(" / ")[0])
        if self.z != Rotation.STATIC:
            parts.append(self.transform_intent.split(" / ")[0])
        if not parts:
            return "NULL STASIS"
        return " · ".join(parts)

    # ── glyph ────────────────────────────────────────────────────────

    def glyph(self) -> str:
        """Compact visual bearing: e.g., '⟳·⟲' for CW-X, STATIC-Y, CCW-Z."""
        return f"{self.x.glyph}{self.y.glyph}{self.z.glyph}"

    def visual(self) -> str:
        """Multi-line visual bearing display."""
        lines = [
            f"     Z",
            f"     │",
            f"  X──┼──Y",
            f"",
            f"  X={self.x.glyph}  Y={self.y.glyph}  Z={self.z.glyph}",
            f"  X: {self.data_intent}",
            f"  Y: {self.scope_intent}",
            f"  Z: {self.transform_intent}",
            f"  speed: {self.speed}/10  [{self.summary}]",
        ]
        return "\n".join(lines)

    # ── mutation ─────────────────────────────────────────────────────

    def with_x(self, rotation: Rotation) -> "Bearing":
        """Return a new Bearing with X-axis set to `rotation`."""
        return Bearing(x=rotation, y=self.y, z=self.z, speed=self.speed)

    def with_y(self, rotation: Rotation) -> "Bearing":
        """Return a new Bearing with Y-axis set to `rotation`."""
        return Bearing(x=self.x, y=rotation, z=self.z, speed=self.speed)

    def with_z(self, rotation: Rotation) -> "Bearing":
        """Return a new Bearing with Z-axis set to `rotation`."""
        return Bearing(x=self.x, y=self.y, z=rotation, speed=self.speed)

    def with_speed(self, speed: int) -> "Bearing":
        """Return a new Bearing with `speed` set."""
        return Bearing(x=self.x, y=self.y, z=self.z, speed=speed)

    def toggle_x(self) -> "Bearing":
        """Flip X-axis CW↔CCW."""
        return Bearing(x=Rotation(-self.x.value), y=self.y, z=self.z, speed=self.speed)

    def toggle_y(self) -> "Bearing":
        """Flip Y-axis CW↔CCW."""
        return Bearing(x=self.x, y=Rotation(-self.y.value), z=self.z, speed=self.speed)

    def toggle_z(self) -> "Bearing":
        """Flip Z-axis CW↔CCW."""
        return Bearing(x=self.x, y=self.y, z=Rotation(-self.z.value), speed=self.speed)

    def compose(self, other: "Bearing") -> "Bearing":
        """Compose two bearings: axes multiply, speed averages."""
        def _compose(a: Rotation, b: Rotation) -> Rotation:
            product = a.value * b.value
            if product == 0:
                return Rotation(a.value + b.value)  # one static → keep the other
            return Rotation(product)  # both active → CW*CCW=CCW, CW*CW=CW, CCW*CCW=CW

        return Bearing(
            x=_compose(self.x, other.x),
            y=_compose(self.y, other.y),
            z=_compose(self.z, other.z),
            speed=max(1, min(10, (self.speed + other.speed) // 2)),
        )

    # ── serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {"x": self.x.value, "y": self.y.value, "z": self.z.value, "speed": self.speed}

    @classmethod
    def from_dict(cls, d: dict) -> "Bearing":
        return cls(
            x=Rotation(d.get("x", 0)),
            y=Rotation(d.get("y", 0)),
            z=Rotation(d.get("z", 0)),
            speed=d.get("speed", 5),
        )

    # ── common factory methods ────────────────────────────────────────

    @classmethod
    def stasis(cls, speed: int = 1) -> "Bearing":
        """NULL STASIS — idle agent."""
        return cls(Rotation.STATIC, Rotation.STATIC, Rotation.STATIC, speed)

    @classmethod
    def observe(cls, speed: int = 5) -> "Bearing":
        """READ a specific target."""
        return cls(Rotation.CW, Rotation.CW, Rotation.STATIC, speed)

    @classmethod
    def observe_broad(cls, speed: int = 5) -> "Bearing":
        """READ with wildcard scope."""
        return cls(Rotation.CW, Rotation.CCW, Rotation.STATIC, speed)

    @classmethod
    def consume(cls, speed: int = 7) -> "Bearing":
        """REMOVE a specific target."""
        return cls(Rotation.CCW, Rotation.CW, Rotation.STATIC, speed)

    @classmethod
    def consume_broad(cls, speed: int = 7) -> "Bearing":
        """REMOVE with wildcard scope."""
        return cls(Rotation.CCW, Rotation.CCW, Rotation.STATIC, speed)

    @classmethod
    def weave(cls, speed: int = 5) -> "Bearing":
        """COMPILE/BUILD a specific pattern."""
        return cls(Rotation.STATIC, Rotation.CW, Rotation.CW, speed)

    @classmethod
    def unravel(cls, speed: int = 5) -> "Bearing":
        """DECOMPILE/ANALYSE broadly."""
        return cls(Rotation.STATIC, Rotation.CCW, Rotation.CCW, speed)

    @classmethod
    def full_send(cls, speed: int = 10) -> "Bearing":
        """All axes CW — full READ + SPECIFIC + WEAVE at max speed."""
        return cls(Rotation.CW, Rotation.CW, Rotation.CW, speed)

    @classmethod
    def dismantle(cls, speed: int = 10) -> "Bearing":
        """All axes CCW — full CONSUME + WILDCARD + UNRAVEL at max speed."""
        return cls(Rotation.CCW, Rotation.CCW, Rotation.CCW, speed)
