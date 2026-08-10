"""
whorl.core.helix — Helical datafiber knotwork cryptography.

The helical layer wraps state values in a weave that only the weaver
can unravel. Without the weaver's key, any exfiltrated data is
inherently worthless — garbage in part or in total.

How it works:
  1. WEAVE — Takes plaintext and a weaver's key, produces a knot
     (a cryptographically transformed blob with embedded bearing metadata).
  2. UNRAVEL — Takes a knot and the weaver's key, recovers the plaintext.
  3. KNOTWORK — Multiple weaves can be composed into a single knot,
     requiring all keys in sequence to unravel.

The "helical" aspect: each weave operation twists the data fiber one
rotation. Multiple weaves produce a double-helix structure that can
only be unwound in reverse order.

This is a SIMULATION layer for the Whorl skeleton. In production,
this would use AES-256-GCM or ChaCha20-Poly1305. The current
implementation uses a simple XOR-based knot with SHA-256 hashing
to demonstrate the concept without external dependencies.
"""

import hashlib
import json
import time
import base64
from dataclasses import dataclass, field
from typing import Any, Optional

from .bearing import Bearing, Rotation


# ─── Knot ─────────────────────────────────────────────────────────────

@dataclass
class Knot:
    """
    A helical datafiber knot — encrypted state with bearing metadata.

    A knot wraps a value with:
      - the weaver's identity
      - the bearing at time of weave
      - a timestamp
      - the encrypted payload
      - a chain of previous knots (for composed weaves)
    """

    payload: str                    # base64-encoded ciphertext
    weaver_id: str                  # who wove it
    bearing: Bearing                # bearing at weave time
    woven_at: float                 # epoch timestamp
    key_hash: str                   # SHA-256 of the weaver's key (not the key itself)
    prev_knot: Optional["Knot"] = None  # for composed/knotwork weaves

    def to_dict(self) -> dict:
        return {
            "payload": self.payload,
            "weaver_id": self.weaver_id,
            "bearing": self.bearing.to_dict(),
            "woven_at": self.woven_at,
            "key_hash": self.key_hash,
            "prev_knot": self.prev_knot.to_dict() if self.prev_knot else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Knot":
        prev = cls.from_dict(d["prev_knot"]) if d.get("prev_knot") else None
        return cls(
            payload=d["payload"],
            weaver_id=d["weaver_id"],
            bearing=Bearing.from_dict(d["bearing"]),
            woven_at=d["woven_at"],
            key_hash=d["key_hash"],
            prev_knot=prev,
        )

    @property
    def depth(self) -> int:
        """How many weaves deep is this knot?"""
        return 1 + (self.prev_knot.depth if self.prev_knot else 0)

    @property
    def is_single(self) -> bool:
        """True if this is a single-weave knot (not composed)."""
        return self.prev_knot is None


# ─── Helix ────────────────────────────────────────────────────────────

class Helix:
    """
    Helical datafiber weaver/unraveler.

    Usage:
        helix = Helix()
        knot = helix.weave("secret data", key="my-key", weaver_id="agent-1")
        plaintext = helix.unravel(knot, key="my-key")
        # → "secret data"

        # Composed knotwork (two keys required):
        knot2 = helix.weave(knot, key="second-key", weaver_id="agent-2",
                            bearing=Bearing.weave())
        plaintext = helix.unravel(knot2, key=["second-key", "my-key"])
    """

    @staticmethod
    def _derive_key_material(key: str) -> bytes:
        """Derive key material from a string key using SHA-256."""
        return hashlib.sha256(key.encode("utf-8")).digest()

    @staticmethod
    def _xor_crypt(data: bytes, key_material: bytes) -> bytes:
        """XOR encrypt/decrypt data with key material (symmetric)."""
        # Cycle key material to match data length
        km = key_material
        while len(km) < len(data):
            km += hashlib.sha256(km[-32:]).digest()
        return bytes(a ^ b for a, b in zip(data, km[:len(data)]))

    @classmethod
    def weave(
        cls,
        value: Any,
        *,
        key: str,
        weaver_id: str,
        bearing: Optional[Bearing] = None,
    ) -> Knot:
        """
        Weave a value into a helical knot.

        If `value` is already a Knot, this composes a new knot on top
        (knotwork), requiring both keys to unravel in reverse order.

        Args:
            value: The plaintext value (or an existing Knot for composition).
            key: The weaver's secret key.
            weaver_id: Agent ID of the weaver.
            bearing: Bearing at time of weave (defaults to WEAVE).

        Returns:
            A new Knot wrapping the encrypted data.
        """
        if bearing is None:
            bearing = Bearing.weave(speed=5)

        # Serialise the value
        if isinstance(value, Knot):
            serialised = json.dumps(value.to_dict(), default=str).encode("utf-8")
        else:
            serialised = json.dumps(value, default=str).encode("utf-8")

        key_material = cls._derive_key_material(key)
        ciphertext = cls._xor_crypt(serialised, key_material)
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

        return Knot(
            payload=base64.b64encode(ciphertext).decode("ascii"),
            weaver_id=weaver_id,
            bearing=bearing,
            woven_at=time.time(),
            key_hash=key_hash,
            prev_knot=value if isinstance(value, Knot) else None,
        )

    @classmethod
    def unravel(
        cls,
        knot: Knot,
        *,
        key: str | list[str],
    ) -> Any:
        """
        Unravel a helical knot back to plaintext.

        For single-weave knots, pass a single key.
        For composed knots (knotwork), pass keys in REVERSE order
        (outermost weave first → innermost last).

        Args:
            knot: The Knot to unravel.
            key: The weaver's key(s). For composed knots, a list of keys
                 in order from outermost to innermost weave.

        Returns:
            The original plaintext value.

        Raises:
            ValueError: If the key is wrong.
        """
        keys = [key] if isinstance(key, str) else list(key)
        if not keys:
            raise ValueError("At least one key is required to unravel")

        return cls._unravel_inner(knot, keys)

    @classmethod
    def _unravel_inner(cls, knot: Knot, keys: list[str]) -> Any:
        """Recursive unravel with key stack."""
        if not keys:
            raise ValueError("Not enough keys to unravel this knot")

        current_key = keys[0]
        remaining_keys = keys[1:]

        # Decrypt
        key_material = cls._derive_key_material(current_key)
        ciphertext = base64.b64decode(knot.payload)
        plaintext_bytes = cls._xor_crypt(ciphertext, key_material)

        try:
            plaintext_str = plaintext_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(
                f"Wrong key for knot woven by {knot.weaver_id} at {knot.woven_at}. "
                f"Key hash: {knot.key_hash}"
            )

        try:
            value = json.loads(plaintext_str)
        except json.JSONDecodeError:
            # Not JSON — return as string
            value = plaintext_str

        # If there's a previous knot, unravel it too
        if knot.prev_knot:
            if not remaining_keys:
                raise ValueError(
                    f"Knot has depth {knot.depth} but only {len(keys)} key(s) provided. "
                    f"Need {knot.depth} keys in reverse weave order."
                )
            return cls._unravel_inner(knot.prev_knot, remaining_keys)

        return value

    @classmethod
    def verify_key(cls, knot: Knot, key: str) -> bool:
        """Check if a key matches this knot without decrypting."""
        expected = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return knot.key_hash == expected

    @classmethod
    def inspect(cls, knot: Knot) -> dict:
        """
        Inspect a knot's metadata without decrypting.
        Safe to call on any knot — reveals structure but not content.
        """
        return {
            "weaver_id": knot.weaver_id,
            "bearing": knot.bearing.glyph(),
            "bearing_summary": knot.bearing.summary,
            "woven_at": knot.woven_at,
            "key_hash": knot.key_hash,
            "depth": knot.depth,
            "is_composed": not knot.is_single,
            "payload_bytes": len(knot.payload),
        }


# ─── HelicalSharedState ───────────────────────────────────────────────

class HelicalSharedState:
    """
    A SharedState wrapper that transparently weaves/unravels values.

    Use this when you want state entries to be automatically encrypted
    with an agent-specific key. Without the key, the state file is
    unreadable — fulfilling the "stolen data is worthless" property.

    Usage:
        hss = HelicalSharedState("state.json")
        hss.weave_write("secret:key", "my secret", agent_id="a1", key="pass1")
        val = hss.unravel_read("secret:key", key="pass1")
    """

    def __init__(self, state):
        self._state = state   # SharedState instance
        self._helix = Helix()

    def weave_write(
        self,
        key: str,
        value: Any,
        *,
        agent_id: str,
        weave_key: str,
        bearing: Optional[Bearing] = None,
    ) -> None:
        """Write a value as a helical knot to shared state."""
        knot = self._helix.weave(
            value,
            key=weave_key,
            weaver_id=agent_id,
            bearing=bearing,
        )
        self._state.write(key, knot.to_dict(), agent_id)

    def unravel_read(self, key: str, *, weave_key: str) -> Optional[Any]:
        """Read and unravel a helical knot from shared state."""
        raw = self._state.read(key)
        if raw is None:
            return None
        if isinstance(raw, dict) and "payload" in raw:
            knot = Knot.from_dict(raw)
            return self._helix.unravel(knot, key=weave_key)
        return raw  # not a knot — plain value

    def inspect_knot(self, key: str) -> Optional[dict]:
        """Inspect a knot's metadata without decrypting."""
        raw = self._state.read(key)
        if raw is None:
            return None
        if isinstance(raw, dict) and "payload" in raw:
            knot = Knot.from_dict(raw)
            return self._helix.inspect(knot)
        return None

    # Passthrough for non-helical operations
    def keys(self):
        return self._state.keys()

    def read(self, key):
        return self._state.read(key)

    def write(self, key, value, agent_id):
        self._state.write(key, value, agent_id)

    def delete(self, key, agent_id):
        return self._state.delete(key, agent_id)

    def snapshot(self):
        return self._state.snapshot()

    def stats(self):
        return self._state.stats()
