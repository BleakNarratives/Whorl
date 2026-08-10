"""
whorl.memory.gate
─────────────────
THE WEIGHT-VEST GATE.

The machine already knows how to compress your garbage — the TokenStretcher
folds it to its floor density in milliseconds, with no model and no network.
This gate holds that floor up as a mirror and refuses the pipe until you
match it. The friction is the point: you have to compress *before* you're
allowed to spend a token on a model.

  FLOOR    the deterministic LOSSLESS trim. Same input → same floor,
           every time. No randomness, no model drift, no way to game it
           by retrying. Only verbal fat is removed — every sentence
           survives, so concise writing is never punished.
  VERDICT  PASS if you are within `tolerance` of the floor, or if the
           machine cannot compress you (you are already dense).
  MIRROR   on a BLOCK, the gate shows you exactly which words it dropped,
           plus the floor itself as the suggested rewrite.
  CHAOS    optional tightening: if the persona registry reports a high
           chaos index (frantic, unfocused), the tolerance tightens and
           the vest bites harder. Offline/absent registry = neutral.
  MEMORY   exceptions the operator accepts with --learn are remembered,
           so the gate never nags about the same prompt twice.

Exit codes (CLI): 0 = passed, 3 = blocked (pipe cut).
"""

from __future__ import annotations
import hashlib
import os
import re
import time
from typing import Any, Optional

from .tokens import count_tokens


# ─── the floor ────────────────────────────────────────────────────────────

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "your", "from", "have",
    "will", "would", "into", "about", "what", "when", "then", "there",
    "some", "very", "just", "should", "could", "also", "than", "them",
}


# Verbal fat — words people pay for that the machine wouldn't. Removing
# these is safe: they hedge, pad, or signal uncertainty without carrying
# load. This is what makes the floor able to bite on run-on prose that
# sentence-level extraction alone would wave through.
#
# Tradeoff: "so" and "well" can occasionally be structural ("so that X").
# We accept that risk — a weight vest that never bites is a scarf.
_FILLER = {
    "basically", "actually", "maybe", "perhaps", "possibly", "probably",
    "literally", "really", "just", "like", "kind", "sort", "potentially",
    "so", "well", "honestly",
}


def _strip_filler(text: str) -> str:
    """Deterministic removal of hedge/padding words, then whitespace
    collapse. Never reorders, never rewrites — only deletes fat."""
    kept = [
        w for w in text.split()
        if w.lower().strip(".,;:!?()'") not in _FILLER
    ]
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def fold_to_floor(text: str) -> str:
    """
    The machine's best LOSSLESS compression of `text`: verbal fat removed,
    nothing else touched.

    Deliberately NOT the TokenStretcher's extractive fold: sentence-level
    extraction drops short sentences, which would punish concise writing
    (a terse factual sentence like "Fed holds rates." would vanish, and
    no amount of rewriting could recover it). The gate's floor only trims
    words the machine wouldn't have paid for — hedge words, padding,
    throat-clearing — and leaves every sentence intact. Deterministic,
    offline, always the same for the same input, never information-losing.
    """
    return _strip_filler(text)


def dropped_signal(original: str, floor: str, limit: int = 8) -> list[str]:
    """
    The words the machine dropped, ranked. These are the words you paid
    for and the floor decided weren't load-bearing.
    """
    def _words(t: str) -> list[str]:
        return [w for w in re.findall(r"[a-z0-9']{4,}", t.lower())
                if w not in _STOPWORDS]

    dropped = []
    counts: dict[str, int] = {}
    for w in _words(original):
        if w not in set(_words(floor)):
            counts[w] = counts.get(w, 0) + 1
    dropped = sorted(counts, key=lambda w: (-counts[w], w))
    return dropped[:limit]


