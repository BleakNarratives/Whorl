#!/usr/bin/env python3
"""
whorl.bridge
────────────
HTTP bridge between the Vertical AI Boardroom frontend and the Whorl workbench.

Exposes the boardroom-compatible JSON contract the Three.js frontend expects,
while routing every request through Whorl modules (hotseat, forge, tailor,
scouts).  Uses vault.load_api_keys() as the unified key source — no hardcoded
credentials anywhere.

Usage (standalone):
    python -m whorl.bridge [--port 8767] [--host 127.0.0.1]

Usage (via CLI):
    whorl bridge [--port 8767] [--host 127.0.0.1]

Endpoints:
    GET  /status            — liveness + Whorl module inventory + DB counts
    POST /convene           — full boardroom session via HotseatSession
    POST /forge             — generate a vertical sales pitch
    POST /tailor/qrd        — tiered QRD summary of a block of text
    POST /tailor/intent     — parse a raw thought into a structured plan
    GET  /scouts            — return recent scout signals
    POST /scouts/ingest     — ingest raw text into the scout pipeline
    GET  /bearings          — return agent Bearing vectors (x/y/z/cw/ccw)
"""

from __future__ import annotations

import argparse
import json
import traceback
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib.parse import urlparse

# ── Whorl module availability map ─────────────────────────────────────────────
_WHORL_OK: Dict[str, bool] = {}


def _try_import(name: str):
    try:
        mod = __import__(name, fromlist=["_"])
        _WHORL_OK[name] = True
        return mod
    except Exception as exc:
        _WHORL_OK[name] = False
        print(f"[whorl.bridge] WARNING: could not import {name}: {exc}")
        return None


_hotseat = _try_import("whorl.hotseat")
_forge   = _try_import("whorl.forge")
_tailor  = _try_import("whorl.tailor")
_scouts  = _try_import("whorl.scouts")
_models  = _try_import("whorl.core.models")
_db      = _try_import("whorl.core.db")

if _db:
    try:
        _db.migrate()
    except Exception as e:
        print(f"[whorl.bridge] DB migration warning: {e}")


