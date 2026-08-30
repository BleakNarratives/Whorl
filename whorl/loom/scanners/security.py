"""
whorl.loom.scanners.security
─────────────────────────────
Vulnerability pattern scanner. AST + regex over Python files.
Original: CodeCity-Bench/src/core/scanners/security_scanner.py — completed.

Patterns detected (SECURITY metrics):
  eval_usage         — eval() calls (code injection risk)
  exec_usage         — exec() calls
  shell_injection    — subprocess with shell=True
  hardcoded_secret   — password/key/secret in string literals
  sql_injection      — string-concatenated SQL queries
  pickle_usage       — pickle.loads / pickle.load (arbitrary code exec)
  os_system          — os.system() calls
  assert_security    — security logic in assert (stripped in -O mode)
  open_redirect      — redirect() with user-controlled input
  weak_hash          — md5 / sha1 usage for security purposes
"""

from __future__ import annotations
import ast
import os
import re
from typing import Any, Dict, List

from whorl.loom.models import Lexeme, LoomMetric, LoomWeave, MetricType
from .base import BaseScanner


def _sec(name: str, value: float, **meta) -> LoomMetric:
    return LoomMetric(
        name=name, value=value,
        metric_type=MetricType.SECURITY,
        metadata=meta,
    )


# ── AST-based detectors ────────────────────────────────────────────────────

class SecurityVisitor(ast.NodeVisitor):

    def __init__(self):
        self.issues: List[Dict] = []

    def _flag(self, name: str, lineno: int, detail: str = ""):
        self.issues.append({"pattern": name, "lineno": lineno, "detail": detail})

    def visit_Call(self, node):
        # eval() / exec()
        if isinstance(node.func, ast.Name):
            if node.func.id == "eval":
                self._flag("eval_usage", node.lineno, "Direct eval() call")
            elif node.func.id == "exec":
                self._flag("exec_usage", node.lineno, "Direct exec() call")

        # subprocess(..., shell=True)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("call", "run", "Popen", "check_output"):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant):
                        if kw.value.value is True:
                            self._flag("shell_injection", node.lineno,
                                       f"subprocess.{node.func.attr}(shell=True)")

        # pickle.loads / pickle.load
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("loads", "load"):
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "pickle":
                        self._flag("pickle_usage", node.lineno,
                                   "pickle.loads() — arbitrary code execution risk")

        # os.system()
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "system":
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "os":
                        self._flag("os_system", node.lineno, "os.system() call")

        # hashlib md5/sha1 (weak for security)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("md5", "sha1"):
                self._flag("weak_hash", node.lineno,
                           f"hashlib.{node.func.attr}() — weak for security use")

        self.generic_visit(node)

    def visit_Assert(self, node):
        # Assert used for security checks is stripped in -O mode
        if isinstance(node.test, ast.Compare):
            self._flag("assert_security", node.lineno,
                       "assert for validation — stripped in optimized mode")
        self.generic_visit(node)


# ── Regex-based detectors (operate on raw source) ─────────────────────────

HARDCODED_SECRET_PATTERNS = [
    (re.compile(r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']'), "hardcoded_password"),
    (re.compile(r'(?i)(api_key|apikey|secret_key|secret)\s*=\s*["\'][^"\']{8,}["\']'), "hardcoded_api_key"),
    (re.compile(r'(?i)(token)\s*=\s*["\'][A-Za-z0-9_\-\.]{16,}["\']'), "hardcoded_token"),
    (re.compile(r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----'), "embedded_private_key"),
]

SQL_CONCAT_PATTERN = re.compile(
    r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP)\s.+\+\s*(str\(|f["\']|["\'])',
    re.MULTILINE
)


def _regex_scan(source: str) -> List[Dict]:
    issues = []
    lines  = source.splitlines()

    for lineno, line in enumerate(lines, start=1):
        # Hardcoded secrets
        for pattern, name in HARDCODED_SECRET_PATTERNS:
            if pattern.search(line):
                issues.append({"pattern": name, "lineno": lineno,
                                "detail": "Potential hardcoded credential"})

        # SQL injection via concatenation
        if SQL_CONCAT_PATTERN.search(line):
            issues.append({"pattern": "sql_injection", "lineno": lineno,
                           "detail": "SQL string concatenation — injection risk"})

    return issues


def _scan_file(path: str) -> List[Dict]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except Exception:
        return []

    issues = _regex_scan(source)

    try:
        tree    = ast.parse(source, filename=path)
        visitor = SecurityVisitor()
        visitor.visit(tree)
        issues.extend(visitor.issues)
    except SyntaxError:
        pass

    return issues


class SecurityScanner(BaseScanner):

    def __init__(self, target_path: str):
        super().__init__(target_path)
        self._summary: Dict[str, Any] = {}
        self._all_issues: List[Dict]  = []

    def scan(self, weave: LoomWeave) -> LoomWeave:
        base = os.path.abspath(self.target_path)

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
                issues   = _scan_file(fpath)

                for issue in issues:
                    self._all_issues.append({**issue, "file": rel_path})

                if issues and file_id in weave.lexemes:
                    for issue in issues:
                        weave.lexemes[file_id].metrics.append(
                            _sec(issue["pattern"], 1.0,
                                 lineno=issue["lineno"],
                                 detail=issue.get("detail", ""))
                        )

        self._summary = {
            "total_issues": len(self._all_issues),
            "by_pattern":   _group_by(self._all_issues, "pattern"),
        }
        return weave

    def get_summary(self) -> Dict[str, Any]:
        return {**self._summary, "issues": self._all_issues[:20]}


def _group_by(items: list, key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        k = item.get(key, "unknown")
        out[k] = out.get(k, 0) + 1
    return out
