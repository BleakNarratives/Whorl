"""
whorl.memory.cycle
──────────────────
Summarization for the context drive.

Implements the `summarize_cycle` idea from concept_source:

    def summarize_cycle(conversation_chunk):
        # Every 10 messages, summarize them into 1 message
        # "User discussed terminal game development, mentioned Cheney events"
        # Reduces 10K tokens → 100 tokens

The summarizer tries, in order:
  1. model_spirit.invoke_model()   — any reachable backend (state/groq/remote/local)
  2. Extractive fallback            — deterministic, offline, never deadlocks
"""

from __future__ import annotations
import re
import threading
import time
from typing import Callable, Iterable, Optional

from .tokens import count_tokens


# ─── bounded execution ───────────────────────────────────────────────────

class _Timeout:
    """
    Run a callable in a worker thread with a hard wall-clock limit.

    model_spirit's remote/Groq backends carry 30-60s timeouts of their
    own; the context drive must never block on them, so the whole model
    round-trip is capped here (default 6s). Offline = fast fallback.
    """

    def __init__(self, seconds: float):
        self.seconds = seconds

    def run(self, fn: Callable, *args):
        result: list = []
        error: list = []

        def _target():
            try:
                result.append(fn(*args))
            except Exception as e:  # noqa: BLE001
                error.append(e)

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=self.seconds)
        if t.is_alive():
            raise TimeoutError(f"model call exceeded {self.seconds}s cap")
        if error:
            raise error[0]
        return result[0] if result else None


# ─── Extractive fallback ─────────────────────────────────────────────────