# ── Bearing config ─────────────────────────────────────────────────────────────
#   x: 0=local  1=regional  2=national  3=global
#   y: 0=surface  1=analysis  2=synthesis  3=strategy
#   z: 0=read-only  1=draft  2=send  3=deploy
#   cw=escalate  ccw=delegate
AGENT_BEARINGS: Dict[str, Dict[str, Any]] = {
    "cfo":   {"x": 2, "y": 3, "z": 1, "cw": True,  "ccw": False,
              "label": "CFO",
              "desc": "National scope / Strategy depth / Draft exec — escalates, holds capital gate"},
    "cmo":   {"x": 3, "y": 2, "z": 2, "cw": False, "ccw": True,
              "label": "CMO",
              "desc": "Global scope / Synthesis depth / Send exec — delegates outbound campaigns"},
    "cro":   {"x": 1, "y": 2, "z": 1, "cw": True,  "ccw": False,
              "label": "CRO",
              "desc": "Regional scope / Synthesis depth / Draft exec — escalates pipeline gaps"},
    "mkt":   {"x": 2, "y": 1, "z": 0, "cw": False, "ccw": False,
              "label": "ANALYST",
              "desc": "National scope / Analysis depth / Read-only — surfaces comps, never acts"},
    "devil": {"x": 3, "y": 3, "z": 2, "cw": True,  "ccw": True,
              "label": "DEVIL'S ADVOCATE",
              "desc": "Global scope / Strategy depth / Send exec — full escalate + delegate"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    try:
        return json.loads(handler.rfile.read(length))
    except Exception:
        return {}


# ── HotseatSession → boardroom adapter ───────────────────────────────────────

def _split_voice(text: str, max_chunks: int = 2) -> list:
    text = text.strip()
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paras) >= 2:
        return paras[:max_chunks]
    sentences = [s.strip() + "." for s in text.rstrip(".").split(". ") if s.strip()]
    if len(sentences) >= 4:
        mid = len(sentences) // 2
        return [" ".join(sentences[:mid]), " ".join(sentences[mid:])]
    return [text]


def _map_hotseat_to_boardroom(session, brief: str, agent_map: Dict[str, str]) -> dict:
    """
    audrey  → CFO + CRO   (auditor / risk voice)
    claib   → CMO + DEVIL (optimist / wildcard)
    vertical → ANALYST    (synthesis + verdict)
    """
    debate = []

    if session.audrey:
        chunks = _split_voice(session.audrey)
        debate.append({"agent": agent_map.get("audrey_cfo", "CFO"), "argument": chunks[0]})
        if len(chunks) >= 2:
            debate.append({"agent": agent_map.get("audrey_cro", "CRO"), "argument": chunks[1]})

    if session.claib:
        chunks = _split_voice(session.claib)
        debate.append({"agent": agent_map.get("claib_cmo",   "CMO"),   "argument": chunks[0]})
        if len(chunks) >= 2:
            debate.append({"agent": agent_map.get("claib_devil", "DEVIL"), "argument": chunks[1]})

    if session.vertical:
        chunks = _split_voice(session.vertical)
        debate.append({"agent": agent_map.get("vertical_analyst", "ANALYST"), "argument": chunks[0]})

    v_upper = (session.vertical or "").upper()
    if "NO-GO" in v_upper or "NO GO" in v_upper:
        verdict = "no-go"
    elif v_upper.strip().startswith("GO") or " GO." in v_upper or " GO," in v_upper:
        verdict = "go"
    elif "PIVOT" in v_upper:
        verdict = "conditional"
    else:
        verdict = "conditional"

    champion_name = {"go": "CMO", "no-go": "CFO"}.get(verdict, "ANALYST")
    champion_text = session.claib if verdict == "go" else session.audrey

    return {
        "boardroom": {
            "debate": debate,
            "synthesis": {
                "verdict":    verdict,
                "consensus":  session.vertical or "Board has deliberated.",
                "hotseat_id": session.id,
            },
        },
        "champion":  {"name": champion_name, "thesis": (champion_text or "")[:140]},
        "session_id": session.id,
    }


def _sim_boardroom(brief: str) -> dict:
    """Canned simulation — bridge stays live without Ollama."""
    import random
    agents = ["CFO", "CMO", "CRO", "ANALYST", "DEVIL"]
    lines = {
        "CFO":    f"[SIM/CFO] Unit economics first. What is the CAC and payback period for: {brief[:60]}?",
        "CMO":    "[SIM/CMO] Nobody here has talked to a real customer yet. One conversation before any model.",
        "CRO":    "[SIM/CRO] Single supplier dependency is the landmine on month four. Found it.",
        "ANALYST":"[SIM/ANALYST] Comparable exits in this vertical: 2-3x revenue. The 10x model is narrative.",
        "DEVIL":  "[SIM/DEVIL] The CFO argument is strongest in the room. So I am about to destroy it.",
    }
    verdict = random.choice(["go", "no-go", "conditional"])
    return {
        "boardroom": {
            "debate": [{"agent": a, "argument": lines[a]} for a in agents],
            "synthesis": {
                "verdict":    verdict,
                "consensus":  "Simulation mode — start Whorl + Ollama for live deliberation.",
                "hotseat_id": None,
            },
        },
        "champion":  {"name": "ANALYST", "thesis": "Data first, always."},
        "session_id": "sim_" + str(uuid.uuid4())[:8],
    }


# ── Request handler ───────────────────────────────────────────────────────────

class BoardroomHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in ("200", "204"):
            super().log_message(fmt, *args)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")
        {"/status": self._handle_status,
         "/scouts": self._handle_scouts,
         "/bearings": self._handle_bearings,
        }.get(path, lambda: _json_response(self, {"error": "not found"}, 404))()

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        {"/convene":       self._handle_convene,
         "/forge":         self._handle_forge,
         "/tailor/qrd":    self._handle_tailor_qrd,
         "/tailor/intent": self._handle_tailor_intent,
         "/scouts/ingest": self._handle_scouts_ingest,
        }.get(path, lambda: _json_response(self, {"error": "not found"}, 404))()

    def _handle_status(self):
        modules = {k.replace("whorl.", ""): v for k, v in _WHORL_OK.items()}
        db_counts = {}
        if _db and _WHORL_OK.get("whorl.core.db"):
            for t in ["signals", "pitches", "hotseat_sessions", "qrds", "agents"]:
                try:
                    db_counts[t] = _db.count(t)
                except Exception:
                    db_counts[t] = -1
        _json_response(self, {
            "status":    "online",
            "version":   "whorl.bridge 1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modules":   modules,
            "db":        db_counts,
            "bearings":  AGENT_BEARINGS,
        })

    def _handle_convene(self):
        body  = _read_body(self)
        brief = body.get("brief", "").strip()
        if not brief:
            _json_response(self, {"error": "brief is required"}, 400)
            return

        enriched = brief
        if _tailor and _WHORL_OK.get("whorl.tailor"):
            try:
                intent = _tailor.parse_intent(brief)
                core   = intent.get("core_intent", "")
                domain = intent.get("domain_hint", "")
                if core and core.lower() != brief.lower():
                    enriched = f"{brief}\n\n[TAILOR: domain={domain}, intent={core}]"
            except Exception as e:
                print(f"[whorl.bridge] Tailor pre-process skipped: {e}")

        if _hotseat and _WHORL_OK.get("whorl.hotseat"):
            try:
                session = _hotseat.run(enriched, silent=True)
                result = _map_hotseat_to_boardroom(session, brief, {
                    "audrey_cfo": "CFO", "audrey_cro": "CRO",
                    "claib_cmo": "CMO", "claib_devil": "DEVIL",
                    "vertical_analyst": "ANALYST",
                })
                _json_response(self, result)
                return
            except Exception as e:
                print(f"[whorl.bridge] Hotseat error: {e}")
                traceback.print_exc()

        _json_response(self, _sim_boardroom(brief))

    def _handle_forge(self):
        body     = _read_body(self)
        target   = body.get("target", "").strip()
        vertical = body.get("vertical", "general").strip().lower()
        if not target:
            _json_response(self, {"error": "target is required"}, 400)
            return
        if not (_forge and _WHORL_OK.get("whorl.forge")):
            _json_response(self, {"error": "forge module unavailable"}, 503)
            return
        if not (_models and _WHORL_OK.get("whorl.core.models")):
            _json_response(self, {"error": "models module unavailable"}, 503)
            return
        try:
            vert_enum = _models.Vertical(vertical)
        except (ValueError, AttributeError):
            vert_enum = _models.Vertical.GENERAL
        try:
            p = _forge.generate(target=target, vertical=vert_enum,
                                signal_context=body.get("signal_context", ""),
                                extra_context=body.get("extra_context", ""))
            _json_response(self, {
                "id": p.id, "target": p.target, "vertical": p.vertical.value,
                "hook": p.hook, "situation": p.situation, "risk": p.risk,
                "fix": p.fix, "ask": p.ask, "cost": p.cost, "guarantee": p.guarantee,
            })
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    def _handle_tailor_qrd(self):
        body = _read_body(self)
        text = body.get("text", "").strip()
        if not text:
            _json_response(self, {"error": "text is required"}, 400)
            return
        if not (_tailor and _WHORL_OK.get("whorl.tailor")):
            _json_response(self, {"error": "tailor module unavailable"}, 503)
            return
        try:
            r = _tailor.qrd(text, source_id=body.get("source_id", "boardroom"))
            _json_response(self, {"id": r.id, "blink": r.blink, "brief": r.brief, "deep": r.deep})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    def _handle_tailor_intent(self):
        body    = _read_body(self)
        thought = body.get("thought", "").strip()
        if not thought:
            _json_response(self, {"error": "thought is required"}, 400)
            return
        if not (_tailor and _WHORL_OK.get("whorl.tailor")):
            _json_response(self, {"error": "tailor module unavailable"}, 503)
            return
        try:
            _json_response(self, _tailor.parse_intent(thought))
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    def _handle_scouts(self):
        if not (_scouts and _WHORL_OK.get("whorl.scouts")):
            _json_response(self, {"signals": [], "error": "scouts module unavailable"})
            return
        try:
            _json_response(self, {"signals": _scouts.list_signals(limit=20)})
        except Exception as e:
            _json_response(self, {"signals": [], "error": str(e)})

    def _handle_scouts_ingest(self):
        body = _read_body(self)
        raw  = body.get("raw", "").strip()
        if not raw:
            _json_response(self, {"error": "raw is required"}, 400)
            return
        if not (_scouts and _WHORL_OK.get("whorl.scouts")):
            _json_response(self, {"error": "scouts module unavailable"}, 503)
            return
        try:
            signals = _scouts.ingest_text(raw)
            _json_response(self, {"ingested": len(signals),
                                   "signals": [{"id": s.id, "headline": s.headline} for s in signals]})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, {"error": str(e)}, 500)

    def _handle_bearings(self):
        _json_response(self, {"bearings": AGENT_BEARINGS})


