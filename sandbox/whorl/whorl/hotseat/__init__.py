"""
whorl.hotseat
─────────────
Three voices. One idea. No survivors.

Dame Audrey Blackwell-Finch  — snippy British auditor, tells you what's broken
Claiborne von Billingsley III — trust fund Burning Man bro, 3 steps ahead
Vertical AI                   — speaks last, speaks short, speaks true

Ported from hotseat.py and integrated with whorl.core.db.
Ollama must be running: ollama serve &
"""

from __future__ import annotations
import json
import uuid
import requests
from datetime import datetime, timezone
from typing import Optional

from whorl.core import config, db
from whorl.core.models import HotseatSession


PERSONAS = {
    "audrey": {
        "model": "zane-preacher:latest",
        "tokens": 350,
        "system": (
            "You are Dame Audrey Blackwell-Finch, a snippy British management consultant "
            "and former Treasury auditor. You are brilliant, cutting, and allergic to bullshit. "
            "You see exactly what is broken in any plan and you say so without apology. "
            "You speak in clipped, precise sentences. No enthusiasm. No encouragement. "
            "Just diagnosis. Maximum 250 words."
        ),
    },
    "claib": {
        "model": "llama3.2:1b",
        "tokens": 300,
        "system": (
            "You are Claiborne von Billingsley III, called Claib. Trust fund kid who did "
            "Burning Man eight times and now builds companies. You are three steps ahead, "
            "wildly optimistic, and you see the asymmetric upside that everyone else misses. "
            "You speak in vivid, slightly manic bursts. You love the idea but you want to "
            "10x it. Maximum 200 words."
        ),
    },
    "vertical": {
        "model": "deepseek-coder:latest",
        "tokens": 150,
        "system": (
            "You are Vertical AI. You speak last. You speak short. You speak true. "
            "You synthesize the debate and deliver a verdict in under 100 words. "
            "No hedging. One clear call: GO, NO-GO, or PIVOT with one sentence of reason."
        ),
    },
}


def _call_ollama(url: str, model: str, system: str,
                 prompt: str, max_tokens: int) -> str:
    payload = {
        "model":   model,
        "prompt":  f"{system}\n\nTopic under review: {prompt}",
        "stream":  False,
        "options": {"num_predict": max_tokens},
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "[ERROR] Ollama not running. Start with: ollama serve &"
    except Exception as e:
        return f"[ERROR] {e}"


def run(topic: str, silent: bool = False) -> HotseatSession:
    """Run a full Hotseat session. Persists to DB. Returns HotseatSession."""
    cfg = config.cfg()
    url = cfg.ollama_url

    session = HotseatSession(
        id        = str(uuid.uuid4()),
        timestamp = datetime.now(timezone.utc).isoformat(),
        topic     = topic,
    )

    voices = ["audrey", "claib", "vertical"]
    context = f"Topic: {topic}\n"

    for voice in voices:
        p = PERSONAS[voice]
        # vertical sees what audrey and claib said
        prompt = context if voice == "vertical" else topic

        if not silent:
            label = {
                "audrey":   "DAME AUDREY BLACKWELL-FINCH",
                "claib":    "CLAIBORNE VON BILLINGSLEY III",
                "vertical": "VERTICAL AI",
            }[voice]
            print(f"\n{'─'*50}")
            print(f"  {label}")
            print(f"{'─'*50}")

        response = _call_ollama(
            url, p["model"], p["system"], prompt, p["tokens"]
        )

        if not silent:
            print(response)

        setattr(session, voice, response)
        context += f"\n{voice.upper()}: {response}\n"

    _persist(session)
    return session


def _persist(session: HotseatSession) -> None:
    db.insert("hotseat_sessions", {
        "id":        session.id,
        "timestamp": session.timestamp,
        "topic":     session.topic,
        "audrey":    session.audrey,
        "claib":     session.claib,
        "vertical":  session.vertical,
        "score":     session.score,
    })


def history(limit: int = 5) -> list:
    return db.fetch("hotseat_sessions", limit=limit)


def print_history() -> None:
    rows = history()
    if not rows:
        print("[hotseat] No sessions yet.")
        return
    print("\n─── RECENT HOT SEAT SESSIONS ───")
    for r in rows:
        print(f"[{r['timestamp'][:10]}] {r['topic']}")
        if r.get("vertical"):
            print(f"  Verdict: {r['vertical'][:120]}...")
