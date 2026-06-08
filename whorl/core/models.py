"""
whorl.core.models
─────────────────
Shared dataclasses. Every module imports from here.
No external deps — stdlib only.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ──────────────────────────────────────────────────────────────────

class Vertical(str, Enum):
    BANK        = "bank"
    RESTAURANT  = "restaurant"
    HVAC        = "hvac"
    PLUMBER     = "plumber"
    REALESTATE  = "realestate"
    RETAIL      = "retail"
    GENERAL     = "general"


class SignalClass(str, Enum):
    SUPPLY_CHAIN    = "supply_chain"
    REAL_ESTATE     = "real_estate"
    ECONOMIC        = "economic"
    GEOPOLITICAL    = "geopolitical"
    LOCAL           = "local"


class AgentState(str, Enum):
    IDLE      = "idle"
    LISTENING = "listening"
    THINKING  = "thinking"
    ACTING    = "acting"
    ERROR     = "error"


# ── Bearing (Whorl permission vectors) ─────────────────────────────────────

@dataclass
class Bearing:
    """
    Capability vector for an agent.
    Replaces boolean permission flags with directional constraints.

    Axes:
      x   — lateral scope     (0=local, 1=regional, 2=national, 3=global)
      y   — depth             (0=surface, 1=analysis, 2=synthesis, 3=strategy)
      z   — execution power   (0=read-only, 1=draft, 2=send, 3=deploy)
      cw  — can escalate      (True = may hand off to higher agent)
      ccw — can delegate      (True = may spawn sub-agents)
    """
    x:   int  = 0
    y:   int  = 0
    z:   int  = 0
    cw:  bool = False
    ccw: bool = False

    def can_execute(self) -> bool:
        return self.z >= 2

    def can_deploy(self) -> bool:
        return self.z >= 3


# ── Core data units ────────────────────────────────────────────────────────

@dataclass
class Signal:
    """Raw intel from a scout."""
    id:          str
    timestamp:   str
    source:      str
    region:      str
    signal_class: SignalClass
    headline:    str
    body:        str
    action:      str
    verified:    bool              = False
    metadata:    Dict[str, Any]   = field(default_factory=dict)


@dataclass
class Pitch:
    """Forge output — a vertical-specific sales document."""
    id:        str
    timestamp: str
    target:    str
    vertical:  Vertical
    situation: str
    risk:      str
    fix:       str
    ask:       str
    hook:      str
    cost:      str
    guarantee: str
    raw:       str                 = ""
    metadata:  Dict[str, Any]     = field(default_factory=dict)


@dataclass
class HotseatSession:
    """One Hotseat run — three voices, one topic."""
    id:        str
    timestamp: str
    topic:     str
    audrey:    str                 = ""   # the auditor
    claib:     str                 = ""   # the visionary
    vertical:  str                 = ""   # the verdict
    score:     Optional[float]     = None


@dataclass
class QRD:
    """Quick Rundown — tiered summary from the Tailor."""
    id:          str
    timestamp:   str
    source_id:   str              # FK to whatever was summarized
    blink:       str              # 30-second version
    brief:       str              # 2-minute version
    deep:        str              # 10-minute version
    full:        str              # complete output


@dataclass
class AgentRecord:
    """Registry entry for a deployed agent."""
    id:       str
    name:     str
    vertical: Vertical
    state:    AgentState          = AgentState.IDLE
    bearing:  Bearing             = field(default_factory=Bearing)
    metadata: Dict[str, Any]      = field(default_factory=dict)