# ── Server bootstrap ──────────────────────────────────────────────────────────

_BANNER = """
 ██╗    ██╗██╗  ██╗ ██████╗ ██████╗ ██╗
 ██║    ██║██║  ██║██╔═══██╗██╔══██╗██║
 ██║ █╗ ██║███████║██║   ██║██████╔╝██║
 ██║███╗██║██╔══██║██║   ██║██╔══██╗██║
 ╚███╔███╔╝██║  ██║╚██████╔╝██║  ██║███████╗
  ╚══╝╚══╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
  Boardroom Bridge — {addr}
"""


def serve(host: str = "127.0.0.1", port: int = 8767) -> None:
    print(_BANNER.format(addr=f"http://{host}:{port}"))
    print("[whorl.bridge] Module status:")
    for name, ok in _WHORL_OK.items():
        print(f"  {'OK' if ok else 'UNAVAILABLE':<14} {name}")
    print(f"\n[whorl.bridge] Listening on http://{host}:{port}")
    print("[whorl.bridge] Open vertical_ai_boardroom_3d.html -> PING BRIDGE\n")
    server = HTTPServer((host, port), BoardroomHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[whorl.bridge] Shutting down.")
        server.server_close()


def main(argv=None) -> None:
    """Entry point for `whorl bridge` CLI subcommand and `python -m whorl.bridge`."""
    parser = argparse.ArgumentParser(
        prog="whorl bridge",
        description="Start the Whorl -> Vertical AI Boardroom HTTP bridge",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args(argv)
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
