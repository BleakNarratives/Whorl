"""
whorl.mind.models
─────────────────
Fundamental data structures for the Mind model scaffolding.

A ModelSpec describes a single model — local or remote, any backend.
A BackendType classifies the runtime engine.
A ModelIntent signals what the caller wants the model to do.

Designed for Whorl integration: ModelSpecs can be attached to Agent bearings
so agents can route prompts to the right model for the right job.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Backend Types ────────────────────────────────────────────────────

class BackendKind(str, Enum):
    """What engine runs this model."""
    OLLAMA       = "ollama"        # ollama serve (local, CPU-friendly)
    HUGGINGFACE  = "huggingface"   # transformers / hub (Python-native)
    LLAMACPP     = "llamacpp"      # llama.cpp (GGUF, extreme efficiency)
    OPENAI       = "openai"        # OpenAI-compatible API
    CUSTOM       = "custom"        # User-defined backend


class ModelRole(str, Enum):
    """What a model is best at — used for routing."""
    GENERAL      = "general"       # Catch-all conversation
    CODE         = "code"          # Code gen, review, explanation
    REASONING    = "reasoning"     # Chain-of-thought, logic
    CREATIVE     = "creative"      # Uncensored, storytelling, chaos
    EMBEDDING    = "embedding"     # Text → vector
    VISION       = "vision"        # Image understanding
    TOOL_USE     = "tool_use"      # Function calling


# ── Quantization tier ────────────────────────────────────────────────

class QuantTier(str, Enum):
    """How aggressively the model is quantized."""
    FP16  = "fp16"    # Full precision
    Q8_0  = "q8_0"    # 8-bit
    Q6_K  = "q6_k"    # 6-bit high quality
    Q5_K  = "q5_k"    # 5-bit
    Q4_K  = "q4_k"    # 4-bit (most common default)
    Q3_K  = "q3_k"    # 3-bit (tight RAM)
    Q2_K  = "q2_k"    # 2-bit (extreme compression)
    IQ3   = "iq3"     # Importance-matrix 3-bit


# ── Model Spec ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelSpec:
    """
    Complete description of a single model.

    Immutable (frozen) to prevent runtime corruption — models are
    discovered, not mutated. To add a model, register a new spec.

    Like a Lexeme in whorl.loom, a ModelSpec is a discrete knot
    in the Mind topology.
    """
    name:         str                             # e.g. "granite3.2:2b"
    backend:      BackendKind                     # what engine runs it
    tag:          str                             # full backend-specific tag
    size_gb:      float                           # disk footprint in GB
    roles:        List[ModelRole] = field(default_factory=lambda: [ModelRole.GENERAL])
    quant:        QuantTier = QuantTier.Q4_K
    context:      int = 4096                      # max context length
    params:       str = ""                        # human-readable param count "2B"
    source:       str = ""                        # HuggingFace slug, Ollama tag, etc.
    aliases:      List[str] = field(default_factory=list)
    metadata:     Dict[str, Any] = field(default_factory=dict)

    def has_role(self, role: ModelRole) -> bool:
        return role in self.roles

    def fits_ram(self, ram_gb: float, overhead: float = 0.5) -> bool:
        """Can this model run in the given RAM budget?"""
        return self.size_gb + overhead <= ram_gb


# ── Model Intent ─────────────────────────────────────────────────────

class Intent(str, Enum):
    """What the caller wants — maps to how a model should respond."""
    CHAT       = "chat"        # Interactive conversation
    COMPLETE   = "complete"    # One-shot completion
    CODE_GEN   = "code_gen"    # Generate code from description
    CODE_FIX   = "code_fix"    # Fix broken code
    EXPLAIN    = "explain"     # Explain a concept or code block
    SUMMARIZE  = "summarize"   # Condense text
    ANALYZE    = "analyze"     # Deep analysis
    CREATIVE   = "creative"    # Unfiltered creative output


@dataclass(frozen=True)
class ModelRequest:
    """A request to route to a model backend."""
    intent:      Intent
    prompt:      str
    model:       Optional[str] = None           # Optional: force a specific model
    role:        Optional[ModelRole] = None     # Preferred role for routing
    system:      Optional[str] = None           # System prompt override
    temperature: float = 0.7
    max_tokens:  int = 1024
    metadata:    Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """What comes back from a model."""
    text:         str
    model:        str                            # which model responded
    backend:      BackendKind
    elapsed_ms:   float
    tokens_in:    int  = 0
    tokens_out:   int  = 0
    metadata:     Dict[str, Any] = field(default_factory=dict)
