"""
whorl.core.state — Persistent shared state store.

All Whorl agents share a single state space. State is versioned
and persisted to disk as JSON. Agents read/write through bearing-based
permissions:

  - READ bearing (+X CW)  → can read state
  - CONSUME bearing (+X CCW) → can write/delete state
  - WEAVE bearing (+Z CW)  → can create new state keys
  - UNRAVEL bearing (+Z CCW) → can inspect state topology

The state store is intentionally simple: a flat key-value namespace
with metadata so agents can discover what exists without scanning.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .bearing import Bearing, Rotation


# ─── Security ────────────────────────────────────────────────────────

ALLOWED_SPIRIT_KEYS = {'glyph', 'persona', 'is_aware', 'synthetic_memory', 'spirit_source', 'spirit_version', 'spirit_capability'}

def validate_meta(meta: dict) -> dict:
    if not isinstance(meta, dict):
        return {}
    return {k: v for k, v in meta.items() if k in ALLOWED_SPIRIT_KEYS}


# ─── State Record ─────────────────────────────────────────────────────

@dataclass
class StateRecord:
    """A single entry in shared state."""
    key: str
    value: Any
    created_by: str       # agent ID
    created_at: float     # epoch timestamp
    version: int = 1
    updated_by: Optional[str] = None
    updated_at: Optional[float] = None
    spirit_metadata: dict = field(default_factory=dict) # NEW: The binding

    def update(self, value: Any, agent_id: str, avatar_meta: dict = None) -> None:
        self.value = value
        self.version += 1
        self.updated_by = agent_id
        self.updated_at = time.time()
        if avatar_meta:
            self.spirit_metadata.update(validate_meta(avatar_meta))

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "version": self.version,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at,
            "spirit_metadata": self.spirit_metadata, # Added
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StateRecord":
        return cls(
            key=d["key"],
            value=d["value"],
            created_by=d.get("created_by", "unknown"),
            created_at=d.get("created_at", time.time()),
            version=d.get("version", 1),
            updated_by=d.get("updated_by"),
            updated_at=d.get("updated_at"),
            spirit_metadata=d.get("spirit_metadata", {}), # Added
        )


# ─── Shared State ─────────────────────────────────────────────────────

class SharedState:
    """
    Persistent shared state for all agents in a Loomy runtime.

    Agents interact with state through bearing-constrained operations.
    State is versioned and persisted as a JSON file.

    Usage:
        state = SharedState("/path/to/state.json")
        state.write("market:btc", 42300.50, agent_id="scout-1")
        val = state.read("market:btc")
        state.keys_starting_with("market:")  # discover
    """

    def __init__(self, filepath: str = "~/.whorl/state.json"):
        # Jail the path to ~/.whorl/
        root_dir = os.path.expanduser("~/.whorl")
        full_path = os.path.expanduser(filepath)

        # Ensure the path is within the jail. Use a separator-aware check so
        # a sibling like ~/.whorl-evil/ cannot pass the prefix test.
        within = full_path == root_dir or full_path.startswith(root_dir + os.sep)
        if not within:
            raise PermissionError(f"Access denied: {full_path} is outside the allowed root {root_dir}")

        self.filepath = full_path
        self._store: dict[str, StateRecord] = {}
        self._load()

    # ── persistence ───────────────────────────────────────────────────

    def _load(self) -> None:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    raw = json.load(f)
                self._store = {
                    k: StateRecord.from_dict(v) for k, v in raw.items()
                }
            except (json.JSONDecodeError, KeyError):
                self._store = {}

    def _save(self) -> None:
        dirname = os.path.dirname(self.filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._store.items()},
                f,
                indent=2,
                default=str,
            )

    # ── CRUD ──────────────────────────────────────────────────────────

    def read(self, key: str) -> Optional[Any]:
        """Read a value from shared state. Returns None if absent."""
        rec = self._store.get(key)
        return rec.value if rec else None

    def read_record(self, key: str) -> Optional[StateRecord]:
        """Read the full record (with metadata)."""
        return self._store.get(key)

    def write(self, key: str, value: Any, agent_id: str, avatar_meta: dict = None) -> None:
        """Write or update a value. Overwrites if key exists."""
        validated_meta = validate_meta(avatar_meta) if avatar_meta else {}
        if key in self._store:
            self._store[key].update(value, agent_id, validated_meta)
        else:
            self._store[key] = StateRecord(
                key=key,
                value=value,
                created_by=agent_id,
                created_at=time.time(),
                spirit_metadata=validated_meta,
            )
        self._save()

    def delete(self, key: str, agent_id: str) -> bool:
        """
        Delete a key from shared state.
        Returns True if the key existed and was deleted.
        Requires CONSUME bearing (the agent must declare intent to remove).
        """
        if key in self._store:
            del self._store[key]
            self._save()
            return True
        return False

    # ── discovery ─────────────────────────────────────────────────────

    def keys(self) -> list[str]:
        """All keys in the state store."""
        return sorted(self._store.keys())

    def keys_starting_with(self, prefix: str) -> list[str]:
        """Keys matching a prefix (namespace discovery)."""
        return sorted(k for k in self._store if k.startswith(prefix))

    def keys_containing(self, substr: str) -> list[str]:
        """Keys containing a substring."""
        return sorted(k for k in self._store if substr in k)

    def by_agent(self, agent_id: str) -> list[StateRecord]:
        """All records created or last updated by a given agent."""
        return [
            r for r in self._store.values()
            if r.created_by == agent_id or r.updated_by == agent_id
        ]

    # ── query ─────────────────────────────────────────────────────────

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)

    def snapshot(self) -> dict[str, Any]:
        """Return a plain dict snapshot of current state (values only)."""
        return {k: v.value for k, v in self._store.items()}

    def stats(self) -> dict:
        """Return state store statistics."""
        if not self._store:
            return {"keys": 0, "oldest_key": None, "newest_key": None}

        oldest = min(self._store.values(), key=lambda r: r.created_at)
        newest = max(self._store.values(), key=lambda r: r.updated_at or r.created_at)
        return {
            "keys": len(self._store),
            "oldest_key": oldest.key,
            "newest_key": newest.key,
            "total_versions": sum(r.version for r in self._store.values()),
        }
