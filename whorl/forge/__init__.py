"""
whorl.forge
───────────
Pitch engine. Takes a target + vertical + optional signal context,
calls Ollama, returns a structured Pitch object.

Domain intel is loaded from whorl/forge/verticals/ JSON files.
"""

from __future__ import annotations
import json
import uuid
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from whorl.core import config, db
from whorl.core.models import Pitch, Vertical

# ── Vertical intel (domain context) ───────────────────────────────────────

VERTICAL_INTEL = {
    Vertical.BANK: {
        "avg_missed_call_cost": 3200,
        "annual_missed_loss":   704000,
        "competitors":          "Chase, Wells, Intrust",
        "pain":                 "Losing 18-34 year olds to online banks. Invisible on Google.",
        "hook":                 "Your missed calls are stealing $3,200 each.",
    },
    Vertical.RESTAURANT: {
        "avg_margin":           "3-9%",
        "delivery_commission":  "15-30%",
        "unanswered_calls_pct": "62%",
        "pain":                 "Third-party delivery eating margins. No online ordering = 20-30% revenue loss.",
        "hook":                 "DoorDash is charging you 30% to sell your own food.",
    },
    Vertical.HVAC: {
        "avg_ticket":           450,
        "calls_per_month":      300,
        "current_conversion":   "35%",
        "pain":                 "Missed after-hours calls. No dispatch coverage at 2 AM.",
        "hook":                 "Every missed call at 2 AM is a $450 job going to your competitor.",
    },
    Vertical.PLUMBER: {
        "avg_service_call":     "175-450",
        "emergency_premium":    "1.5-2x",
        "lead_gen_fee":         "15-25%",
        "pain":                 "No-shows, price shoppers, slow seasons, missed emergency calls.",
        "hook":                 "Your best customers call at midnight. Are you there?",
    },
    Vertical.REALESTATE: {
        "signal":               "34% spike in pre-foreclosure listings",
        "region":               "Metro Atlanta, GA",
        "pain":                 "Cash buyers can't find motivated sellers fast enough.",
        "hook":                 "There are 34% more motivated sellers in this market than 90 days ago.",
    },
}

SYSTEM_PROMPT = """You are FORGE, a precision sales pitch writer for small and mid-size businesses.

You write in a specific format — direct, operator-to-operator, no corporate fluff.
Every word earns its place. You write like someone who has worked the job, not sold to it.

Output strict JSON with these keys:
situation, risk, fix, ask, hook, cost, guarantee

Rules:
- situation: what you found (specific, researched)
- risk: the cost of inaction (quantified when possible)
- fix: what you build (concrete, not abstract)
- ask: the call to action (specific time, no commitment)
- hook: one devastating sentence the target will remember
- cost: monthly price
- guarantee: the risk reversal

Return ONLY the JSON object. No preamble. No markdown."""


def generate(
    target: str,
    vertical: Vertical,
    signal_context: str = "",
    extra_context: str = "",
) -> Pitch:
    """Generate a pitch via Ollama and persist to DB."""
    cfg  = config.cfg()
    intel = VERTICAL_INTEL.get(vertical, {})

    user_prompt = f"""
TARGET: {target}
VERTICAL: {vertical.value}
DOMAIN INTEL: {json.dumps(intel, indent=2)}
SIGNAL CONTEXT: {signal_context or 'None'}
EXTRA CONTEXT: {extra_context or 'None'}

Write a pitch for {target}.
""".strip()

    raw_response = _call_ollama(
        cfg.ollama_url,
        cfg.model.get("model_forge", "llama3.2:1b"),
        SYSTEM_PROMPT,
        user_prompt,
        max_tokens=600,
    )

    parsed = _parse_response(raw_response)

    pitch = Pitch(
        id        = str(uuid.uuid4()),
        timestamp = datetime.now(timezone.utc).isoformat(),
        target    = target,
        vertical  = vertical,
        situation = parsed.get("situation", ""),
        risk      = parsed.get("risk", ""),
        fix       = parsed.get("fix", ""),
        ask       = parsed.get("ask", ""),
        hook      = parsed.get("hook", ""),
        cost      = parsed.get("cost", ""),
        guarantee = parsed.get("guarantee", ""),
        raw       = raw_response,
    )

    _persist(pitch)
    return pitch


def _call_ollama(url: str, model: str, system: str,
                 prompt: str, max_tokens: int = 600) -> str:
    payload = {
        "model":  model,
        "prompt": f"{system}\n\n{prompt}",
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    try:
        r = requests.post(url, json=payload, timeout=90)
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        return json.dumps({"error": str(e)})


def _parse_response(raw: str) -> dict:
    """Extract JSON from model output."""
    import re
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {"situation": raw, "risk": "", "fix": "",
                "ask": "", "hook": "", "cost": "", "guarantee": ""}


def _persist(pitch: Pitch) -> None:
    db.insert("pitches", {
        "id":        pitch.id,
        "timestamp": pitch.timestamp,
        "target":    pitch.target,
        "vertical":  pitch.vertical.value,
        "situation": pitch.situation,
        "risk":      pitch.risk,
        "fix":       pitch.fix,
        "ask":       pitch.ask,
        "hook":      pitch.hook,
        "cost":      pitch.cost,
        "guarantee": pitch.guarantee,
        "raw":       pitch.raw,
    })


def list_pitches(limit: int = 20) -> list:
    return db.fetch("pitches", limit=limit)


def print_pitch(pitch: Pitch) -> None:
    width = 60
    print("=" * width)
    print(f"PITCH REPORT: {pitch.target.upper()}")
    print(f"VERTICAL: {pitch.vertical.value.upper()}")
    print(f"GENERATED: {pitch.timestamp[:10]}")
    print("=" * width)
    print(f"\nTHE SITUATION\n{pitch.situation}")
    print(f"\nTHE RISK\n{pitch.risk}")
    print(f"\nTHE FIX\n{pitch.fix}")
    print(f"\nTHE ASK\n{pitch.ask}")
    print(f"\nCOST: {pitch.cost}")
    print(f"GUARANTEE: {pitch.guarantee}")
    print(f"\nTHE HOOK\n{pitch.hook}")
    print("=" * width)
