"""
whorl.loom.scanners.complexity
───────────────────────────────
AST-based cyclomatic complexity scanner for Python files.
Original: CodeCity-Bench/src/core/scanners/complexity_scanner.py — completed.

Metrics produced (COMPLEXITY):
  cyclomatic_complexity  — per function and per file
  function_count         — number of functions/methods in file
  max_function_complexity — worst single function in file
  avg_function_complexity — mean across all functions
  nesting_depth          — max observed nesting level

Complexity ratings:
  1-5    LOW     — simple, readable
  6-10   MEDIUM  — manageable
  11-20  HIGH    — refactor candidate
  21+    CRITICAL — danger zone
"""

from __future__ import annotations
import ast
import os
from typing import Any, Dict, List, Tuple

from whorl.loom.models import Lexeme, LoomMetric, LoomWeave, MetricType
from .base import BaseScanner


def _metric(name: str, value: float, **meta) -> LoomMetric:
    return LoomMetric(
        name=name, value=value,
        metric_type=MetricType.COMPLEXITY,
        metadata=meta,
    )


class ComplexityVisitor(ast.NodeVisitor):
    """
    Counts cyclomatic complexity: starts at 1, +1 for each
    decision point (branch) in the code.
    """

    def __init__(self):
        self.complexity   = 1
        self.nesting      = 0
        self.max_nesting  = 0

    def _enter(self):
        self.nesting += 1
        self.max_nesting = max(self.max_nesting, self.nesting)

    def _exit(self):
        self.nesting -= 1

    def visit_If(self, node):
        self.complexity += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_For(self, node):
        self.complexity += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_While(self, node):
        self.complexity += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_Try(self, node):
        self.complexity += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # and/or each add a branch
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.complexity += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Match(self, node):
        # Python 3.10+ match/case
        self.complexity += len(node.cases)
        self.generic_visit(node)


def _measure_function(func_node: ast.FunctionDef | ast.AsyncFunctionDef) \
        -> Tuple[int, int]:
    """Returns (complexity, max_nesting) for a single function."""
    visitor = ComplexityVisitor()
    visitor.visit(func_node)
    return visitor.complexity, visitor.max_nesting


def _analyze_file(path: str) -> Tuple[List[Dict], int]:
    """
    Returns:
      functions — list of {name, complexity, nesting, lineno}
      file_complexity — sum of all function complexities
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return [], 0
    except Exception:
        return [], 0

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            c, nesting = _measure_function(node)
            functions.append({
                "name":       node.name,
                "complexity": c,
                "nesting":    nesting,
                "lineno":     node.lineno,
            })

    file_complexity = sum(f["complexity"] for f in functions) or 1
    return functions, file_complexity


class ComplexityScanner(BaseScanner):

    def __init__(self, target_path: str):
        super().__init__(target_path)
        self._summary: Dict[str, Any] = {}
        self._hotspots: List[Dict]    = []

    def scan(self, weave: LoomWeave) -> LoomWeave:
        base = os.path.abspath(self.target_path)
        all_hotspots = []
        total_complex = 0
        total_funcs   = 0

        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs
                       if not d.startswith(".")
                       and d not in ("__pycache__", "node_modules", ".git",
                                     "venv", ".venv", "dist", "build")]

            for fname in files:
                if not fname.endswith(".py"):
                    continue

                fpath    = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, base)
                file_id  = f"file:{rel_path}"

                functions, file_complexity = _analyze_file(fpath)
                total_complex += file_complexity
                total_funcs   += len(functions)

                # Add file-level complexity metric to existing file Lexeme
                if file_id in weave.lexemes:
                    max_c = max((f["complexity"] for f in functions), default=1)
                    avg_c = (file_complexity / len(functions)) if functions else 1.0

                    weave.lexemes[file_id].metrics.extend([
                        _metric("cyclomatic_complexity",   float(file_complexity)),
                        _metric("max_function_complexity", float(max_c)),
                        _metric("avg_function_complexity", avg_c),
                        _metric("function_count",          float(len(functions))),
                    ])

                # Create function-level Lexemes
                for func in functions:
                    func_id = f"function:{rel_path}:{func['name']}:{func['lineno']}"
                    f_lexeme = Lexeme(
                        id=func_id,
                        label=f"function:{func['name']}",
                        metrics=[
                            _metric("cyclomatic_complexity", float(func["complexity"])),
                            _metric("nesting_depth",         float(func["nesting"])),
                        ],
                    )
                    weave.add(f_lexeme)
                    weave.connect(file_id, func_id)

                    if func["complexity"] >= 10:
                        all_hotspots.append({
                            "file":       rel_path,
                            "function":   func["name"],
                            "complexity": func["complexity"],
                            "lineno":     func["lineno"],
                        })

        self._hotspots = sorted(all_hotspots,
                                key=lambda h: h["complexity"], reverse=True)
        self._summary  = {
            "total_complexity": total_complex,
            "total_functions":  total_funcs,
            "hotspots_found":   len(self._hotspots),
        }

        return weave

    def get_summary(self) -> Dict[str, Any]:
        return {**self._summary, "hotspots": self._hotspots[:10]}
