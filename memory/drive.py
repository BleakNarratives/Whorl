"""
whorl.memory.drive
──────────────────
The External Context Drive — ContextExpander.

Builds out `concept_source/concept_external_context_drive.py`, which was
all `pass` stubs:

    class ContextExpander:
        def __init__(self, base_model, external_storage="vector_db"):
            self.model = base_model
            self.memory_bank = []      # External storage
            self.active_context = []   # RAM equivalent

        def smart_compress(self, conversation_history):  # pass
        def context_retrieval(self, current_query):     # pass

The external storage is SharedState (whorl.core.state). Compression is
handled by the TokenStretcher; retrieval is a lightweight lexical +
recency scorer that re-injects the most relevant archived chunk into the
active context — no heavy vector DB required on a 2.6 GB machine.
"""

from __future__ import annotations
import re
import time

from .tokens import count_tokens, estimate_tokens
from .stretcher import TokenStretcher
from .cycle import Summarizer


def _tokenize_lite(text: str) -> set[str]:
    """Lowercase word tokens for scoring — no external deps."""
    return set(re.findall(r"[a-z0-9]{2,}", text.lower()))


def _overlap(query_tokens: set[str], content: str) -> int:
    content_tokens = _tokenize_lite(content)
    if not content_tokens:
        return 0
    return len(query_tokens & content_tokens)


