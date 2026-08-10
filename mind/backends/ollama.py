"""
whorl.mind.backends.ollama
───────────────────────────
Ollama backend — wraps the ollama CLI for local inference.

This is the primary backend for resource-constrained environments
(Chromebook, Android/Termux). Ollama handles model caching, quantization,
and memory management automatically.

Uses subprocess calls to `ollama` CLI — no Python deps needed.
"""

from __future__ import annotations
import json
import subprocess
import time
from typing import List, Optional

from .base import ModelBackend
from ..models import (
    ModelSpec, ModelRequest, ModelResponse,
    BackendKind, ModelRole, QuantTier,
)


class OllamaBackend(ModelBackend):
    """Ollama CLI backend for local models."""

    kind = BackendKind.OLLAMA

    # Built-in catalog — models we know about with roles pre-assigned
    KNOWN_MODELS: dict[str, dict] = {
        "llama3.2:1b": {
            "roles": [ModelRole.GENERAL],
            "params": "1B", "context": 2048,
            "aliases": ["llama", "general"],
        },
        "granite3.2:2b": {
            "roles": [ModelRole.REASONING, ModelRole.GENERAL],
            "params": "2B", "context": 131072,
            "aliases": ["thinker", "reason"],
        },
        "granite-code:3b-instruct-q3_K_M": {
            "roles": [ModelRole.CODE],
            "params": "3B", "context": 128000,
            "aliases": ["code", "dev"],
        },
        "mannix/smallthinker-abliterated:IQ3_XXS": {
            "roles": [ModelRole.CREATIVE],
            "params": "3B", "context": 32768,
            "aliases": ["wild", "uncensored", "creative"],
        },
    }

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        """Run an ollama CLI command."""
        return subprocess.run(
            ["ollama", *args],
            capture_output=True, text=True, timeout=60,
        )

    def _run_json(self, *args: str) -> dict:
        """Run an ollama CLI command expecting JSON output."""
        result = self._run(*args)
        result.check_returncode()
        return json.loads(result.stdout)

    def health(self) -> bool:
        """Check if ollama server is reachable."""
        try:
            result = self._run("list")
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

    def list_models(self) -> List[ModelSpec]:
        """Discover all models installed in ollama."""
        try:
            output = self._run("list")
            if output.returncode != 0:
                return []

            specs = []
            lines = output.stdout.strip().split("\n")
            # Skip header line
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                name = parts[0]
                size_str = parts[2]
                unit = parts[3] if len(parts) > 3 else "GB"

                # Parse size
                try:
                    size_val = float(size_str)
                except ValueError:
                    size_val = 0.0
                if unit == "MB":
                    size_val /= 1000

                # Check known models catalog
                known = self.KNOWN_MODELS.get(name, {})
                roles = known.get("roles", [ModelRole.GENERAL])
                params_val = known.get("params", "")
                context_val = known.get("context", 4096)
                aliases = known.get("aliases", [])

                # Detect quantization from tag
                quant = QuantTier.Q4_K
                for qt in QuantTier:
                    if qt.value in name.lower():
                        quant = qt
                        break

                spec = ModelSpec(
                    name=name,
                    backend=BackendKind.OLLAMA,
                    tag=name,
                    size_gb=size_val,
                    roles=roles,
                    quant=quant,
                    context=context_val,
                    params=params_val,
                    source=f"ollama:{name}",
                    aliases=aliases,
                )
                specs.append(spec)

            return specs

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return []

    def is_installed(self, model: ModelSpec) -> bool:
        """Check if a model is in ollama's local catalog."""
        for m in self.list_models():
            if m.tag == model.tag:
                return True
        return False

    def generate(self, request: ModelRequest, model: ModelSpec) -> ModelResponse:
        """Run inference through ollama CLI."""
        t0 = time.time()

        # Build the prompt — with system message if provided
        full_prompt = request.prompt
        if request.system:
            full_prompt = f"System: {request.system}\n\nUser: {request.prompt}"

        # Build command with model parameters
        cmd = ["ollama", "run", model.tag]
        cmd.extend(["--temperature", str(request.temperature)])
        cmd.extend(["--max-tokens", str(request.max_tokens)])
        cmd.append(full_prompt)

        result = self._run(*cmd)
        elapsed = (time.time() - t0) * 1000

        if result.returncode != 0:
            return ModelResponse(
                text=f"[ollama error] {result.stderr.strip()}",
                model=model.name,
                backend=BackendKind.OLLAMA,
                elapsed_ms=elapsed,
            )

        return ModelResponse(
            text=result.stdout.strip(),
            model=model.name,
            backend=BackendKind.OLLAMA,
            elapsed_ms=round(elapsed, 1),
        )

    def pull(self, model: ModelSpec) -> bool:
        """Pull a model from ollama library."""
        try:
            result = self._run("pull", model.tag)
            return result.returncode == 0
        except Exception:
            return False

    def unload(self, model: ModelSpec) -> bool:
        """Unload a model from ollama memory."""
        result = self._run("stop", model.tag)
        return result.returncode == 0
