#!/usr/bin/env python3
"""Whorl Demo Harness — side-by-side: naive prompting vs the Whorl pipeline.

The brief: "Sixty seconds, same input, with and without."

  LEFT  — naive: dump straight into an LLM, print whatever comes back
          (the "LLM with extra steps" baseline everyone will accuse you of)
  RIGHT — Whorl: MindaIntent parser -> structured IR -> Signal Loom signals
          -> bounded intervention plan -> scored verdict

Run:
    python3 demo_intent_compare.py                 # default scenarios
    python3 demo_intent_compare.py --once          # single scenario, fast
    python3 demo_intent_compare.py --input "your chaotic thought dump"

Output: a side-by-side text panel + a JSON record per run (demo_results.jsonl)
so the comparison can be diffed across runs and rendered later.

DNA_TAG: ORIGIN=BleakNarratives/Whorl | ROLE=demo-harness | LAST_SYNC=2026-08-29
"""

from __future__ import annotations

import argparse
import os
import pathlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import sys as _sys

_here = str(Path(__file__).resolve().parent)
if _here not in _sys.path:
    _sys.path.insert(0, _here)

from whorl.tailor import parse_intent  # noqa: E402
from whorl.signal_loom import CATEGORIES, SEVERITIES  # noqa: E402

# ---------------------------------------------------------------------------
# Scenarios: chaotic thought dumps where naive prompting tends to lose the
# thread (mixed domains, mixed urgency, buried constraints).
# ---------------------------------------------------------------------------

SCENARIOS: List[Dict[str, str]] = [
    {
        "id": "hvac_dual_urgency",
        "dump": (
            "ok so the van AC compressor died again mid-route, third time since june, "
            "and mrs. alvarez is waiting on her install tomorrow 9am so I can't take "
            "the van in until friday, but frankie wants his furnace quote by thursday "
            "and I promised the rossi job would start monday. also my kid has a "
            "recital thursday 6pm. the compressor is like 900 bucks plus labor and "
            "I'm already thin on october cash flow. do I rent a van? do I push frankie?"
        ),
    },
    {
        "id": "buried_constraint",
        "dump": (
            "long day. fixed the perez walk-in finally, compressor relay was toast. "
            "note to self: mrs. alvarez is allergic to latex so no rubber gaskets on "
            "her install, order the silicone ones. frankie's quote still pending, he "
            "wants it under 4k or he goes with whoever's cheaper. oh and the rossi "
            "monday start depends on the permit clearing friday. recital thursday 6pm "
            "non-negotiable. cash flow is the real issue, october is thin."
        ),
    },
    {
        "id": "contradictory_priorities",
        "dump": (
            "frankie says under 4k or he walks. rossi wants monday but the permit "
            "won't clear until friday so that's impossible unless I pull the crew off "
            "alvarez. alvarez install can't slip again, third reschedule, she'll "
            "cancel the contract. I said I'd be at the recital. I always say that. "
            "quote needs to go out tonight or frankie goes with whoever's cheaper. "
            "compressor rental is 900. october cash is thin. what do I do first."
        ),
    },
]

# ---------------------------------------------------------------------------
# LEFT: naive baseline — one raw LLM call, no structure, no memory
# ---------------------------------------------------------------------------

NAIVE_SYSTEM = (
    "You are a helpful assistant. The user will give you a messy brain-dump "
    "about their work. Respond helpfully."
)


def _load_groq_key() -> Optional[str]:
    """Read the Groq key from Whorl's vault (secrets.toml) or env."""
    key_path = Path.home() / ".whorl" / "secrets.toml"
    if key_path.exists():
        try:
            import toml

            key = toml.loads(key_path.read_text()).get("api_keys", {}).get("groq")
            if key:
                return key
        except Exception:
            pass
    key = os.environ.get("GROQ_API_KEY")
    return key or None


def _llm_raw(prompt: str, system: str, timeout: int = 45) -> str:
    """Minimal direct LLM call (Groq), used only for the naive baseline."""
    import requests

    key = _load_groq_key()
    if not key:
        raise RuntimeError(
            "No Groq key for naive baseline — set GROQ_API_KEY or ~/.whorl/secrets.toml"
        )

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def run_naive(dump: str) -> Dict:
    """Baseline: one raw call, no structure, no memory, no lifecycle."""
    t0 = time.monotonic()
    try:
        text = _llm_raw(dump, NAIVE_SYSTEM)
        ok = True
    except Exception as e:
        text = f"[naive baseline failed: {e}]"
        ok = False
    return {
        "side": "naive",
        "ok": ok,
        "text": text,
        "latency_s": round(time.monotonic() - t0, 2),
    }


# ---------------------------------------------------------------------------
# RIGHT: Whorl pipeline — parse -> IR -> signals -> bounded plan
# ---------------------------------------------------------------------------

