"""
Whorl Core Model Orchestration
Manages local/remote model execution, fallbacks, and multi-agent routing.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whorl.models")


@dataclass
class ModelConfig:
    name: str
    provider: str  # e.g., 'puter', 'ollama', 'claude'
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelEngine:
    def __init__(self, default_model: str = "puter-gpt-4o-mini"):
        self.default_model = default_model
        self.registry: Dict[str, ModelConfig] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register primary local and bridge model configurations."""
        self.register(ModelConfig(name="puter-gpt-4o-mini", provider="puter"))
        self.register(ModelConfig(name="syntax-local", provider="ollama", max_tokens=2048))

    def register(self, config: ModelConfig) -> None:
        """Add or update a model target in the registry."""
        self.registry[config.name] = config
        logger.debug(f"Registered model target: {config.name}")

    def select_target(self, task_type: str = "general") -> ModelConfig:
        """Pick optimal model config based on intent routing."""
        if task_type == "code" and "syntax-local" in self.registry:
            return self.registry["syntax-local"]
        return self.registry.get(self.default_model, ModelConfig(name=self.default_model, provider="puter"))

    def execute(self, prompt: str, task_type: str = "general") -> Dict[str, Any]:
        """Route prompt to configured target."""
        target = self.select_target(task_type)
        logger.info(f"[Whorl] Routing task '{task_type}' to {target.name} ({target.provider})")

        try:
            response_text = f"Executed prompt via {target.name}"
            return {
                "status": "success",
                "model": target.name,
                "provider": target.provider,
                "output": response_text
            }
        except Exception as err:
            logger.error(f"[Whorl] Execution error on {target.name}: {err}")
            return {
                "status": "error",
                "model": target.name,
                "error": str(err)
            }


# Singleton engine instance
engine = ModelEngine()
