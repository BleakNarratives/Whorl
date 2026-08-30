"""
whorl.tailor
────────────
The QRD Engine. Takes any dense output — pitch, hotseat session,
signal blob — and produces tiered summaries:

  BLINK   — 30 seconds, one decision
  BRIEF   — 2 minutes, context + recommendation
  DEEP    — 10 minutes, full analysis
  FULL    — unabridged (passthrough)

Also houses the MindaIntent parser: raw thought → structured plan.
"""

from __future__ import annotations
import json
import re
import uuid
import requests
from datetime import datetime, timezone
from typing import Optional

from whorl.core import config, db
from whorl.core.models import QRD


QRD_SYSTEM = """You are the Tailor. Your job is to make dense information digestible.

You receive raw text — could be a pitch, an intel report, a debate transcript — and
you produce three summaries at different depths.

Output strict JSON with these keys:
  blink  — one sentence. Decision-forcing. Under 20 words.
  brief  — 3-4 sentences. Context + recommendation. Under 80 words.
  deep   — full paragraph. Analysis with nuance. Under 300 words.

Return ONLY the JSON. No preamble. No markdown fences."""


MINDA_SYSTEM = """You are Kimi, co-creator with Minda.
Minda speaks in raw, passionate, sometimes chaotic terms.
Your job is to translate Minda's raw statement into a structured execution plan.

Constraints are sacred:
  - If Minda says "no cost" → do not propose AWS
  - If Minda says "today" → scope to hours, not weeks
  - If Minda says "phone only" → no desktop tools

Output strict JSON with:
  intent     — what Minda actually wants (one sentence)
  urgency    — high / medium / low
  constraint — the non-negotiable limits
  steps      — array of concrete next actions (max 5)
  blocker    — what could stop this (one sentence)

Return ONLY the JSON."""


def _call_ollama(url: str, model: str, system: str,
                 prompt: str, max_tokens: int = 800) -> str:
    payload = {
        "model":   model,
        "prompt":  f"{system}\n\n{prompt}",
        "stream":  False,
        "options": {"num_predict": max_tokens},
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return json.dumps({"error": str(e)})


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {"raw": raw}


def qrd(source_text: str, source_id: str = "") -> QRD:
    """Generate a QRD from any text blob. Persists to DB."""
    cfg   = config.cfg()
    model = cfg.model.get("model_tailor", "deepseek-coder:latest")

    raw  = _call_ollama(cfg.ollama_url, model, QRD_SYSTEM, source_text)
    data = _parse_json(raw)

    record = QRD(
        id        = str(uuid.uuid4()),
        timestamp = datetime.now(timezone.utc).isoformat(),
        source_id = source_id,
        blink     = data.get("blink", ""),
        brief     = data.get("brief", ""),
        deep      = data.get("deep", ""),
        full      = source_text,
    )

    db.insert("qrds", {
        "id":        record.id,
        "timestamp": record.timestamp,
        "source_id": record.source_id,
        "blink":     record.blink,
        "brief":     record.brief,
        "deep":      record.deep,
        "full":      record.full,
    })

    return record


def parse_intent(raw_thought: str) -> dict:
    """
    MindaIntent parser. Raw → structured execution plan.
    Usage: whorl tailor intent "I need to pitch the HVAC guy today no budget"
    """
    cfg   = config.cfg()
    model = cfg.model.get("model_tailor", "deepseek-coder:latest")
    raw   = _call_ollama(cfg.ollama_url, model, MINDA_SYSTEM, raw_thought)
    return _parse_json(raw)


def print_qrd(record: QRD) -> None:
    print(f"\n{'═'*55}")
    print(f"  QRD [{record.timestamp[:10]}]")
    print(f"{'═'*55}")
    print(f"\n  BLINK  →  {record.blink}")
    print(f"\n  BRIEF\n  {record.brief}")
    print(f"\n  DEEP\n  {record.deep}")
    print(f"{'─'*55}")
