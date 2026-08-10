"""
whorl.mind.backends
────────────────────
Pluggable model backends.

Each backend implements the ModelBackend ABC:
  - OllamaBackend    : local ollama serve
  - HuggingFaceBackend : transformers pipeline

To add a new backend (llama.cpp, vLLM, OpenAI API):
  1. Subclass ModelBackend
  2. Set `kind` to the appropriate BackendKind
  3. Implement list_models(), generate(), health()
  4. Register it in mind/registry.py's DEFAULT_BACKENDS
"""

from .base import ModelBackend
from .ollama import OllamaBackend
from .huggingface import HuggingFaceBackend

__all__ = [
    "ModelBackend",
    "OllamaBackend",
    "HuggingFaceBackend",
]
