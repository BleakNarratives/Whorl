"""
whorl.memory.stretcher
──────────────────────
The TokenStretcher — keeps active context under a hard token budget.

Builds out `concept_source/concept_token_stretcher.py`, which was pseudocode:

    class TokenStretcher:
        def __init__(self, model, max_context=8000):
            self.model = model
            self.hard_limit = max_context
            self.active_tokens = 0
            self.external_memory = VectorDatabase()   # <-- undefined

        def add_message(self, message):
            tokens = count_tokens(message)
            if self.active_tokens + tokens > self.hard_limit:
                self.compress_oldest()
            self.active_tokens += tokens
            self.messages.append(message)             # <-- never initialized

The external "vector database" is SharedState (whorl.core.state) — a
persistent, versioned JSON store that doubles as the archive. Summaries
are produced by Summarizer (model_spirit when reachable, extractive
fallback offline).
"""

from __future__ import annotations
import time
from typing import Any, Optional

from .tokens import count_tokens, estimate_tokens
from .cycle import Summarizer


def _msg(content: str, role: str = "user") -> dict:
    return {"role": role, "content": content}


class TokenStretcher:
    """
    A sliding context window with external compression.

    Usage:
        s = TokenStretcher(max_context=2000)
        s.add_message("hello")
        s.add_message({"role": "user", "content": "what's the plan?"})
        active = s.context()          # always within budget
        archived = s.archive()        # what got pushed out + summaries
        s.save()                      # persist to SharedState
    """

    def __init__(
        self,
        max_context: int = 8000,
        state=None,
        *,
        name: str = "default",
        summarizer: Optional[Summarizer] = None,
        compress_fraction: float = 0.2,
    ):
        self.max_context = max_context
        self.state = state
        self.name = name
        self.summarizer = summarizer or Summarizer()
        self.compress_fraction = compress_fraction

        self.messages: list[dict] = []
        self.archived: list[dict] = []       # rolled-out messages
        self.summaries: list[dict] = []      # folded summaries
        self.active_tokens = 0

    # ── ingestion ─────────────────────────────────────────────────────

    def add_message(self, message, role: str = "user") -> int:
        """
        Add a message (str or dict). If the budget would be exceeded,
        compress the oldest fifth first. Returns the new active token count.
        """
        if isinstance(message, str):
            message = _msg(message, role)
        elif not isinstance(message, dict) or "content" not in message:
            raise ValueError("message must be a str or {'role','content'} dict")

        tokens = count_tokens(str(message.get("content", "")))

        guard = 0
        while self.active_tokens + tokens > self.max_context and len(self.messages) > 1:
            before = self.active_tokens
            self.compress_oldest()
            guard += 1
            # Guarantee progress: if a fold did not actually shrink the
            # budget (summary ≈ original on tiny folds), drop raw instead
            # of looping forever.
            if self.active_tokens >= before and guard > 1:
                self._force_drop_oldest()
            if guard > 32:
                break

        self.messages.append(message)
        self.active_tokens += tokens
        return self.active_tokens

    # ── compression ───────────────────────────────────────────────────

    def compress_oldest(self) -> dict:
        """
        Take the oldest `compress_fraction` of messages, summarize them,
        move the raw messages to `archived`, and prepend the summary.
        Returns the summary dict.
        """
        n = max(1, int(len(self.messages) * self.compress_fraction))
        old = self.messages[:n]
        rest = self.messages[n:]

        summary_text = self.summarizer.summarize(old)

        summary = {
            "role": "summary",
            "content": summary_text,
            "folded": len(old),
            "backend": self.summarizer.last_backend,
            "compressed_at": time.time(),
        }

        self.archived.extend(old)
        self.summaries.append(summary)
        self.messages = [summary] + rest
        self.active_tokens = estimate_tokens(self.messages)
        return summary

    def _force_drop_oldest(self) -> None:
        """Hard guarantee of progress: drop the oldest raw message, marking
        it in the archive so nothing is silently lost."""
        if not self.messages:
            return
        dropped = self.messages.pop(0)
        dropped = dict(dropped)
        dropped["dropped"] = True
        self.archived.append(dropped)
        self.active_tokens = estimate_tokens(self.messages)

    # ── accessors ─────────────────────────────────────────────────────

    def context(self) -> list[dict]:
        """The active context (within budget)."""
        return list(self.messages)

    def archive(self) -> list[dict]:
        """Raw messages that were pushed out by compression."""
        return list(self.archived)

    def summary_log(self) -> list[dict]:
        """All folds that have been created."""
        return list(self.summaries)

    def usage(self) -> dict:
        """Token accounting."""
        return {
            "active_tokens": self.active_tokens,
            "hard_limit": self.max_context,
            "messages_active": len(self.messages),
            "messages_archived": len(self.archived),
            "summaries": len(self.summaries),
            "saved_tokens": sum(count_tokens(s["content"]) for s in self.archived),
            "budget_used_pct": round(100 * self.active_tokens / self.max_context, 1)
            if self.max_context else 0.0,
        }

    # ── persistence (the "VectorDatabase" is SharedState) ─────────────

    def save(self) -> str:
        """
        Persist the full drive (active + archived + summaries) to
        SharedState under memory:stretch:<name>. Returns the record id.
        """
        record_id = f"memory:stretch:{self.name}"
        payload = {
            "id": record_id,
            "updated_at": time.time(),
            "active": self.messages,
            "archived": self.archived,
            "summaries": self.summaries,
            "usage": self.usage(),
        }
        if self.state is not None:
            self.state.write(record_id, payload, "whorl.memory")
        return record_id

    def load(self) -> bool:
        """Restore from SharedState. Returns True if a record was found."""
        if self.state is None:
            return False
        record = self.state.read(f"memory:stretch:{self.name}")
        if not isinstance(record, dict):
            return False
        self.messages = record.get("active", [])
        self.archived = record.get("archived", [])
        self.summaries = record.get("summaries", [])
        self.active_tokens = estimate_tokens(self.messages)
        return True

    # ── dumps ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "max_context": self.max_context,
            "usage": self.usage(),
            "active": self.messages,
            "archived": self.archived,
            "summaries": self.summaries,
        }
