"""
whorl.loom.hotspots
───────────────────
The convergence-campaign report: the worst complexity zones of a codebase
as markdown.

`scan()` already computes everything this needs — per-file cyclomatic
complexity (and max/avg per function), function-level complexity with
nesting, line counts, and vibe (documentation density). This module
ranks the FILE hotspots (a zone to refactor is a file, not a bare
function) and renders a campaign-ready report:

    whorl loom hotspots <path> [--top N] [--out reports/loom_hotspots.md]

The report follows the campaign's existing conventions (see
reports/CROSTINI_CLEANUP_REPORT.md): a `Generated:` line, a summary, a
ranked table, per-zone detail with worst functions and a concrete next
action, and a "watch" section for undocumented zones and security flags.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from whorl.loom.models import LoomWeave, Lexeme
from whorl.loom.report import _complexity_label


def _measured_files(weave: LoomWeave) -> List[Lexeme]:
    """Files that carry a real complexity metric (Python sources measured by
    the AST scanner) — everything else would just be a default 1.0 and noise."""
    return [
        l for l in weave.files()
        if l.get_metric("cyclomatic_complexity") is not None
    ]


def measured_file_count(weave: LoomWeave) -> int:
    """How many file zones actually carry cyclomatic metrics."""
    return len(_measured_files(weave))


def file_hotspots(weave: LoomWeave, n: int = 10) -> List[Lexeme]:
    """
    Top N FILE zones by cyclomatic complexity.

    `n` is clamped to at least 1 so a negative or zero value can never
    silently invert or empty the ranking.
    """
    n = max(1, n)
    return sorted(_measured_files(weave),
                  key=lambda l: l.complexity(), reverse=True)[:n]


def worst_functions(weave: LoomWeave, file_lexeme: Lexeme, n: int = 5) -> List[dict]:
    """
    The heaviest functions inside a hotspot file, most complex first.

    Function lexemes are connected to their file during the scan; the
    line number is embedded in the lexeme id
    (function:<rel_path>:<name>:<lineno>).
    """
    funcs = []
    for fid in file_lexeme.edges:
        lex = weave.lexemes.get(fid)
        if lex is None or not lex.id.startswith("function:"):
            continue
        # id format: function:<rel_path>:<name>:<lineno> — rel paths use
        # "/" and Python identifiers cannot contain ":", so the last
        # field is always the line number.
        parts = lex.id.split(":")
        lineno = parts[-1]
        name = lex.label[len("function:"):]
        funcs.append({
            "name":       name,
            "complexity": lex.complexity(),
            "nesting":    lex.get_metric("nesting_depth") or 0.0,
            "lineno":     lineno,
            "band":       _complexity_label(lex.complexity()),
        })
    funcs.sort(key=lambda f: f["complexity"], reverse=True)
    return funcs[:n]


def _fmt_time(ts: Optional[float] = None) -> str:
    return datetime.fromtimestamp(ts).isoformat() if ts else datetime.now().isoformat()


def render_markdown(
    weave: LoomWeave,
    target_path: str = "",
    top: int = 10,
    generated: Optional[float] = None,
) -> str:
    """
    Render the full hotspots report for the convergence campaign.

    Args:
        weave: a completed LoomWeave (from whorl.loom.scan)
        target_path: the scanned path (for the header)
        top: how many hotspot zones to rank
        generated: unix timestamp for the Generated: line (default now)

    Returns:
        The markdown document as a string.
    """
    zones = file_hotspots(weave, top)

    L: List[str] = []
    L.append("# Loom Hotspots — worst complexity zones")
    L.append(f"Generated: {_fmt_time(generated)}")
    if target_path:
        L.append(f"Target: `{target_path}`")
    L.append("")
    L.append("> For the **convergence campaign**: fix the CRIT/HIGH zones first. "
             "A zone is a file — its worst functions are listed below.")
    L.append("")

    # ── Summary ───────────────────────────────────────────────────────
    crit = sum(1 for z in zones if _complexity_label(z.complexity()) == "CRIT")
    high = sum(1 for z in zones if _complexity_label(z.complexity()) == "HIGH")
    L.append("## Summary")
    L.append(f"- Files scanned: **{weave.file_count}**")
    L.append(f"- Functions: **{weave.function_count}**")
    L.append(f"- Total cyclomatic complexity: **{weave.total_complexity:.0f}**")
    L.append(f"- Avg vibe (documentation): **{weave.avg_vibe:.2f}**")
    L.append(f"- Security issues flagged: **{weave.security_count}**")
    L.append(f"- Hotspot zones ranked: **{len(zones)}** "
             f"({crit} CRIT, {high} HIGH, "
             f"{len(zones) - crit - high} MED/LOW)")
    L.append("")

    # ── Ranked table ──────────────────────────────────────────────────
    L.append("## Hotspot rank")
    if not zones:
        L.append("_No measurable hotspots found_ — no Python sources with "
                 "cyclomatic metrics were scanned.")
        L.append("")
        _also_watch(weave, L)
        return "\n".join(L)

    L.append("| # | Zone | Complexity | Band | Max func | Funcs | Lines | Vibe |")
    L.append("|---|------|-----------:|------|---------:|------:|------:|-----:|")
    for i, z in enumerate(zones, 1):
        rel = z.label[len("file:"):]
        band = _complexity_label(z.complexity())
        maxf = z.get_metric("max_function_complexity") or 0.0
        funcs = int(z.get_metric("function_count") or 0)
        lines = int(z.get_metric("line_count") or 0)
        L.append(
            f"| {i} | `{rel}` | {z.complexity():.0f} | {band} "
            f"| {maxf:.0f} | {funcs} | {lines} | {z.vibe():.2f} |"
        )
    L.append("")

    # ── Per-zone detail ───────────────────────────────────────────────
    L.append("## Top zones")
    for i, z in enumerate(zones, 1):
        rel = z.label[len("file:"):]
        band = _complexity_label(z.complexity())
        L.append("")
        L.append(f"### {i}. `{rel}`")
        L.append("")
        L.append(f"- **Complexity:** {z.complexity():.0f} ({band})")
        L.append(f"- **Max function:** "
                 f"{z.get_metric('max_function_complexity') or 0:.0f} · "
                 f"**Functions:** {int(z.get_metric('function_count') or 0)} · "
                 f"**Lines:** {int(z.get_metric('line_count') or 0)}")
        L.append(f"- **Vibe:** {z.vibe():.2f}"
                 + (" — **undocumented zone, document before touching**"
                    if z.vibe() < 0.3 else ""))
        L.append("")

        funcs = worst_functions(weave, z)
        if funcs:
            L.append("Worst functions:")
            L.append("")
            L.append("| Function | Complexity | Band | Nesting | Line |")
            L.append("|----------|-----------:|------|--------:|-----:|")
            for f in funcs:
                L.append(
                    f"| `{f['name']}` | {f['complexity']:.0f} "
                    f"| {f['band']} | {f['nesting']:.0f} | {f['lineno']} |"
                )
            L.append("")
            names = ", ".join(f"`{f['name']}`" for f in funcs)
            L.append(f"**Next action for the convergence campaign:** split the "
                     f"heaviest functions ({names}) out of this zone — each "
                     f"extraction cuts one decision surface out of a "
                     f"{band} file.")
        else:
            L.append("_No function-level measurements — module-level code or "
                     "non-Python content only._")
        L.append("")

    # ── Also watch ────────────────────────────────────────────────────
    _also_watch(weave, L)
    L.append("")
    L.append("---")
    L.append("*Reported by `whorl loom hotspots`. Re-run after each refactor "
             "round; the campaign's rules of engagement live in "
             "`CONVERGENCE_GUARDRAILS.md`.*")
    return "\n".join(L)


def _also_watch(weave: LoomWeave, L: List[str]) -> None:
    """Append the dark-spots + security-flag watch list. Shared by the normal
    and empty-scan report paths so neither hardcodes a wrong answer."""
    L.append("## Also watch")
    dark = [d for d in weave.dark_spots(n=6) if d.id.startswith("file:")]
    if dark:
        L.append("- **Dark spots (undocumented, dangerous to touch):**")
        for d in dark:
            rel = d.label[len("file:"):]
            L.append(f"  - `{rel}` — vibe {d.vibe():.2f}")
    else:
        L.append("- Dark spots: none")

    flags = weave.security_flags()
    if flags:
        L.append("- **Security flags:**")
        seen = set()
        for lex, metric in flags[:8]:
            key = f"{lex.label}:{metric.name}"
            if key in seen:
                continue
            seen.add(key)
            rel = lex.label[len("file:"):]
            L.append(f"  - `{rel}` — {metric.name} "
                     f"(line {metric.metadata.get('lineno', '?')})")
    else:
        L.append("- Security flags: 0")