def evaluate(
    text: str,
    tolerance: float = 0.15,
    chaos: Optional[float] = None,
) -> dict[str, Any]:
    """
    Run a prompt through the gate.

    Args:
        text: the prompt to evaluate.
        tolerance: how much slack above the floor is allowed (0.15 = you
                   may be at most 15% fatter than the machine's fold).
        max_chars: floor fold cap.
        chaos: optional 0..1 chaos index. High chaos tightens the gate:
               effective_tolerance = tolerance * (1.0 - 0.5 * chaos).

    Returns:
        {
          "accepted": bool,
          "original_tokens", "floor_tokens": int,
          "density": floor/original (0..1, lower = more compressible),
          "slack": original/floor (1.0 = exactly matched the machine),
          "tolerance_used": float,
          "suggested": str,        # the floor — your mirror
          "dropped_words": [str],
          "chaos": float | None,
          "backend": "extractive",  # deterministic by construction
          "already_dense": bool,    # machine couldn't compress you
        }
    """
    text = text.strip()
    if not text:
        return {
            "accepted": False,
            "original_tokens": 0,
            "floor_tokens": 0,
            "density": 0.0,
            "slack": 0.0,
            "tolerance_used": tolerance,
            "suggested": "",
            "dropped_words": [],
            "chaos": chaos,
            "backend": "extractive",
            "already_dense": False,
            "reason": "empty prompt",
        }

    floor = fold_to_floor(text)
    original_tokens = count_tokens(text)
    floor_tokens = count_tokens(floor)

    # Everything was fat — no signal survives the trim.
    if floor_tokens == 0:
        return {
            "accepted": False,
            "original_tokens": original_tokens,
            "floor_tokens": 0,
            "density": 0.0,
            "slack": float("inf"),
            "tolerance_used": tolerance,
            "suggested": "",
            "dropped_words": dropped_signal(text, ""),
            "chaos": chaos,
            "backend": "extractive",
            "already_dense": False,
            "reason": "no signal — every word was filler",
        }

    # The machine could not compress you — you are already dense.
    if floor_tokens >= original_tokens:
        return {
            "accepted": True,
            "original_tokens": original_tokens,
            "floor_tokens": floor_tokens,
            "density": 1.0,
            "slack": 1.0,
            "tolerance_used": tolerance,
            "suggested": floor,
            "dropped_words": [],
            "chaos": chaos,
            "backend": "extractive",
            "already_dense": True,
            "reason": "already at machine density",
        }

    # Chaos tightens the vest. 0.5 max bite at chaos == 1.
    effective = tolerance
    if chaos is not None:
        effective = tolerance * max(0.25, 1.0 - 0.5 * min(1.0, max(0.0, chaos)))

    slack = original_tokens / floor_tokens
    accepted = slack <= (1.0 + effective)

    return {
        "accepted": accepted,
        "original_tokens": original_tokens,
        "floor_tokens": floor_tokens,
        "density": round(floor_tokens / original_tokens, 3),
        "slack": round(slack, 2),
        "tolerance_used": round(effective, 3),
        "suggested": floor,
        "dropped_words": dropped_signal(text, floor),
        "chaos": chaos,
        "backend": "extractive",
        "already_dense": False,
        "reason": "within tolerance" if accepted else "above the floor",
    }


# ─── chaos gate (feature-detected, never a hard dependency) ───────────────

def chaos_index() -> Optional[float]:
    """
    A 0..1 chaos/volatility index from the persona registry, or None when
    no registry is reachable. Feature-detected so an absent or broken
    persona store just disables the chaos gate instead of failing it.
    """
    try:
        import sys
        root_base = os.path.expanduser("~/RootBase")
        added = False
        if os.path.isdir(root_base) and root_base not in sys.path:
            sys.path.insert(0, root_base)
            added = True
        try:
            from persona_registry import get_persona  # noqa: F401 — feature-detected

            # Try the known personas; any temperature-like field qualifies.
            for name in ("mike", "default", "operator"):
                try:
                    p = get_persona(name)
                except Exception:
                    continue
                for attr in ("temperature", "chaos", "volatility", "heat"):
                    val = getattr(p, attr, None)
                    if isinstance(val, (int, float)):
                        return min(1.0, max(0.0, float(val)))
            return None
        finally:
            # Undo the sys.path mutation — don't leak the probe into the
            # caller's import environment.
            if added:
                try:
                    sys.path.remove(root_base)
                except ValueError:
                    pass
    except Exception:
        return None


# ─── learned exceptions ───────────────────────────────────────────────────

def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


class GateMemory:
    """
    Remembered exceptions, stored in SharedState under `gate:exceptions`.
    The gate consults this before blocking: a prompt the operator already
    accepted with --learn passes silently.
    """

    def __init__(self, state=None):
        self.state = state

    def is_learned(self, text: str) -> bool:
        if self.state is None:
            return False
        rec = self.state.read("gate:exceptions")
        return isinstance(rec, dict) and _fingerprint(text) in rec

    def learn(self, text: str, tolerance: float) -> None:
        if self.state is None:
            return
        rec = self.state.read("gate:exceptions") or {}
        rec[_fingerprint(text)] = {
            "learned_at": time.time(),
            "tolerance_used": tolerance,
        }
        self.state.write("gate:exceptions", rec, "whorl.memory.gate")


# ─── the full gate pass ───────────────────────────────────────────────────

def gate_pass(
    text: str,
    *,
    tolerance: float = 0.15,
    use_chaos: bool = True,
    state=None,
    learn: bool = False,
) -> dict[str, Any]:
    """
    The complete gate pipeline: learned-exception check → chaos read →
    evaluate → (optionally) learn.

    Returns the evaluate() dict plus "learned": bool.
    """
    memory = GateMemory(state)
    result = evaluate(text, tolerance=tolerance,
                      chaos=chaos_index() if use_chaos else None)

    if memory.is_learned(text):
        result["accepted"] = True
        result["learned"] = True
        result["reason"] = "previously accepted (learned exception)"
        return result
    result["learned"] = False

    if learn and result["accepted"]:
        memory.learn(text, result["tolerance_used"])
        result["reason"] = "within tolerance (now learned)"
    return result
