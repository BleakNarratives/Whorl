"""
whorl.loom.models
─────────────────
The fundamental data structures of the Loom topological space.
Original: CodeCity-Bench/src/core/loom/models.py — completed and integrated.

A LoomWeave is the full topology of a codebase:
  - Lexemes are the knots (files, functions, classes)
  - LoomMetrics are the measurements on each knot
  - Edges are the connections between knots
  - 3D coordinates come from layout.py after weave_topology()
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class MetricType(str, Enum):
    STRUCTURAL  = "structural"    # file size, line count, directory depth
    COMPLEXITY  = "complexity"    # cyclomatic complexity
    SEMANTIC    = "semantic"      # import coupling, function arity
    VIBE        = "vibe"          # documentation density (docstrings + comments)
    TOPOLOGICAL = "topological"   # connectedness, centrality
    SECURITY    = "security"      # vulnerability patterns


@dataclass(frozen=True)
class LoomMetric:
    """A single measurement at a knot in the topological space."""
    name:        str
    value:       float
    metric_type: MetricType
    metadata:    Dict[str, Any] = field(default_factory=dict)


@dataclass
class Lexeme:
    """
    The fundamental unit of the Loom weave.
    A Lexeme is a discrete knot — a file, function, class, or directory.

    After weave_topology() runs, x/y/z hold the 3D position
    in the topological landscape.
    """
    id:       str
    label:    str                              # e.g. "function:calculate_total"
    metrics:  List[LoomMetric]                 = field(default_factory=list)
    edges:    List[str]                        = field(default_factory=list)  # Lexeme IDs
    x:        float                            = 0.0
    y:        float                            = 0.0
    z:        float                            = 0.0                          # complexity height

    def get_metric(self, name: str) -> Optional[float]:
        for m in self.metrics:
            if m.name == name:
                return m.value
        return None

    def get_by_type(self, mtype: MetricType) -> List[LoomMetric]:
        return [m for m in self.metrics if m.metric_type == mtype]

    def complexity(self) -> float:
        c = self.get_metric("cyclomatic_complexity")
        return c if c is not None else 1.0

    def vibe(self) -> float:
        v = self.get_metric("vibe_score")
        return v if v is not None else 0.0

    def security_issues(self) -> List[LoomMetric]:
        return self.get_by_type(MetricType.SECURITY)


@dataclass
class LoomWeave:
    """
    The complete topological surface of a scanned codebase.
    Holds all Lexemes and aggregate statistics.
    """
    version:  str                              = "1.0"
    lexemes:  Dict[str, Lexeme]                = field(default_factory=dict)
    metadata: Dict[str, Any]                   = field(default_factory=dict)

    # Aggregate stats — populated by weave_topology()
    total_complexity:  float = 0.0
    avg_vibe:          float = 0.0
    security_count:    int   = 0
    file_count:        int   = 0
    function_count:    int   = 0

    def add(self, lexeme: Lexeme) -> None:
        self.lexemes[lexeme.id] = lexeme

    def connect(self, from_id: str, to_id: str) -> None:
        if from_id in self.lexemes:
            if to_id not in self.lexemes[from_id].edges:
                self.lexemes[from_id].edges.append(to_id)

    def files(self) -> List[Lexeme]:
        return [l for l in self.lexemes.values() if l.id.startswith("file:")]

    def functions(self) -> List[Lexeme]:
        return [l for l in self.lexemes.values() if l.id.startswith("function:")]

    def hotspots(self, n: int = 10) -> List[Lexeme]:
        """Top N most complex Lexemes — the danger zones."""
        return sorted(
            self.lexemes.values(),
            key=lambda l: l.complexity(),
            reverse=True,
        )[:n]

    def dark_spots(self, n: int = 10) -> List[Lexeme]:
        """Top N least documented Lexemes — the vibe deserts."""
        candidates = [l for l in self.lexemes.values()
                      if l.id.startswith(("file:", "function:"))]
        return sorted(candidates, key=lambda l: l.vibe())[:n]

    def security_flags(self) -> List[Tuple[Lexeme, LoomMetric]]:
        """All security issues across the weave."""
        flags = []
        for lexeme in self.lexemes.values():
            for issue in lexeme.security_issues():
                flags.append((lexeme, issue))
        return flags