class ContextExpander:
    """
    External memory bank + retrieval.

    Usage:
        d = ContextExpander(state=SharedState(), name="scout-alpha")
        d.store("market:btc", "BTC consolidated above 42k ...")
        d.store("market:shipping", "Port congestion at LA ...")
        d.smart_compress(long_history)              # folds via TokenStretcher
        chunk = d.context_retrieval("what's shipping doing?")
    """

    def __init__(
        self,
        state=None,
        *,
        name: str = "default",
        max_context: int = 8000,
        summarizer: Summarizer | None = None,
    ):
        self.state = state
        self.name = name
        self.stretcher = TokenStretcher(
            max_context=max_context,
            state=state,
            name=f"{name}:drive",
            summarizer=summarizer,
        )
        self._bank: dict[str, dict] = {}
        self._hydrate()

    def _hydrate(self) -> None:
        """
        Load previously-persisted chunks from SharedState into memory.

        Without this, a fresh process would find an empty bank even though
        `whorl memory drive --put ...` persisted entries earlier — the
        store and the retrieval path must agree on what exists.
        """
        if self.state is None:
            return
        try:
            for key in self.state.keys_starting_with(f"memory:drive:{self.name}:"):
                rec = self.state.read(key)
                if isinstance(rec, dict) and "content" in rec:
                    self._bank[rec.get("key", key)] = rec
        except Exception:
            pass

    # ── external store ───────────────────────────────────────────────

    def store(self, key: str, content: str, meta: dict | None = None) -> None:
        """Persist a chunk to the external drive (SharedState)."""
        self._bank[key] = {
            "key": key,
            "content": content,
            "meta": meta or {},
            "stored_at": time.time(),
            "tokens": count_tokens(content),
        }
        if self.state is not None:
            self.state.write(f"memory:drive:{self.name}:{key}",
                             self._bank[key], "whorl.memory")

    def get(self, key: str) -> dict | None:
        if key in self._bank:
            return self._bank[key]
        if self.state is not None:
            rec = self.state.read(f"memory:drive:{self.name}:{key}")
            if isinstance(rec, dict):
                self._bank[key] = rec
                return rec
        return None

    def keys(self) -> list[str]:
        return sorted(self._bank.keys())

    # ── woven storage (Helix-Speak at-rest) ──────────────────────────

    def store_woven(self, key: str, content: str, weave_key: str,
                    agent_id: str = "whorl.memory") -> None:
        """
        Persist a chunk as a helical knot — unreadable at rest without the
        weave key. Retrieval can score it by key only (content is cipher).
        """
        from whorl.core.helix import Helix
        knot = Helix.weave(content, key=weave_key, weaver_id=agent_id)
        self._bank[key] = {
            "key": key,
            "content": knot.to_dict(),
            "woven": True,
            "stored_at": time.time(),
            "tokens": count_tokens(content),
        }
        if self.state is not None:
            self.state.write(f"memory:drive:{self.name}:{key}",
                             self._bank[key], "whorl.memory")

    def get_woven(self, key: str, weave_key: str):
        """Unravel a woven chunk back to plaintext. Returns None if absent;
        raises ValueError on a wrong key or corrupted chunk."""
        from whorl.core.helix import Helix, Knot
        rec = self.get(key)
        if rec is None:
            return None
        if rec.get("woven"):
            try:
                return Helix.unravel(Knot.from_dict(rec["content"]), key=weave_key)
            except (ValueError, KeyError, TypeError) as e:
                raise ValueError(f"cannot unravel '{key}': {e}") from e
        return rec.get("content")

    def bank_size(self) -> int:
        return len(self._bank)

    # ── compression ──────────────────────────────────────────────────

    def smart_compress(self, conversation_history) -> list[dict]:
        """
        Compress a conversation: the TokenStretcher keeps the recent tail
        verbatim and folds the older content into summaries. The summaries
        are also stored into the drive so retrieval can find them.
        """
        for m in conversation_history:
            self.stretcher.add_message(m)

        for summary in self.stretcher.summary_log():
            self.store(f"summary:{summary.get('compressed_at', 0.0):.3f}",
                       summary["content"],
                       {"role": "summary", "backend": summary.get("backend")})

        return self.stretcher.context()

    # ── retrieval ────────────────────────────────────────────────────

    def context_retrieval(self, query: str, top_k: int = 3,
                          include_active: bool = True,
                          weave_key: str | None = None):
        """
        Fetch the most relevant chunks from the external drive and
        re-inject them into active context.

        Scoring is recency-weighted lexical overlap — no vector DB needed:
            score = overlap(query, content) * recency_bonus
        """
        q_tokens = _tokenize_lite(query)
        scored = []

        for key, rec in self._bank.items():
            # Woven chunks are cipher at rest — score by key only, never
            # peek at their content (it would be garbage anyway).
            woven = bool(rec.get("woven"))
            content = "" if woven else rec.get("content", "")
            # Score both the chunk content AND its key — a query for
            # "shipping" should find the chunk stored under market:shipping.
            base = _overlap(q_tokens, content) + _overlap(q_tokens, key)
            if base == 0:
                continue
            # Recency bonus: newer chunks win ties.
            age = time.time() - rec.get("stored_at", 0)
            recency = 1.0 / (1.0 + age / 3600.0)
            scored.append((base * (0.7 + 0.3 * recency), key, rec))

        scored.sort(key=lambda t: t[0], reverse=True)
        hits = [s[1] for s in scored[:top_k]]

        injected = []
        for k in hits:
            rec = self._bank.get(k)
            if not rec:
                continue
            entry = dict(rec)
            if entry.get("woven"):
                if weave_key:
                    try:
                        from whorl.core.helix import Helix, Knot
                        entry["content"] = Helix.unravel(
                            Knot.from_dict(entry["content"]), key=weave_key)
                    except (ValueError, KeyError, TypeError):
                        entry["content"] = "(wrong weave key or corrupted chunk — cannot unravel)"
                else:
                    entry["content"] = "(woven at rest — pass --key to unravel)"
            injected.append(entry)

        if include_active:
            return {
                "query": query,
                "hits": hits,
                "injected_chunks": injected,
                "active_context": self.stretcher.context(),
                "tokens": estimate_tokens(
                    [c.get("content", "") for c in injected]
                    + [m.get("content", "") for m in self.stretcher.context()]
                ),
            }
        return injected

    # ── persistence ──────────────────────────────────────────────────

    def save(self) -> None:
        """Persist the whole drive state. Woven chunks stay woven."""
        self.stretcher.save()
        for key, rec in self._bank.items():
            if rec.get("woven"):
                # Re-persist the chunk as-is so the woven flag survives;
                # routing it through store() would flatten it to plaintext.
                if self.state is not None:
                    self.state.write(f"memory:drive:{self.name}:{key}",
                                     rec, "whorl.memory")
            else:
                self.store(key, rec["content"], rec.get("meta"))

    def usage(self) -> dict:
        return {
            "name": self.name,
            "bank_entries": self.bank_size(),
            "bank_tokens": sum(r.get("tokens", 0) for r in self._bank.values()),
            "stretcher": self.stretcher.usage(),
        }


# Alias — the concept stub called it ContextExpander; the ecosystem also
# reads well as ContextDrive. Both names point at the same class.
ContextDrive = ContextExpander
