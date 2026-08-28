"""
whorl.agent_state
─────────────────
Git-like version tracking for agent state. Every agent gets a directory
under ~/.whorl/agents/{name}/ with versioned JSON files and a HEAD pointer.

Storage layout:
    ~/.whorl/agents/{name}/
        HEAD          → current version label (e.g. "v3" or "branch:fix-hedging")
        v1.json       → initial state
        v2.json       → after tuning
        v3.json       → current (HEAD points here)
        branches.json → {branch_name: version_label} map

State file schema (vN.json):
    {
      "version": 3,
      "branch": "main",
      "parent": "v2",
      "timestamp": "2026-08-27T21:00:00Z",
      "label": "tuned-register",
      "config": { "vertical": "hvac", "model": "llama3.2:1b", ... },
      "scores": {
        "fire_drill": { "runs": 12, "avg": 0.78, "pass_rate": "9/12" },
        "hotseat":    { "sessions": 3, "avg_confidence": 0.85 }
      },
      "history": [
        {"at": "...", "event": "created"},
        {"at": "...", "event": "fire_drill_score", "detail": "hallucination_probe: 0.9"}
      ]
    }

Operations:
    init_agent(name, config)        → create v1
    current(name)                   → read current state
    record_score(name, source, detail) → bump version with new score
    rewind(name, to_version)        → move HEAD back
    branch(name, branch_name)       → fork current state
    switch(name, target)            → move HEAD to any version/branch
    log(name)                       → version history
    list_agents()                   → all tracked agents
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from whorl.core.config import WHORL_DIR


# ── Paths ────────────────────────────────────────────────────────────────

AGENTS_DIR = WHORL_DIR / "agents"


def _agent_dir(name: str) -> Path:
    return AGENTS_DIR / name


def _head_path(name: str) -> Path:
    return _agent_dir(name) / "HEAD"


def _version_path(name: str, version: str) -> Path:
    return _agent_dir(name) / f"{version}.json"


def _branches_path(name: str) -> Path:
    return _agent_dir(name) / "branches.json"


# ── Low-level I/O ────────────────────────────────────────────────────────

def _read_head(name: str) -> str:
    """Read HEAD pointer. Returns version label like 'v3'."""
    p = _head_path(name)
    if not p.exists():
        return ""
    return p.read_text().strip()


def _write_head(name: str, label: str) -> None:
    _head_path(name).write_text(label)


def _read_version(name: str, version: str) -> Optional[dict]:
    """Read a version file. version can be 'v3' or 'branch:fix-hedging'."""
    # Resolve branch references
    if version.startswith("branch:"):
        branch_name = version.split(":", 1)[1]
        branches = _read_branches(name)
        version = branches.get(branch_name, version)
        if version.startswith("branch:"):
            return None  # broken branch ref

    p = _version_path(name, version)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _write_version(name: str, state: dict) -> str:
    """Write a version file. Returns the version label."""
    label = f"v{state['version']}"
    _version_path(name, label).write_text(
        json.dumps(state, indent=2, default=str)
    )
    return label


def _read_branches(name: str) -> Dict[str, str]:
    p = _branches_path(name)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def _write_branches(name: str, branches: Dict[str, str]) -> None:
    _branches_path(name).write_text(
        json.dumps(branches, indent=2)
    )


def _next_version(name: str) -> int:
    """Get the next version number."""
    head = _read_head(name)
    if not head:
        return 1
    state = _read_version(name, head)
    if state:
        return state["version"] + 1
    return 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ───────────────────────────────────────────────────────────

def init_agent(name: str, config: Dict[str, Any] = None) -> dict:
    """Create initial state (v1) for an agent. Idempotent."""
    d = _agent_dir(name)
    if _head_path(name).exists():
        return current(name)  # already initialized

    d.mkdir(parents=True, exist_ok=True)

    state = {
        "version": 1,
        "branch": "main",
        "parent": None,
        "timestamp": _now(),
        "label": "initial",
        "config": config or {},
        "scores": {},
        "history": [
            {"at": _now(), "event": "created"},
        ],
    }
    label = _write_version(name, state)
    _write_head(name, label)
    _write_branches(name, {"main": label})
    return state


def current(name: str) -> Optional[dict]:
    """Read the current state (HEAD)."""
    head = _read_head(name)
    if not head:
        return None
    return _read_version(name, head)


def record_score(name: str, source: str, detail: str,
                 scores_update: Dict[str, Any] = None) -> dict:
    """Bump version with a new score event.

    Args:
        name: agent name
        source: score source (e.g. "fire_drill", "hotseat", "manual")
        detail: human-readable detail (e.g. "hallucination_probe: 0.9")
        scores_update: optional dict to merge into scores[source]
    """
    state = current(name)
    if not state:
        state = init_agent(name)

    # Determine branch from HEAD
    head_label = _read_head(name)
    branch = "main"
    if head_label.startswith("branch:"):
        branch = head_label.split(":", 1)[1]
    elif ":" not in head_label:
        branches = _read_branches(name)
        for bname, blabel in branches.items():
            if blabel == head_label:
                branch = bname
                break

    new_version = state["version"] + 1

    # Merge scores
    new_scores = dict(state.get("scores", {}))
    if scores_update:
        if source not in new_scores:
            new_scores[source] = {}
        new_scores[source].update(scores_update)

    new_state = {
        "version": new_version,
        "branch": branch,
        "parent": f"v{state['version']}",
        "timestamp": _now(),
        "label": detail[:60] if detail else f"score:{source}",
        "config": dict(state.get("config", {})),
        "scores": new_scores,
        "history": state.get("history", []) + [
            {"at": _now(), "event": f"{source}_score", "detail": detail},
        ],
    }

    label = _write_version(name, new_state)
    _write_head(name, label)

    # Update branch pointer
    branches = _read_branches(name)
    branches[branch] = label
    _write_branches(name, branches)

    return new_state


def rewind(name: str, to_version: int) -> dict:
    """Move HEAD back to a previous version.

    The current HEAD is NOT deleted (history is preserved).
    The rewound version becomes the new HEAD.
    """
    target_label = f"v{to_version}"
    state = _read_version(name, target_label)
    if not state:
        raise ValueError(f"Version {target_label} not found for agent '{name}'")

    state["history"] = state.get("history", []) + [
        {"at": _now(), "event": "rewind", "detail": f"from HEAD to {target_label}"},
    ]
    _write_head(name, target_label)

    # Update main branch pointer
    branches = _read_branches(name)
    branches["main"] = target_label
    _write_branches(name, branches)

    return state


def branch(name: str, branch_name: str) -> dict:
    """Fork current state into a named branch.

    Creates a new version on the branch with the current config.
    HEAD moves to the branch.
    """
    state = current(name)
    if not state:
        raise ValueError(f"Agent '{name}' not initialized")

    # Check branch doesn't already exist
    branches = _read_branches(name)
    if branch_name in branches:
        raise ValueError(f"Branch '{branch_name}' already exists")

    new_version = state["version"] + 1
    new_state = {
        "version": new_version,
        "branch": branch_name,
        "parent": f"v{state['version']}",
        "timestamp": _now(),
        "label": f"branch:{branch_name}",
        "config": dict(state.get("config", {})),
        "scores": dict(state.get("scores", {})),
        "history": state.get("history", []) + [
            {"at": _now(), "event": "branch_created", "detail": branch_name},
        ],
    }

    label = _write_version(name, new_state)
    _write_head(name, f"branch:{branch_name}")

    branches[branch_name] = label
    _write_branches(name, branches)

    return new_state


def switch_branch(name: str, target: str) -> dict:
    """Move HEAD to a branch or specific version.

    target can be:
        "main"           → switch to main branch
        "branch:X"       → switch to branch X
        "v3"             → switch to version 3 directly
    """
    if target == "main":
        branches = _read_branches(name)
        label = branches.get("main", "v1")
        _write_head(name, label)
        return _read_version(name, label)

    if target.startswith("branch:"):
        branch_name = target.split(":", 1)[1]
        branches = _read_branches(name)
        if branch_name not in branches:
            raise ValueError(f"Branch '{branch_name}' not found")
        _write_head(name, target)
        return _read_version(name, branches[branch_name])

    # Direct version reference
    state = _read_version(name, target)
    if not state:
        raise ValueError(f"Version '{target}' not found")
    _write_head(name, target)
    return state


def log(name: str, limit: int = 20) -> List[dict]:
    """Walk the version chain from HEAD backwards."""
    entries = []
    head = _read_head(name)
    if not head:
        return entries

    state = _read_version(name, head)
    while state and len(entries) < limit:
        entries.append({
            "version": state["version"],
            "branch": state.get("branch", "?"),
            "label": state.get("label", ""),
            "timestamp": state.get("timestamp", ""),
            "scores_summary": _summarize_scores(state.get("scores", {})),
        })
        parent = state.get("parent")
        if not parent:
            break
        state = _read_version(name, parent)

    return entries


def list_agents() -> List[str]:
    """List all tracked agent names."""
    if not AGENTS_DIR.exists():
        return []
    return sorted(d.name for d in AGENTS_DIR.iterdir() if d.is_dir())


def agent_summary(name: str) -> Optional[dict]:
    """Get a compact summary of an agent's state."""
    state = current(name)
    if not state:
        return None
    return {
        "name": name,
        "version": state["version"],
        "branch": state.get("branch", "main"),
        "label": state.get("label", ""),
        "config": state.get("config", {}),
        "scores": state.get("scores", {}),
        "history_len": len(state.get("history", [])),
    }


# ── Helpers ──────────────────────────────────────────────────────────────

def _summarize_scores(scores: Dict[str, Any]) -> str:
    """Compact one-line score summary."""
    parts = []
    for source, data in scores.items():
        if isinstance(data, dict):
            avg = data.get("avg", data.get("avg_score", "?"))
            runs = data.get("runs", data.get("sessions", "?"))
            parts.append(f"{source}:{avg}({runs})")
        else:
            parts.append(f"{source}:{data}")
    return " ".join(parts) if parts else "no scores"


def init_known_agents() -> int:
    """Initialize state for all known agents (yvette, forge, hotseat voices)."""
    known = ["yvette", "forge", "hotseat_audrey", "hotseat_claib", "hotseat_vertical"]
    added = 0
    for name in known:
        if not current(name):
            init_agent(name, config={"source": "init_known_agents"})
            added += 1
    return added
