"""
whorl.loom.report
─────────────────
Terminal report renderer for a completed LoomWeave.
Designed for Termux — no colour libraries, pure ASCII.
"""

from __future__ import annotations
from whorl.loom.models import LoomWeave


VIBE_LABEL = {
    (0.0, 0.3): "GHOST  ░░░",
    (0.3, 0.6): "SPARSE ▒▒░",
    (0.6, 0.8): "DECENT ▓▒░",
    (0.8, 1.1): "VIVID  ███",
}

COMPLEXITY_LABEL = {
    (0,  6):  "LOW",
    (6,  11): "MED",
    (11, 21): "HIGH",
    (21, 999):"CRIT",
}


def _vibe_label(score: float) -> str:
    for (lo, hi), label in VIBE_LABEL.items():
        if lo <= score < hi:
            return label
    return "?"


def _complexity_label(score: float) -> str:
    for (lo, hi), label in COMPLEXITY_LABEL.items():
        if lo <= score < hi:
            return label
    return "?"


def _bar(value: float, max_val: float, width: int = 20) -> str:
    filled = int((value / max_val) * width) if max_val > 0 else 0
    return "█" * filled + "░" * (width - filled)


def print_report(weave: LoomWeave, target_path: str = "") -> None:
    W = 62

    print()
    print("═" * W)
    print("  WHORL LOOM — CODEBASE TOPOLOGY REPORT")
    if target_path:
        print(f"  {target_path}")
    print("═" * W)

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n  FILES       {weave.file_count}")
    print(f"  FUNCTIONS   {weave.function_count}")
    print(f"  COMPLEXITY  {weave.total_complexity:.0f}  total cyclomatic")
    print(f"  VIBE        {weave.avg_vibe:.2f}  ({_vibe_label(weave.avg_vibe)})")
    print(f"  SECURITY    {weave.security_count}  issues flagged")

    # ── Hotspots ───────────────────────────────────────────────────────
    hotspots = weave.hotspots(n=8)
    if hotspots:
        print(f"\n{'─'*W}")
        print("  COMPLEXITY HOTSPOTS  (refactor candidates)")
        print(f"{'─'*W}")
        max_c = max(l.complexity() for l in hotspots) or 1
        for lex in hotspots:
            c     = lex.complexity()
            label = _complexity_label(c)
            bar   = _bar(c, max_c, width=16)
            name  = lex.label[:38]
            print(f"  [{label}] {bar}  {c:4.0f}  {name}")

    # ── Dark spots ─────────────────────────────────────────────────────
    dark = weave.dark_spots(n=6)
    dark = [l for l in dark if l.id.startswith("file:")]
    if dark:
        print(f"\n{'─'*W}")
        print("  VIBE DARK SPOTS  (undocumented — dangerous to touch)")
        print(f"{'─'*W}")
        for lex in dark:
            v    = lex.vibe()
            bar  = _bar(v, 1.0, width=16)
            name = lex.label.replace("file:", "")[:42]
            print(f"  {_vibe_label(v)}  {bar}  {v:.2f}  {name}")

    # ── Security flags ─────────────────────────────────────────────────
    flags = weave.security_flags()
    if flags:
        print(f"\n{'─'*W}")
        print("  SECURITY FLAGS")
        print(f"{'─'*W}")
        seen = set()
        for lex, metric in flags[:12]:
            key = f"{lex.label}:{metric.name}"
            if key in seen:
                continue
            seen.add(key)
            lineno = metric.metadata.get("lineno", "?")
            file_  = lex.label.replace("file:", "")[:36]
            print(f"  [{metric.name:<22}]  line {lineno:<5}  {file_}")
    else:
        print(f"\n  No security issues detected.")

    print(f"\n{'═'*W}\n")
