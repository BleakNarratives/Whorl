"""
whorl.mind
──────────
The Mind module — modular model scaffolding for Whorl.

Provides:
  - Backend-agnostic model discovery (Ollama, HuggingFace, ...)
  - Role-based routing (CODE, REASONING, CREATIVE, ...)
  - Model registry with alias resolution
  - Pluggable backend architecture — add llama.cpp, vLLM, etc.

Designed to be:
  - Modular: new backends are one file
  - Growable: the registry auto-discovers what's available
  - Whorl-compatible: ModelSpecs can bind to Agent bearings
"""

from .models import (
    ModelSpec, ModelRequest, ModelResponse,
    BackendKind, ModelRole, Intent, QuantTier,
)
from .backends import ModelBackend, OllamaBackend, HuggingFaceBackend
from .registry import ModelRegistry, RegistrySnapshot

__all__ = [
    # Data structures
    "ModelSpec", "ModelRequest", "ModelResponse",
    "BackendKind", "ModelRole", "Intent", "QuantTier",
    # Backends
    "ModelBackend", "OllamaBackend", "HuggingFaceBackend",
    # Registry
    "ModelRegistry", "RegistrySnapshot",
]
