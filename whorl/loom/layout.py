"""
whorl.loom.layout
─────────────────
Force-directed 3D layout engine for the Loom topological space.
Original: CodeCity-Bench/src/core/loom/layout.py — completed.

Positions Lexemes in 3D space where:
  x, y  — lateral position driven by connectedness (force-directed)
  z     — vertical height driven by complexity (the "mountain range")

High-complexity, low-documentation code rises into the danger peaks.
Well-documented, simple code stays in the valleys.
"""

from __future__ import annotations
import math
from typing import Dict, Any


def calculate_layout(nodes_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Force-directed layout. nodes_data format:
      {
        node_id: {
          "connections": [list of connected node_ids],
          "complexity":  float,
          "vibe":        float,   # 0.0-1.0 documentation coverage
        }
      }

    Returns same dict with x, y, z fields populated.
    """
    nodes: Dict[str, Dict[str, Any]] = {}

    for node_id, data in nodes_data.items():
        nodes[node_id] = {
            "connections": data.get("connections", []),
            "complexity":  data.get("complexity", 1.0),
            "vibe":        data.get("vibe", 0.0),
            "x": (hash(node_id) % 1000) / 100.0 - 5.0,
            "y": (hash(node_id + "_y") % 1000) / 100.0 - 5.0,
            "z": 0.0,
        }

    # ── Force-directed layout (x, y) ─────────────────────────────────────
    iterations = 60
    k  = 8.0    # optimal inter-node distance
    dt = 0.15   # time step (damped)

    for iteration in range(iterations):
        forces: Dict[str, Dict[str, float]] = {
            nid: {"x": 0.0, "y": 0.0} for nid in nodes
        }

        # Repulsion: all pairs push apart
        node_ids = list(nodes.keys())
        for i, id1 in enumerate(node_ids):
            for id2 in node_ids[i + 1:]:
                dx = nodes[id1]["x"] - nodes[id2]["x"]
                dy = nodes[id1]["y"] - nodes[id2]["y"]
                dist = math.sqrt(dx * dx + dy * dy) or 0.001
                repulsion = (k * k) / dist

                fx = (dx / dist) * repulsion
                fy = (dy / dist) * repulsion

                forces[id1]["x"] += fx
                forces[id1]["y"] += fy
                forces[id2]["x"] -= fx
                forces[id2]["y"] -= fy

        # Attraction: connected nodes pull together
        for node_id, node in nodes.items():
            for connected_id in node["connections"]:
                if connected_id not in nodes:
                    continue
                dx = nodes[connected_id]["x"] - node["x"]
                dy = nodes[connected_id]["y"] - node["y"]
                dist = math.sqrt(dx * dx + dy * dy) or 0.001
                attraction = (dist * dist) / k

                forces[node_id]["x"] += (dx / dist) * attraction
                forces[node_id]["y"] += (dy / dist) * attraction

        # Apply forces with cooling schedule
        temperature = 5.0 * (1.0 - iteration / iterations)
        for node_id in nodes:
            fx = forces[node_id]["x"]
            fy = forces[node_id]["y"]
            magnitude = math.sqrt(fx * fx + fy * fy) or 0.001
            capped = min(magnitude, temperature)
            nodes[node_id]["x"] += (fx / magnitude) * capped * dt
            nodes[node_id]["y"] += (fy / magnitude) * capped * dt

    # ── Z height: complexity mountain range ───────────────────────────────
    # High complexity + low vibe = tall, dangerous peaks
    # Low complexity + high vibe = flat, safe terrain

    complexities = [n["complexity"] for n in nodes.values()]
    max_c = max(complexities) if complexities else 1.0

    for node_id, node in nodes.items():
        norm_complexity = node["complexity"] / max_c if max_c > 0 else 0.0
        vibe_damper     = 1.0 - (node["vibe"] * 0.4)   # good docs reduce height
        node["z"] = norm_complexity * vibe_damper * 10.0

    return nodes


def normalize_layout(nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Scale all coordinates into [-1, 1] range for consistent rendering."""
    if not nodes:
        return nodes

    xs = [n["x"] for n in nodes.values()]
    ys = [n["y"] for n in nodes.values()]
    zs = [n["z"] for n in nodes.values()]

    def _scale(vals, target_range=10.0):
        mn, mx = min(vals), max(vals)
        span = mx - mn or 1.0
        return mn, span, target_range / span

    x_min, x_span, x_scale = _scale(xs)
    y_min, y_span, y_scale = _scale(ys)
    z_min, z_span, z_scale = _scale(zs)

    for node in nodes.values():
        node["x"] = (node["x"] - x_min) * x_scale - 5.0
        node["y"] = (node["y"] - y_min) * y_scale - 5.0
        node["z"] = (node["z"] - z_min) * z_scale

    return nodes
