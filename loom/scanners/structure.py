"""
whorl.loom.scanners.structure
──────────────────────────────
Maps the file system hierarchy into Lexemes.
Each file and directory becomes a knot in the weave.
Original: CodeCity-Bench/src/core/scanners/structure_scanner.py — completed.

Metrics produced (STRUCTURAL):
  line_count     — total lines in file
  code_lines     — non-blank, non-comment lines
  file_size_kb   — file size in kilobytes
  depth          — directory nesting depth
  file_count     — number of files in a directory
"""

from __future__ import annotations
import os
from typing import Any, Dict, Set

from whorl.loom.models import Lexeme, LoomMetric, LoomWeave, MetricType
from .base import BaseScanner


SUPPORTED_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rs", ".rb", ".php",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".swift", ".kt", ".scala",
    ".sh", ".bash", ".zsh",
    ".sql", ".r", ".m",
}


def _metric(name: str, value: float, **meta) -> LoomMetric:
    return LoomMetric(
        name=name, value=value,
        metric_type=MetricType.STRUCTURAL,
        metadata=meta,
    )


def _count_lines(path: str):
    """Returns (total_lines, code_lines). Skips binary files."""
    total = 0
    code  = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                total += 1
                stripped = line.strip()
                if stripped and not stripped.startswith(("#", "//", "/*", "*", "<!--")):
                    code += 1
    except Exception:
        pass
    return total, code


class StructureScanner(BaseScanner):

    def __init__(self, target_path: str):
        super().__init__(target_path)
        self._summary: Dict[str, Any] = {}

    def scan(self, weave: LoomWeave) -> LoomWeave:
        base = os.path.abspath(self.target_path)
        total_files = 0
        total_lines = 0

        for root, dirs, files in os.walk(base):
            # Skip hidden dirs and common noise
            dirs[:] = [d for d in dirs
                       if not d.startswith(".")
                       and d not in ("__pycache__", "node_modules", ".git",
                                     "venv", ".venv", "dist", "build")]

            rel_root = os.path.relpath(root, base)
            depth    = 0 if rel_root == "." else rel_root.count(os.sep) + 1

            # ── Directory Lexeme ──────────────────────────────────────────
            if rel_root != ".":
                dir_id = f"dir:{rel_root}"
                if dir_id not in weave.lexemes:
                    weave.add(Lexeme(
                        id=dir_id,
                        label=f"dir:{rel_root}",
                        metrics=[
                            _metric("depth",      float(depth)),
                            _metric("file_count", float(len(files))),
                        ],
                    ))

            # ── File Lexemes ──────────────────────────────────────────────
            for fname in files:
                _, ext = os.path.splitext(fname)
                if ext.lower() not in SUPPORTED_EXTENSIONS:
                    continue

                fpath    = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, base)
                file_id  = f"file:{rel_path}"

                try:
                    size_kb = os.path.getsize(fpath) / 1024
                except OSError:
                    size_kb = 0.0

                lines, code_lines = _count_lines(fpath)
                total_files += 1
                total_lines += lines

                lexeme = Lexeme(
                    id=file_id,
                    label=f"file:{rel_path}",
                    metrics=[
                        _metric("line_count",   float(lines)),
                        _metric("code_lines",   float(code_lines)),
                        _metric("file_size_kb", size_kb),
                        _metric("depth",        float(depth)),
                    ],
                )
                weave.add(lexeme)

                # Connect file to its parent directory
                if rel_root != ".":
                    dir_id = f"dir:{rel_root}"
                    weave.connect(dir_id, file_id)

        self._summary = {
            "total_files": total_files,
            "total_lines": total_lines,
        }

        return weave

    def get_summary(self) -> Dict[str, Any]:
        return self._summary