def _intent_to_signals(intent: Dict) -> List[Dict]:
    """Deterministic mapping from MindaIntent IR to Signal Loom signals."""
    signals = []
    urgency = float(intent.get("urgency", 0.0))
    constraints = intent.get("constraints") or []
    paths = intent.get("execution_paths") or []

    if urgency >= 0.7:
        signals.append(
            {
                "category": "workflow",
                "severity": "critical" if urgency >= 0.85 else "high",
                "detail": f"core_intent urgency {urgency}: {intent.get('core_intent', '')[:80]}",
            }
        )
    for c in constraints[:5]:
        signals.append(
            {
                "category": "workflow",
                "severity": "moderate",
                "detail": f"constraint: {str(c)[:70]}",
            }
        )
    if not paths:
        signals.append(
            {
                "category": "workflow",
                "severity": "moderate",
                "detail": "no execution paths extracted — intent may be underspecified",
            }
        )
    if not signals:
        signals.append(
            {
                "category": "workflow",
                "severity": "informational",
                "detail": "no urgent signals from intent",
            }
        )
    return signals


def _plan_from_signals(signals: List[Dict]) -> List[Dict]:
    """Deterministic, bounded intervention plan from ranked signals."""
    sev_rank = {
        s: i
        for i, s in enumerate(["informational", "low", "moderate", "high", "critical"])
    }
    ranked = sorted(signals, key=lambda s: -sev_rank.get(s.get("severity", "low"), 0))
    plan = []
    for i, s in enumerate(ranked[:5], 1):
        plan.append(
            {
                "order": i,
                "category": s.get("category", "workflow"),
                "severity": s.get("severity", "low"),
                "action": s.get("detail", ""),
                "bounded": True,
            }
        )
    return plan


def run_whorl(dump: str) -> Dict:
    """Whorl pipeline: parse -> IR -> signals -> bounded plan."""
    t0 = time.monotonic()
    try:
        intent = parse_intent(dump)
        signals = _intent_to_signals(intent)
        plan = _plan_from_signals(signals)
        ok = True
    except Exception as e:
        intent, signals = {}, []
        plan = [
            {
                "order": 1,
                "category": "error",
                "severity": "critical",
                "action": f"pipeline failed: {e}",
                "bounded": False,
            }
        ]
        ok = False
    return {
        "side": "whorl",
        "ok": ok,
        "intent": intent,
        "signals": signals,
        "plan": plan,
        "latency_s": round(time.monotonic() - t0, 2),
    }


# ---------------------------------------------------------------------------
# Rendering + persistence
# ---------------------------------------------------------------------------

def render_side_by_side(naive: Dict, whorl: Dict) -> str:
    lines = []
    lines.append("=" * 78)
    lines.append(
        "LEFT: NAIVE (raw LLM, no structure)".ljust(39)
        + "| RIGHT: WHORL (intent -> IR -> plan)"
    )
    lines.append("=" * 78)

    n_lines = (naive.get("text") or "").splitlines() or [""]
    w_plan = whorl.get("plan") or []

    max_h = max(len(n_lines), len(w_plan), 1)
    for i in range(max_h):
        left = n_lines[i] if i < len(n_lines) else ""
        if i < len(w_plan):
            p = w_plan[i]
            right = f"[{p.get('severity', '?'):>12}] {p.get('action', '')[:45]}"
        else:
            right = ""
        lines.append(f"{left[:37]:<37} | {right[:38]}")
    lines.append("=" * 78)
    lines.append(
        f"naive latency: {naive.get('latency_s', '?')}s".ljust(39)
        + f"| whorl latency: {whorl.get('latency_s', '?')}s"
    )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Whorl side-by-side demo")
    ap.add_argument("--once", action="store_true", help="run only the first scenario")
    ap.add_argument("--input", default=None, help="custom thought-dump text")
    ap.add_argument("--out", default="demo_results.jsonl", help="JSONL output path")
    args = ap.parse_args()

    scenarios = SCENARIOS[:1] if args.once else SCENARIOS
    if args.input:
        scenarios = [{"id": "custom", "dump": args.input}]

    out_path = Path(__file__).resolve().parent / args.out
    for sc in scenarios:
        run_id = uuid.uuid4().hex[:8]
        ts = datetime.now(timezone.utc).isoformat()
        print(f"\n### scenario: {sc['id']} (run {run_id}) ###")
        print(f"INPUT: {sc['dump'][:100]}{'...' if len(sc['dump']) > 100 else ''}\n")

        naive = run_naive(sc["dump"])
        whorl = run_whorl(sc["dump"])
        print(render_side_by_side(naive, whorl))

        record = {
            "run_id": run_id,
            "ts": ts,
            "scenario_id": sc["id"],
            "input": sc["dump"],
            "naive": naive,
            "whorl": whorl,
        }
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"[saved] {out_path.name} run_id={run_id}")


if __name__ == "__main__":
    main()
