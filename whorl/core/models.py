"""
whorl.core.models
─────────────────
Data models for every Whorl module. Restored 2026-08-27 after commit
004dae6 replaced these with ModelEngine (now appended at bottom).

Imported by: scouts, forge, hotseat, tailor, agents/yvette, bridge, cli.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whorl.models")


# ── Enums ─────────────────────────────────────────────────────────────────

class SignalClass(Enum):
    ECONOMIC = "economic"
    SUPPLY_CHAIN = "supply_chain"
    GEOPOLITICAL = "geopolitical"
    REAL_ESTATE = "real_estate"


class Vertical(Enum):
    BANK = "bank"
    RESTAURANT = "restaurant"
    HVAC = "hvac"
    PLUMBER = "plumber"
    REALESTATE = "realestate"
    GENERAL = "general"


class AgentState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    RESPONDING = "responding"
    ERROR = "error"


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class Signal:
    id: str = ""
    timestamp: str = ""
    source: str = ""
    region: str = ""
    signal_class: SignalClass = SignalClass.ECONOMIC
    headline: str = ""
    body: str = ""
    action: str = ""
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Pitch:
    id: str = ""
    timestamp: str = ""
    target: str = ""
    vertical: Vertical = Vertical.GENERAL
    situation: str = ""
    risk: str = ""
    fix: str = ""
    ask: str = ""
    hook: str = ""
    cost: str = ""
    guarantee: str = ""
    raw: str = ""


@dataclass
class HotseatSession:
    id: str = ""
    timestamp: str = ""
    topic: str = ""
    audrey: Optional[str] = None
    claib: Optional[str] = None
    vertical: Optional[str] = None
    score: Optional[float] = None


@dataclass
class QRD:
    id: str = ""
    timestamp: str = ""
    source_id: str = ""
    blink: str = ""
    brief: str = ""
    deep: str = ""
    full: str = ""


@dataclass
class Bearing:
    x: int = 0       # 0=local 1=regional 2=national 3=global
    y: int = 0       # 0=surface 1=analysis 2=synthesis 3=strategy
    z: int = 0       # 0=read-only 1=draft 2=send 3=deploy
    cw: bool = False  # escalate
    ccw: bool = False  # delegate


@dataclass
class AgentRecord:
    id: str = ""
    name: str = ""
    vertical: Vertical = Vertical.GENERAL
    state: AgentState = AgentState.IDLE
    bearing: Bearing = field(default_factory=Bearing)


# ── Model Engine (appended 2026-08-26 — routes tasks to local/remote models)
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    name: str = ""
    provider: str = ""   # e.g., 'puter', 'ollama', 'claude'
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelEngine:
    def __init__(self, default_model: str = "puter-gpt-4o-mini"):
        self.default_model = default_model
        self.registry: Dict[str, ModelConfig] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(ModelConfig(name="puter-gpt-4o-mini", provider="puter"))
        self.register(ModelConfig(name="syntax-local", provider="ollama", max_tokens=2048))

    def register(self, config: ModelConfig) -> None:
        self.registry[config.name] = config
        logger.debug(f"Registered model target: {config.name}")

    def select_target(self, task_type: str = "general") -> ModelConfig:
        if task_type == "code" and "syntax-local" in self.registry:
            return self.registry["syntax-local"]
        return self.registry.get(self.default_model,
                                 ModelConfig(name=self.default_model, provider="puter"))

    def execute(self, prompt: str, task_type: str = "general") -> Dict[str, Any]:
        target = self.select_target(task_type)
        logger.info(f"[Whorl] Routing task '{task_type}' to {target.name} ({target.provider})")
        try:
            response_text = f"Executed prompt via {target.name}"
            return {
                "status": "success",
                "model": target.name,
                "provider": target.provider,
                "output": response_text,
            }
        except Exception as err:
            logger.error(f"[Whorl] Execution error on {target.name}: {err}")
            return {
                "status": "error",
                "model": target.name,
                "error": str(err),
            }


# Singleton engine instance
engine = ModelEngine()
