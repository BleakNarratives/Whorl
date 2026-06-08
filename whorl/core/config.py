"""
whorl.core.config
─────────────────
Reads ~/.whorl/config.toml and exposes a frozen WhorlConfig object.
Creates defaults on first run.
"""

from __future__ import annotations
import os
import toml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any

WHORL_DIR     = Path(os.environ.get("WHORL_HOME", "~/.whorl")).expanduser()
CONFIG_PATH   = WHORL_DIR / "config.toml"
DB_PATH       = WHORL_DIR / "whorl.db"
LOG_PATH      = WHORL_DIR / "whorl.log"

DEFAULTS: Dict[str, Any] = {
    "whorl": {
        "version":   "0.1.0",
        "log_level": "INFO",
    },
    "ollama": {
        "url":            "http://localhost:11434/api/generate",
        "model_audrey":   "zane-preacher:latest",
        "model_claib":    "llama3.2:1b",
        "model_vertical": "deepseek-coder:latest",
        "model_forge":    "llama3.2:1b",
        "model_tailor":   "deepseek-coder:latest",
    },
    "nostr": {
        "relay":      "wss://relay.damus.io",
        "keys_path":  str(WHORL_DIR / "nostr_keys.json"),
    },
    "scouts": {
        "feeds":      [],
        "interval":   3600,          # seconds between sweeps
    },
    "forge": {
        "output_dir": str(WHORL_DIR / "pitches"),
    },
    "agents": {
        "registry":   str(WHORL_DIR / "agents.json"),
    },
}


@dataclass
class WhorlConfig:
    raw: Dict[str, Any] = field(default_factory=dict)

    # Flattened accessors
    @property
    def ollama_url(self) -> str:
        return self.raw["ollama"]["url"]

    @property
    def model(self) -> Dict[str, str]:
        return self.raw["ollama"]

    @property
    def nostr_relay(self) -> str:
        return self.raw["nostr"]["relay"]

    @property
    def nostr_keys_path(self) -> str:
        return self.raw["nostr"]["keys_path"]

    @property
    def scout_feeds(self):
        return self.raw["scouts"]["feeds"]

    @property
    def forge_output_dir(self) -> Path:
        return Path(self.raw["forge"]["output_dir"])

    def get(self, *keys, default=None):
        d = self.raw
        for k in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(k, default)
        return d


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load() -> WhorlConfig:
    """Load config, creating defaults if missing."""
    WHORL_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(toml.dumps(DEFAULTS))
        print(f"[whorl] Created default config at {CONFIG_PATH}")

    user_config = toml.loads(CONFIG_PATH.read_text())
    merged = _deep_merge(DEFAULTS, user_config)
    return WhorlConfig(raw=merged)


# Module-level singleton
_cfg: WhorlConfig | None = None

def cfg() -> WhorlConfig:
    global _cfg
    if _cfg is None:
        _cfg = load()
    return _cfg

# ── API key loader ─────────────────────────────────────────────────────────

def load_api_keys() -> dict:
    secrets_path = WHORL_DIR / "secrets.toml"
    keys = {}
    if secrets_path.exists():
        import toml
        keys = toml.loads(secrets_path.read_text()).get("api_keys", {})
    for name in ["OPENAI", "GROQ", "MISTRAL", "GEMINI", "ANTHROPIC"]:
        env_val = os.getenv(f"{name}_API_KEY")
        if env_val:
            keys[name.lower()] = env_val
    return keys

# ── Unified key loading (delegated to vault) ───────────────────────────────

def load_api_keys() -> dict:
    """Delegate to vault module for unified key loading."""
    # Lazy import to avoid circular deps
    from . import vault
    return vault.load_api_keys()

# ── Unified key loading (delegated to vault) ───────────────────────────────

def load_api_keys() -> dict:
    """Delegate to vault module for unified key loading."""
    # Lazy import to avoid circular deps
    from . import vault
    return vault.load_api_keys()