def _extractive_summary(entries, max_chars: int = 400) -> str:
    """
    Deterministic extractive summary: keep topic-leading sentences from
    each entry, deduplicate, and cap the length. Good enough to preserve
    the thread's skeleton when no model is reachable.
    """
    sentences: list[str] = []
    seen: set[str] = set()   # raw-sentence dedupe (prefix-agnostic)

    def _split(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]

    for e in entries:
        content = e.get("content", "") if isinstance(e, dict) else str(e)
        role = e.get("role", "") if isinstance(e, dict) else ""
        prefix = f"{role}: " if role else ""
        for s in _split(content):
            # Skip empty/short fragments; dedupe on the RAW sentence so
            # identical content collapses even when role prefixes differ.
            if len(s) < 24 or s in seen:
                continue
            seen.add(s)
            # Stay under the cap, counting the role prefix AND the
            # truncation ellipsis — never exceed max_chars.
            budget_left = max_chars - sum(len(s2) for s2 in sentences)
            room = budget_left - len(prefix) - 1  # -1 for "…"
            if room <= 0:
                break
            kept = s if len(s) <= room else s[:room].rstrip() + "…"
            sentences.append(prefix + kept)
        if sum(len(s2) for s2 in sentences) >= max_chars:
            break

    if not sentences:
        # Last resort — head/tail of the raw text.
        flat = " ".join(e.get("content", "") if isinstance(e, dict) else str(e)
                        for e in entries)
        return (flat[: max_chars // 2] + " … " + flat[-max_chars // 2:]).strip()

    return " ".join(sentences[:8])


# ─── Summarizer ──────────────────────────────────────────────────────────

class Summarizer:
    """
    Pluggable summarizer. By default routes through model_spirit when a
    backend is reachable, else uses the extractive fallback.

    Usage:
        s = Summarizer()
        s.summarize([{"role": "user", "content": "..."}, ...])
    """

    def __init__(
        self,
        model_invoker: Optional[Callable[[str], str]] = None,
        max_summary_chars: int = 400,
        min_chars_for_model: int = 120,
        model_timeout: float = 6.0,
    ):
        self._invoker = model_invoker
        self.max_summary_chars = max_summary_chars
        self.min_chars_for_model = min_chars_for_model
        self.model_timeout = model_timeout
        self._last_backend: Optional[str] = None

    @property
    def last_backend(self) -> Optional[str]:
        """Which summarizer ran last: 'model' or 'extractive'."""
        return self._last_backend

    # Reachability probe — cached so the drive doesn't re-pay the timeout
    # on every fold. 0 = unknown, 1 = reachable, -1 = unreachable.
    _probe = 0
    _probe_at = 0.0

    def _model_available(self) -> bool:
        """Quick reachability probe through model_spirit, cached 60s."""
        now = time.time()
        if self._probe != 0 and now - self._probe_at < 60:
            return self._probe == 1

        try:
            from whorl.tools.model_spirit import _resolve_mode, _remote_health, _groq_key
            mode = _resolve_mode()
            ok = (
                mode in ("state", "remote") and _Timeout(2.0).run(_remote_health)
            ) or (
                mode == "groq" and bool(_groq_key())
            )
            Summarizer._probe = 1 if ok else -1
        except Exception:
            Summarizer._probe = -1
        Summarizer._probe_at = now
        return Summarizer._probe == 1

    def _invoke_model(self, text: str) -> Optional[str]:
        """Try model_spirit; returns None on any failure (offline-safe)."""
        if self._invoker is not None:
            try:
                out = _Timeout(self.model_timeout).run(self._invoker, text)
                return out if out and not out.startswith(("Model Error", "Remote Error",
                                                           "Groq Error", "Parse Error")) else None
            except Exception:
                return None

        if not self._model_available():
            return None

        try:
            from whorl.tools.model_spirit import invoke_model
            prompt = (
                "Summarize the following agent conversation or text block into a tight, "
                "information-dense summary. Keep names, numbers, decisions, and open threads. "
                f"Max {self.max_summary_chars} characters.\n\n---\n{text[:8000]}"
            )
            out, _meta = _Timeout(self.model_timeout).run(
                invoke_model, prompt, max_tokens=200, temperature=0.2
            )
            if not out or out.startswith(("Model Error", "Remote Error", "Groq Error", "Parse Error")):
                return None
            return out.strip()
        except Exception:
            return None

    def summarize(self, entries) -> str:
        """
        Summarize a list of messages (str or {role, content} dicts).

        Returns the summary string and records which backend produced it.
        """
        flat = " ".join(
            e.get("content", "") if isinstance(e, dict) else str(e)
            for e in entries
        ).strip()

        if not flat:
            self._last_backend = "extractive"
            return "(empty)"

        # Only bother with a model when there's enough to compress meaningfully.
        if len(flat) >= self.min_chars_for_model:
            model_out = self._invoke_model(flat)
            if model_out:
                self._last_backend = "model"
                return model_out[: self.max_summary_chars].strip()

        self._last_backend = "extractive"
        return _extractive_summary(entries, max_chars=self.max_summary_chars)


def summarize_cycle(
    conversation: Iterable,
    every: int = 10,
    summarizer: Optional[Summarizer] = None,
    include_remaining: bool = False,
) -> list[dict]:
    """
    Fold a long conversation into summaries every `every` messages.

    Mirrors the concept stub:

        def summarize_cycle(conversation_chunk):
            # Every 10 messages, summarize them into 1 message
            # Reduces 10K tokens → 100 tokens

    Args:
        conversation: iterable of message dicts or strings.
        every: how many messages per fold.
        summarizer: Summarizer instance (fresh one if None).
        include_remaining: if True, also return the tail that did not fill
                           a full fold (default: drop it — the drive keeps
                           the tail as active context).

    Returns:
        List of {"role": "summary", "content": str, "folded": int, "backend": str}.
    """
    every = max(1, int(every))
    s = summarizer or Summarizer()
    items = list(conversation)
    folds: list[dict] = []

    for i in range(0, len(items) - len(items) % every, every):
        chunk = items[i:i + every]
        folds.append({
            "role": "summary",
            "content": s.summarize(chunk),
            "folded": len(chunk),
            "backend": s.last_backend,
        })

    if include_remaining:
        tail = items[len(items) - len(items) % every:]
        if tail:
            folds.append({
                "role": "summary",
                "content": s.summarize(tail),
                "folded": len(tail),
                "backend": s.last_backend,
            })

    return folds


def tokens_saved(conversation: Iterable, every: int = 10) -> tuple[int, int]:
    """
    Estimate the token reduction of a cycle fold.

    Returns (raw_tokens, folded_tokens).
    """
    items = list(conversation)
    raw = count_tokens(" ".join(
        e.get("content", "") if isinstance(e, dict) else str(e) for e in items
    ))
    folds = summarize_cycle(items, every=every)
    folded = sum(count_tokens(f["content"]) for f in folds)
    return raw, folded
