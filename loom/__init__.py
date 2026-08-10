"""
whorl.loom
──────────
CodeCity-Bench — ported and integrated into the helical Whorl package.

Entry point: scan(path) runs all four scanners in sequence,
weaves the topology, persists a scan record to SharedState,
and returns the LoomWeave.

CLI: whorl loom scan ./path
"""

from __future__ import annotations
import json
import time
import uuid
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
from whorl.core.state import SharedState

STATE_KEY_PREFIX = "loom:scan"


def _state() -> SharedState:
    """SharedState is path-jailed to ~/.whorl — loom records live there."""
    return SharedState("~/.whorl/loom.json")


def scan(target_path: str, silent: bool = False) -> LoomWeave:
    path = str(Path(target_path).resolve())
    weave = LoomWeave(
        version  = "1.0",
        metadata = {"target": path,
                    "timestamp": time.time()},
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
    """Write the scan record into SharedState (the outer package's store)."""
    scan_id = str(uuid.uuid4())[:8]
    record = {
        "id":        scan_id,
        "timestamp": weave.metadata.get("timestamp", 0),
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
    try:
        state = _state()
        state.write(f"{STATE_KEY_PREFIX}:{scan_id}", record, "whorl.loom")
        # Keep the most recent scan id discoverable
        state.write(f"{STATE_KEY_PREFIX}:latest", scan_id, "whorl.loom")
    except Exception as e:
        # Persistence is best-effort — the weave is still returned.
        print(f"[loom] (record not persisted: {e})")


def latest() -> dict | None:
    """Return the most recent persisted scan record, if any."""
    try:
        state = _state()
        scan_id = state.read(f"{STATE_KEY_PREFIX}:latest")
        if scan_id:
            return state.read(f"{STATE_KEY_PREFIX}:{scan_id}")
    except Exception:
        pass
    return None


def history(limit: int = 5) -> list[dict]:
    """Return the most recent scan records."""
    try:
        state = _state()
        keys = state.keys_starting_with(f"{STATE_KEY_PREFIX}:")
        ids = [k.split(":")[-1] for k in keys if not k.endswith(":latest")]
        records = [state.read(f"{STATE_KEY_PREFIX}:{i}") for i in ids]
        records = [r for r in records if isinstance(r, dict)]
        records.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return records[:limit]
    except Exception:
        return []
