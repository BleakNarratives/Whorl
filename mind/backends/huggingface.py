"""
whorl.mind.backends.huggingface
─────────────────────────────────
HuggingFace backend — wraps the transformers library.

Supports:
  - Any model on the HuggingFace Hub (text-generation)
  - Auto-detection of model architecture
  - CPU-first inference (good for resource-constrained environments)
  - Optional quantization via bitsandbytes

Unlike the Ollama backend, this requires:
  pip install transformers torch accelerate

This backend is OPTIONAL — the Mind system works without it.
If transformers isn't installed, health() returns False gracefully.
"""

from __future__ import annotations
import time
from typing import List, Optional

from .base import ModelBackend
from ..models import (
    ModelSpec, ModelRequest, ModelResponse,
    BackendKind, ModelRole, QuantTier,
)


class HuggingFaceBackend(ModelBackend):
    """HuggingFace transformers backend."""

    kind = BackendKind.HUGGINGFACE

    def __init__(self):
        self._pipeline = None
        self._loaded_model: Optional[str] = None
        self._transformers_available = False
        self._torch_available = False
        self._check_deps()

    def _check_deps(self) -> None:
        """Check if transformers + torch are importable."""
        try:
            import transformers  # noqa: F401
            self._transformers_available = True
        except ImportError:
            self._transformers_available = False

        try:
            import torch  # noqa: F401
            self._torch_available = True
        except ImportError:
            self._torch_available = False

    def health(self) -> bool:
        """Backend is healthy if deps are available."""
        return self._transformers_available and self._torch_available

    def list_models(self) -> List[ModelSpec]:
        """
        HF doesn't have a local model list like ollama.
        Returns built-in recommendations for small CPU-friendly models.
        """
        return [
            ModelSpec(
                name="microsoft/phi-2",
                backend=BackendKind.HUGGINGFACE,
                tag="microsoft/phi-2",
                size_gb=2.7,
                roles=[ModelRole.CODE, ModelRole.REASONING],
                quant=QuantTier.FP16,
                params="2.7B",
                context=2048,
                source="microsoft/phi-2",
                aliases=["phi2", "phi"],
            ),
            ModelSpec(
                name="Qwen/Qwen2.5-0.5B-Instruct",
                backend=BackendKind.HUGGINGFACE,
                tag="Qwen/Qwen2.5-0.5B-Instruct",
                size_gb=0.9,
                roles=[ModelRole.CODE, ModelRole.GENERAL],
                quant=QuantTier.FP16,
                params="0.5B",
                context=32768,
                source="Qwen/Qwen2.5-0.5B-Instruct",
                aliases=["qwen05", "tiny"],
            ),
            ModelSpec(
                name="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                backend=BackendKind.HUGGINGFACE,
                tag="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                size_gb=2.2,
                roles=[ModelRole.GENERAL],
                quant=QuantTier.FP16,
                params="1.1B",
                context=2048,
                source="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                aliases=["tinyllama"],
            ),
        ]

    def is_installed(self, model: ModelSpec) -> bool:
        """
        HF models are downloaded on first use — they're not "installed"
        in a registry. We consider them available if the backend is healthy.
        """
        return self.health()

    def generate(self, request: ModelRequest, model: ModelSpec) -> ModelResponse:
        """Run inference through transformers pipeline."""
        t0 = time.time()

        if not self.health():
            elapsed = (time.time() - t0) * 1000
            return ModelResponse(
                text="[HF error] transformers or torch not installed. "
                     "Run: pip install transformers torch",
                model=model.name,
                backend=BackendKind.HUGGINGFACE,
                elapsed_ms=elapsed,
            )

        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
            import torch
            import gc

            # Load model if not already loaded — unload previous first
            if self._loaded_model != model.tag:
                if self._pipeline is not None:
                    del self._pipeline
                    self._pipeline = None
                    gc.collect()
                if self._loaded_model is not None:
                    # Free torch memory if possible
                    if hasattr(torch, 'cuda'):
                        try:
                            torch.cuda.empty_cache()
                        except Exception:
                            pass

                tokenizer = AutoTokenizer.from_pretrained(model.tag, trust_remote_code=True)
                hf_model = AutoModelForCausalLM.from_pretrained(
                    model.tag,
                    torch_dtype=torch.float32,  # CPU-safe
                    device_map="cpu",
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                )
                self._pipeline = pipeline(
                    "text-generation",
                    model=hf_model,
                    tokenizer=tokenizer,
                )
                self._loaded_model = model.tag

            # Build prompt
            system_prefix = f"System: {request.system}\n" if request.system else ""
            full_prompt = f"{system_prefix}User: {request.prompt}\nAssistant:"

            output = self._pipeline(
                full_prompt,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                do_sample=True,
            )

            elapsed = (time.time() - t0) * 1000
            generated = output[0]["generated_text"]

            # Strip the input prompt from output
            if full_prompt in generated:
                generated = generated[len(full_prompt):].strip()

            return ModelResponse(
                text=generated,
                model=model.name,
                backend=BackendKind.HUGGINGFACE,
                elapsed_ms=round(elapsed, 1),
            )

        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            return ModelResponse(
                text=f"[HF error] {e}",
                model=model.name,
                backend=BackendKind.HUGGINGFACE,
                elapsed_ms=elapsed,
            )
