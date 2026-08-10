"""
whorl.memory.tokens
───────────────────
Token estimation without a tokenizer dependency.

The concept stub called `count_tokens(message)` without ever defining it.
This is that function — a hybrid estimator that is stable across
languages and degrades to a character-based bound for long inputs.

Why hybrid: word-count alone underestimates dense code, character-count
alone overestimates prose. Blending both and taking the ceiling keeps the
estimate conservative (we prefer to compress a little early rather than
overflow the context window).
"""

from __future__ import annotations


def count_tokens(text: str) -> int:
    """
    Estimate the token count of a string.

    Uses a hybrid of word and character estimates:
      words       = len(text.split())
      chars       = len(text)
      estimate    = max(words, ceil(chars / 4))

    For non-string values the caller is expected to str() them first;
    this function raises on anything else so misuse is loud.
    """
    if not isinstance(text, str):
        raise TypeError(f"count_tokens expects str, got {type(text).__name__}")

    if not text:
        return 0

    words = len(text.split())
    chars = len(text)

    # ceil(chars / 4) without importing math
    char_est = (chars + 3) // 4
    return max(words, char_est)


def estimate_tokens(entries) -> int:
    """
    Count tokens across an iterable of str (or message dicts).

    Accepts either raw strings or {"role": ..., "content": ...} dicts
    (the standard message shape used by the drive).
    """
    total = 0
    for e in entries:
        if isinstance(e, dict):
            content = e.get("content", "")
            # Include the role marker in the estimate — it costs tokens too.
            total += count_tokens(str(e.get("role", "")) + " " + str(content))
        else:
            total += count_tokens(str(e))
    return total
