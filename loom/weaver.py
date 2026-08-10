"""
whorl.loom.weaver
─────────────────
LoomWeaver transforms discrete code metrics into a continuous
topological surface — the Weave.

Original: CodeCity-Bench/src/core/loom/weaver.py — completed.
"""

from __future__ import annotations
from .layout import calculate_layout, normalize_layout
from .models import Lexeme, LoomMetric, LoomWeave, MetricType


class LoomWeaver:
    """
    Consumes a LoomWeave (populated by scanners) and computes
    3D coordinates + aggregate statistics.

    Usage:
        weave  = LoomWeave()
        # ... scanners populate weave.lexemes ...
        weaver = LoomWeaver(weave)
        weaver.weave_topology()
        # weave.lexemes now have x, y, z coordinates
    """

    def __init__(self, weave: LoomWeave):
        self.weave = weave

    def weave_topology(self) -> LoomWeave:
        """
        1. Build nodes_data from lexeme metrics
        2. Run force-directed layout (x, y) + complexity height (z)
        3. Write coordinates back to lexemes
        4. Compute aggregate stats
        """
        nodes_data = {}

        for lexeme_id, lexeme in self.weave.lexemes.items():
            complexity = 1.0
            vibe       = 0.0

            for metric in lexeme.metrics:
                if metric.metric_type == MetricType.COMPLEXITY:
                    complexity = max(complexity, metric.value)
                elif metric.metric_type == MetricType.VIBE:
                    vibe = metric.value

            nodes_data[lexeme_id] = {
                "connections": lexeme.edges,
                "complexity":  complexity,
                "vibe":        vibe,
            }

        # Compute layout
        layout = calculate_layout(nodes_data)
        layout = normalize_layout(layout)

        # Write coordinates back
        for lexeme_id, coords in layout.items():
            if lexeme_id in self.weave.lexemes:
                self.weave.lexemes[lexeme_id].x = coords["x"]
                self.weave.lexemes[lexeme_id].y = coords["y"]
                self.weave.lexemes[lexeme_id].z = coords["z"]

        # Aggregate stats
        self._compute_aggregates()

        return self.weave

    def _compute_aggregates(self) -> None:
        w = self.weave
        lexemes = list(w.lexemes.values())

        if not lexemes:
            return

        w.file_count     = sum(1 for l in lexemes if l.id.startswith("file:"))
        w.function_count = sum(1 for l in lexemes if l.id.startswith("function:"))

        complexities = [l.complexity() for l in lexemes]
        w.total_complexity = sum(complexities)

        vibes = [l.vibe() for l in lexemes if l.vibe() > 0]
        w.avg_vibe = sum(vibes) / len(vibes) if vibes else 0.0

        w.security_count = sum(len(l.security_issues()) for l in lexemes)
