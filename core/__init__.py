"""
Whorl Core — Agent runtime, rotational bearing, persistent shared state, and Loomy.

The core is intentionally minimal. Agents boot with 2-3 parameters
and handle everything from there through their own observation loop.
"""

from .bearing import Bearing, Axis, Rotation
from .state   import SharedState, StateRecord
from .agent   import Agent
from .runtime import Loomy

__all__ = [
    "Bearing", "Axis", "Rotation",
    "SharedState", "StateRecord",
    "Agent",
    "Loomy",
]
