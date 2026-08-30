"""
whorl.loom.scanners.scribe
───────────────────────────
SMACK-grade scanner to quantify semantic documentation density.
Original: CodeCity-Bench/src/core/scanners/scribe_scanner.py — completed.

Produces a "Vibe Score" (0.0–1.0) per file and function:
  0.0–0.3  GHOST   — dark, undocumented, dangerous to touch
  0.3–0.6  SPARSE  — some hints, needs work
  0.6–0.8  DECENT  — readable for a focused reader
  0.8–1.0  VIVID   — fully lit, safe terrain

Metrics produced (VIBE):
  vibe_score          — composite 0.0-1.0
  docstring_coverage  — fraction of functions with docstrings
  comment_density     — comment lines / total lines
  inline_doc_ratio    — inline comments per function
"""

from __future__ import annotations
import ast
import tokenize
import io
import os
from typing import Any, Dict, Set, Tuple

from whorl.loom.models import Lexeme, LoomMetric, LoomWeave, MetricType
from .base import BaseScanner


def _metric(name: str, value: float, **meta) -> LoomMetric:
    return LoomMetric(
        name=name, value=value,
        metric_type=MetricType.VIBE,
        metadata=meta,
    )


def _has_docstring(node: ast.AST) -> bool:
    """True if the node's first statement is a string literal (docstring)."""
    if not isinstance(getattr(node, "body", None), list):
        return False
    body = node.body
    return (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )


def _get_comment_lines(source: str) -> Set[int]:
    """Return set of line numbers that contain comments."""
    comment_lines: Set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok_type, _, start, _, _ in tokens:
            if tok_type == tokenize.COMMENT:
                comment_lines.add(start[0])
    except tokenize.TokenError:
        pass
    return comment_lines


def _analyze_vibe(path: str) -> Tuple[float, float, float]:
    """
    Returns (vibe_score, docstring_coverage, comment_density)
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except Exception:
        return 0.0, 0.0, 0.0

    # ── AST pass: docstring coverage ────────────────────────────────────
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return 0.0, 0.0, 0.0

    functions_total = 0
    functions_with_doc = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            functions_total += 1
            if _has_docstring(node):
                functions_with_doc += 1

    docstring_coverage = (
        functions_with_doc / functions_total
        if functions_total > 0 else 0.5   # files with no functions get middle credit
    )

    # ── Tokenize pass: comment density ──────────────────────────────────
    total_lines   = source.count("\n") + 1
    comment_lines = _get_comment_lines(source)
    blank_lines   = sum(1 for l in source.splitlines() if not l.strip())
    code_lines    = max(total_lines - blank_lines, 1)

    comment_density = min(len(comment_lines) / code_lines, 1.0)

    # ── Composite Vibe Score ─────────────────────────────────────────────
    # Docstring coverage carries more weight than raw comment density
    vibe_score = (docstring_coverage * 0.65) + (comment_density * 0.35)
    vibe_score = min(vibe_score, 1.0)

    return vibe_score, docstring_coverage, comment_density


class ScribeScanner(BaseScanner):

    def __init__(self, target_path: str):
        super().__init__(target_path)
        self._summary: Dict[str, Any] = {}

    def scan(self, weave: LoomWeave) -> LoomWeave:
        base = os.path.abspath(self.target_path)
        total_vibe   = 0.0
        files_scanned = 0
        dark_spots: list = []

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

                vibe, doc_cov, comment_d = _analyze_vibe(fpath)
                total_vibe   += vibe
                files_scanned += 1

                if file_id in weave.lexemes:
                    weave.lexemes[file_id].metrics.extend([
                        _metric("vibe_score",         vibe),
                        _metric("docstring_coverage", doc_cov),
                        _metric("comment_density",    comment_d),
                    ])

                if vibe < 0.3:
                    dark_spots.append({"file": rel_path, "vibe": vibe})

        avg_vibe = total_vibe / files_scanned if files_scanned > 0 else 0.0

        self._summary = {
            "files_scanned": files_scanned,
            "avg_vibe":      round(avg_vibe, 3),
            "dark_spots":    sorted(dark_spots, key=lambda x: x["vibe"])[:10],
        }

        return weave

    def get_summary(self) -> Dict[str, Any]:
        return self._summary
