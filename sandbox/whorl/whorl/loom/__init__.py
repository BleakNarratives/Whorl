"""
whorl.loom
──────────
CodeCity-Bench — ported and integrated.

Entry point: scan(path) runs all four scanners in sequence,
weaves the topology, persists to DB, and returns the LoomWeave.

CLI: whorl loom scan ./path
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from whorl.loom.models    import LoomWeave
from whorl.loom.weaver    import LoomWeaver
from whorl.loom.report    import print_report
from whorl.loom.scanners  import (
    StructureScanner,
    ComplexityScanner,
    ScribeScanner,
    SecurityScanner,
)
from whorl.core import db


def scan(target_path: str, silent: bool = False) -> LoomWeave:
    path = str(Path(target_path).resolve())
    weave = LoomWeave(
        version  = "1.0",
        metadata = {"target": path,
                    "timestamp": datetime.now(timezone.utc).isoformat()},
    )

    scanners = [
        ("structure",  StructureScanner(path)),
        ("complexity", ComplexityScanner(path)),
        ("scribe",     ScribeScanner(path)),
        ("security",   SecurityScanner(path)),
    ]

    if not silent:
        print(f"\n[loom] Scanning {path}")

    for name, scanner in scanners:
        if not silent:
            print(f"[loom] Running {name} scanner...")
        scanner.scan(weave)

    if not silent:
        print("[loom] Weaving topology...")

    weaver = LoomWeaver(weave)
    weaver.weave_topology()

    _persist(weave, path)

    if not silent:
        print_report(weave, target_path)

    return weave


def _persist(weave: LoomWeave, target: str) -> None:
    record = {
        "id":        str(uuid.uuid4()),
        "timestamp": weave.metadata.get("timestamp", ""),
        "source_id": target,
        "blink":     f"{weave.file_count} files, complexity {weave.total_complexity:.0f}, vibe {weave.avg_vibe:.2f}",
        "brief":     (
            f"Scanned {weave.file_count} files, {weave.function_count} functions. "
            f"Total cyclomatic complexity: {weave.total_complexity:.0f}. "
            f"Avg vibe score: {weave.avg_vibe:.2f}. "
            f"Security issues: {weave.security_count}."
        ),
        "deep":      json.dumps({
            "hotspots": [
                {"label": l.label, "complexity": l.complexity()}
                for l in weave.hotspots(n=5)
            ],
            "dark_spots": [
                {"label": l.label, "vibe": l.vibe()}
                for l in weave.dark_spots(n=5)
            ],
            "security_count": weave.security_count,
        }),
        "full":      json.dumps({
            "lexeme_count":     len(weave.lexemes),
            "file_count":       weave.file_count,
            "func_count":       weave.function_count,
            "total_complexity": weave.total_complexity,
            "avg_vibe":         weave.avg_vibe,
            "security_count":   weave.security_count,
        }),
    }
    db.insert("qrds", record)
