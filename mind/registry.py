"""
whorl.mind.registry
───────────────────
The ModelRegistry — discovers, manages, and routes across backends.

Like Loomy hosts agents, the Registry hosts model backends.
It provides:
  - Automatic discovery of installed models across all backends
  - Role-based routing (give me a CODE model)
  - Alias resolution (lm code → granite-code:3b)
  - Health monitoring of backends

Usage:
    registry = ModelRegistry()
    registry.discover()                    # scan all backends

    model = registry.resolve("code")       # find the code model
    model = registry.resolve_role(ModelRole.CODE)  # any code model

    response = registry.ask("Write a Python function", role=ModelRole.CODE)
    response = registry.ask("Tell me a joke", model="llama3.2:1b")
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import (
    ModelSpec, ModelRequest, ModelResponse,
    BackendKind, ModelRole, Intent,
)
from .backends import (
    ModelBackend,
    OllamaBackend,
    HuggingFaceBackend,
)


@dataclass
class RegistrySnapshot:
    """A point-in-time view of all models across backends."""
    backends: List[str]                        # active backend names
    total_models: int
    by_role: Dict[str, List[str]]              # role → [model names]
    models: List[ModelSpec]
    timestamp: float = field(default_factory=time.time)


class ModelRegistry:
    """
    Central model registry.

    Discovers models across all registered backends, resolves
    aliases and roles, and routes requests to the right model.

    Pattern matches Loomy: Loomy hosts agents, Registry hosts backends.
    """

    def __init__(self, auto_discover: bool = True):
        self._backends: Dict[BackendKind, ModelBackend] = {}
        self._models: Dict[str, ModelSpec] = {}      # tag → spec
        self._aliases: Dict[str, str] = {}            # alias → tag
        self._by_role: Dict[ModelRole, List[str]] = {}  # role → [tags]

        # Register default backends
        self._register(OllamaBackend())
        self._register(HuggingFaceBackend())

        if auto_discover:
            self.discover()

    # ── Backend Management ──────────────────────────────────────────

    def _register(self, backend: ModelBackend) -> None:
        """Register a backend (idempotent)."""
        self._backends[backend.kind] = backend

    def register_backend(self, backend: ModelBackend) -> None:
        """Public: add a custom backend."""
        self._register(backend)
        self.discover()

    def get_backend(self, kind: BackendKind) -> Optional[ModelBackend]:
        """Get a backend by kind."""
        return self._backends.get(kind)

    def healthy_backends(self) -> List[ModelBackend]:
        """Only backends that are currently reachable."""
        return [b for b in self._backends.values() if b.health()]

    # ── Discovery ───────────────────────────────────────────────────

    def discover(self) -> RegistrySnapshot:
        """Scan all healthy backends for installed models."""
        self._models.clear()
        self._aliases.clear()
        self._by_role.clear()

        for backend in self.healthy_backends():
            for spec in backend.list_models():
                self._models[spec.tag] = spec

                # Index aliases
                for alias in spec.aliases:
                    self._aliases[alias] = spec.tag

                # Index by role
                for role in spec.roles:
                    if role not in self._by_role:
                        self._by_role[role] = []
                    if spec.tag not in self._by_role[role]:
                        self._by_role[role].append(spec.tag)

        return self.snapshot()

    def snapshot(self) -> RegistrySnapshot:
        """Current state of the registry."""
        by_role = {
            role.value: [self._models[t].name for t in tags]
            for role, tags in self._by_role.items()
        }
        return RegistrySnapshot(
            backends=[b.kind.value for b in self.healthy_backends()],
            total_models=len(self._models),
            by_role=by_role,
            models=list(self._models.values()),
        )

    # ── Resolution ──────────────────────────────────────────────────

    def resolve(self, identifier: str) -> Optional[ModelSpec]:
        """
        Resolve a model by alias, name, or tag.

        Resolution order:
          1. Exact alias match ("code")
          2. Exact tag match ("granite-code:3b-instruct-q3_K_M")
          3. Prefix match on tag
        """
        # Alias lookup
        if identifier in self._aliases:
            return self._models.get(self._aliases[identifier])

        # Exact tag match
        if identifier in self._models:
            return self._models[identifier]

        # Prefix match
        for tag, spec in self._models.items():
            if tag.startswith(identifier):
                return spec

        return None

    def resolve_role(self, role: ModelRole) -> Optional[ModelSpec]:
        """Get the first available model for a given role."""
        tags = self._by_role.get(role, [])
        for tag in tags:
            if tag in self._models:
                return self._models[tag]
        return None

    def list_roles(self) -> Dict[ModelRole, List[ModelSpec]]:
        """All models, grouped by role."""
        return {
            role: [self._models[t] for t in tags if t in self._models]
            for role, tags in self._by_role.items()
        }

    # ── Inference ───────────────────────────────────────────────────

    def ask(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ModelResponse:
        """
        Send a prompt to a model. Route automatically if no model specified.

        Args:
          prompt: The user prompt
          model: Optional specific model identifier (alias, name, or tag)
          role: Preferred role for routing (e.g. ModelRole.CODE)
          system: Optional system prompt
          temperature: Creativity (0.0 = deterministic, 1.0 = wild)
          max_tokens: Max output tokens

        Returns:
          ModelResponse with the generated text and metadata.
        """
        t0 = time.time()

        # Resolve the model
        spec: Optional[ModelSpec] = None
        if model:
            spec = self.resolve(model)
        elif role:
            spec = self.resolve_role(role)

        if spec is None:
            elapsed = (time.time() - t0) * 1000
            return ModelResponse(
                text=f"[mind] No model found. "
                     f"model={model}, role={role}. "
                     f"Run discover() and try again.",
                model="unknown",
                backend=BackendKind.CUSTOM,
                elapsed_ms=elapsed,
            )

        # Build request
        intent = Intent.CHAT
        if role == ModelRole.CODE:
            intent = Intent.CODE_GEN
        elif role == ModelRole.CREATIVE:
            intent = Intent.CREATIVE
        elif role == ModelRole.REASONING:
            intent = Intent.ANALYZE

        request = ModelRequest(
            intent=intent,
            prompt=prompt,
            model=spec.tag,
            role=role,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Route to the right backend
        backend = self._backends.get(spec.backend)
        if backend is None or not backend.health():
            elapsed = (time.time() - t0) * 1000
            return ModelResponse(
                text=f"[mind] Backend {spec.backend.value} is not available.",
                model=spec.name,
                backend=spec.backend,
                elapsed_ms=elapsed,
            )

        return backend.generate(request, spec)

    # ── Introspection ───────────────────────────────────────────────

    @property
    def model_count(self) -> int:
        return len(self._models)

    def model_names(self) -> List[str]:
        return [s.name for s in self._models.values()]

    def __len__(self) -> int:
        return len(self._models)

    def __contains__(self, identifier: str) -> bool:
        return self.resolve(identifier) is not None
