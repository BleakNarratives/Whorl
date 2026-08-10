"""
whorl.mind.backends.base
─────────────────────────
Abstract base class for all model backends.

Every backend must implement:
  - list_models()  → discover available models
  - is_installed() → check if a model is available
  - generate()     → send a prompt, get a response
  - health()       → is the backend reachable?

New backends (vLLM, llama.cpp, custom APIs) extend this base.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import ModelSpec, ModelRequest, ModelResponse, BackendKind


class ModelBackend(ABC):
    """
    Abstract model backend.

    Subclasses implement the actual inference plumbing.
    The registry calls these — users never touch backends directly.
    """

    kind: BackendKind  # Set by subclass

    @abstractmethod
    def list_models(self) -> List[ModelSpec]:
        """Discover all models available through this backend."""
        ...

    @abstractmethod
    def is_installed(self, model: ModelSpec) -> bool:
        """Check if a specific model is available locally."""
        ...

    @abstractmethod
    def generate(self, request: ModelRequest, model: ModelSpec) -> ModelResponse:
        """Send a request to a model and return the response."""
        ...

    @abstractmethod
    def health(self) -> bool:
        """Check if the backend is reachable and operational."""
        ...

    def pull(self, model: ModelSpec) -> bool:
        """
        Download/install a model. Optional — not all backends support this.
        Returns True on success.
        """
        return False

    def unload(self, model: ModelSpec) -> bool:
        """
        Unload a model from memory. Optional.
        Returns True if model was unloaded.
        """
        return False
