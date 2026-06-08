"""
whorl.tailor
QRD Engine + MindaIntent parser.
Uses APIs when available, falls back to Ollama local.
"""

from __future__ import annotations
import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from whorl.core import db
from whorl.core.config import cfg, load_api_keys
from whorl.core.models import QRD


QRD_SYSTEM = """You are the Tailor. Produce exactly four tiers:

BLINK: One sentence. 30 seconds. The single most important takeaway.
BRIEF: 3-5 sentences. 2 minutes. Key context, one action item, one risk.
DEEP: Structured analysis. 10 minutes. Sections: Situation, Options, Recommendation, Risks, First Action.
FULL: "See original input."

Output strict JSON with keys: blink, brief, deep, full. No markdown in values."""

INTENT_SYSTEM = """You are the MindaIntent parser. Extract structured intent from chaotic thought dumps.

Output strict JSON:
{"domain_hint": "plumber|auto_dealer|convenience|general", "urgency": 0.0, "emotional_valence": -1.0, "constraints": [], "core_intent": "...", "execution_paths": [{"name": "...", "description": "...", "estimated_hours": 0, "requires_api": false}], "resources_needed": [], "confidence": 0.0}"""


_KEYS = None

def _keys():
    global _KEYS
    if _KEYS is None:
        _KEYS = load_api_keys()
    return _KEYS


def _call_llm(prompt, system, model=None):
    keys = _keys()
    
    if keys.get("openai"):
        try:
            r = requests.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {keys['openai']}", "Content-Type": "application/json"},
                json={"model": model or "gpt-4o-mini", "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.3},
                timeout=30)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[tailor] OpenAI failed: {e}")
    
    if keys.get("groq"):
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {keys['groq']}", "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.3},
                timeout=15)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[tailor] Groq failed: {e}")
    
    if keys.get("mistral"):
        try:
            r = requests.post("https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {keys['mistral']}", "Content-Type": "application/json"},
                json={"model": "mistral-small-latest", "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.3},
                timeout=20)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[tailor] Mistral failed: {e}")
    
    if keys.get("gemini"):
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={keys['gemini']}",
                json={"contents": [{"parts": [{"text": system + "\n\n" + prompt}]}]},
                timeout=20)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[tailor] Gemini failed: {e}")
    
    try:
        r = requests.post(cfg().ollama_url,
            json={"model": cfg().model.get("model_tailor", "llama3.2:1b"), "prompt": f"{system}\n\n{prompt}", "stream": False, "options": {"temperature": 0.3}},
            timeout=120)
        r.raise_for_status()
        return r.json()["response"]
    except Exception as e:
        raise RuntimeError(f"All LLM providers failed. Last error: {e}")


def _extract_json(text):
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def qrd(text, source_id=""):
    raw = _call_llm(text, QRD_SYSTEM)
    data = _extract_json(raw)
    record = QRD(
        id=str(uuid.uuid4())[:8],
        timestamp=datetime.now().isoformat(),
        source_id=source_id or "manual",
        blink=data.get("blink", "No summary generated."),
        brief=data.get("brief", "No brief generated."),
        deep=data.get("deep", "No deep analysis generated."),
        full=data.get("full", "See original input."))
    db.insert("qrds", record.__dict__)
    return record


def parse_intent(thought):
    raw = _call_llm(thought, INTENT_SYSTEM)
    return _extract_json(raw)


def print_qrd(record):
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        console.print(Panel(record.blink, title="[bold cyan]BLINK[/bold cyan] (30 sec)", border_style="cyan"))
        console.print(Panel(record.brief, title="[bold green]BRIEF[/bold green] (2 min)", border_style="green"))
        console.print(Panel(record.deep, title="[bold yellow]DEEP[/bold yellow] (10 min)", border_style="yellow"))
        console.print(Panel(record.full, title="[bold dim]FULL[/bold dim] (unbounded)", border_style="dim"))
    except ImportError:
        print("\n" + "="*50)
        print(f"  BLINK (30 sec)  [{record.id}]")
        print("="*50)
        print(f"  {record.blink}\n")
        print("="*50)
        print("  BRIEF (2 min)")
        print("="*50)
        print(f"  {record.brief}\n")
        print("="*50)
        print("  DEEP (10 min)")
        print("="*50)
        print(f"  {record.deep}\n")
        print("="*50)
        print("  FULL")
        print("="*50)
        print(f"  {record.full}\n")
