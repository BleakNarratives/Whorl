"""whorl.core — shared foundation: models, config, database, key vault.

Re-exports the public surface so `from whorl.core import Signal` and
`from whorl.core import cfg` work without naming the submodule.
"""

from .config import WhorlConfig, cfg, load, load_api_keys
from .db import connect, count, fetch, insert, migrate
from .models import (
    AgentRecord,
    AgentState,
    Bearing,
    HotseatSession,
    Pitch,
    Signal,
    SignalClass,
    Vertical,
)
from .vault import load_api_keys as load_vault_keys

__all__ = [
    "AgentRecord",
    "AgentState",
    "Bearing",
    "HotseatSession",
    "Pitch",
    "Signal",
    "SignalClass",
    "Vertical",
    "WhorlConfig",
    "cfg",
    "connect",
    "count",
    "fetch",
    "insert",
    "load",
    "load_api_keys",
    "load_vault_keys",
    "migrate",
]
