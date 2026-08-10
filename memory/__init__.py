"""
whorl.memory
────────────
The External Context Drive.

Builds out the concept stubs that lived in `concept_source/`
(concept_token_stretcher.py, concept_external_context_drive.py,
concept_summary_cycle.py) onto the firm rails of the Whorl package:

  - SharedState  (whorl.core.state)   → the persistent external memory bank
  - model_spirit (whorl.tools.model_spirit) → the summarizer (when reachable)

Components:
  TokenStretcher   — keeps active context under a hard token budget;
                     compresses the oldest messages into a summary and
                     archives them externally.
  ContextExpander  — the "drive": full history persists to SharedState;
                     retrieval re-injects relevant chunks into active context.
  summarize_cycle  — every N messages, fold the conversation into a summary.
  count_tokens     — dependency-free token estimator (word + char hybrid).

Everything degrades gracefully offline: if no model is reachable, a
deterministic extractive summarizer is used so the drive never deadlocks.
"""

from .tokens import count_tokens, estimate_tokens
from .stretcher import TokenStretcher
from .drive import ContextExpander, ContextDrive
from .cycle import summarize_cycle, Summarizer, tokens_saved

__all__ = [
    "count_tokens",
    "estimate_tokens",
    "TokenStretcher",
    "ContextExpander",
    "ContextDrive",
    "summarize_cycle",
    "Summarizer",
    "tokens_saved",
]
