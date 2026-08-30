"""
whorl.loom.scanners.base
────────────────────────
Abstract base for all Loom scanners.
Original: CodeCity-Bench/src/core/scanners/base.py
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict

from whorl.loom.models import LoomWeave


class BaseScanner(ABC):
    """
    Each scanner analyzes a target (file or directory) and
    populates Lexemes into a LoomWeave.

    Scanners are composable — run multiple scanners over the same
    target and merge their metric contributions into one weave.
    """

    def __init__(self, target_path: str):
        self.target_path = target_path

    @abstractmethod
    def scan(self, weave: LoomWeave) -> LoomWeave:
        """
        Analyze the target and add Lexemes + metrics to the weave.
        Returns the same weave (mutated in-place) for chaining.
        """
        ...

    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """Human-readable summary of what this scanner found."""
        ...
