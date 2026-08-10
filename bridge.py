#!/usr/bin/env python3
"""
whorl.bridge
────────────
HTTP bridge over the Loomy runtime & shared state.

Declared in pyproject.toml as the `whorl-bridge` console script but never
implemented. This is the helical-world counterpart to the legacy
`whorl/whorl/bridge/` boardroom bridge: it exposes Loomy state, agent
bearings, loom scan history, and the External Context Drive over JSON.

Endpoints:
    GET  /            — index of routes
    GET  /status      — runtime health + module inventory
    GET  /state       — full shared state snapshot
    GET  /bearings    — agent bearing vectors
    GET  /loom        — recent loom scan records
    GET  /memory      — External Context Drive usage
    GET  /healthz     — liveness probe

Usage:
    python3 -m whorl.bridge [--host 127.0.0.1] [--port 8767]
    whorl-bridge [--host 127.0.0.1] [--port 8767]
"""

from __future__ import annotations
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib.parse import urlparse


# ── module availability (lazy — the bridge stays up if a dep is missing) ─

def _try_import(name: str):
    try:
        return __import__(name, fromlist=["_"])
    except Exception:
        return None


_core = _try_import("whorl.core")
_loom = _try_import("whorl.loom")
_memory = _try_import("whorl.memory")


def _state_snapshot() -> Dict[str, Any]:
    if not _core:
        return {"error": "whorl.core unavailable"}
    try:
        state = _core.SharedState()
        return {
            "path": state.filepath,
            "stats": state.stats(),
            "keys": state.keys(),
            "snapshot": state.snapshot(),
        }
    except Exception as e:
        return {"error": str(e)}


def _bearings() -> Dict[str, Any]:
    if not _core:
        return {"error": "whorl.core unavailable"}
    try:
        from whorl.core.bearing import Bearing
        return {
            "legend": {
                "X (data)": "CW: READ/COPY/OBSERVE · CCW: REMOVE/CONSUME",
                "Y (scope)": "CW: SPECIFIC · CCW: WILDCARD",
                "Z (transform)": "CW: WEAVE/COMPILE · CCW: UNRAVEL/DECOMPILE",
            },
            "factories": {
                name: cls().to_dict()
                for name, cls in [
                    ("stasis", Bearing.stasis),
                    ("observe", Bearing.observe),
                    ("observe_broad", Bearing.observe_broad),
                    ("consume", Bearing.consume),
                    ("weave", Bearing.weave),
                    ("unravel", Bearing.unravel),
                    ("full_send", Bearing.full_send),
                    ("dismantle", Bearing.dismantle),
                ]
            },
        }
    except Exception as e:
        return {"error": str(e)}


def _loom_history() -> Dict[str, Any]:
    if not _loom:
        return {"error": "whorl.loom unavailable"}
    try:
        return {"scans": _loom.history(limit=10)}
    except Exception as e:
        return {"error": str(e)}


def _memory_usage() -> Dict[str, Any]:
    if not _memory:
        return {"error": "whorl.memory unavailable"}
    try:
        drive = _memory.ContextExpander()
        return drive.usage()
    except Exception as e:
        return {"error": str(e)}


class LoomyBridgeHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in ("200", "204", "404"):
            super().log_message(fmt, *args)

    def _json(self, data: Any, status: int = 200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        routes = {
            "/":        lambda: self._json({
                "name": "whorl-bridge",
                "version": "0.1.0-alpha",
                "routes": ["/status", "/state", "/bearings", "/loom", "/memory", "/healthz"],
            }),
            "/status":  lambda: self._json({
                "status": "online",
                "version": "0.1.0-alpha",
                "modules": {
                    "core": bool(_core),
                    "loom": bool(_loom),
                    "memory": bool(_memory),
                },
            }),
            "/state":   lambda: self._json(_state_snapshot()),
            "/bearings": lambda: self._json(_bearings()),
            "/loom":    lambda: self._json(_loom_history()),
            "/memory":  lambda: self._json(_memory_usage()),
            "/healthz": lambda: self._json({"status": "ok"}, 200),
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self._json({"error": "not found"}, 404)


_BANNER = """
 ██╗    ██╗██╗  ██╗ ██████╗ ██████╗ ██╗
 ██║    ██║██║  ██║██╔═══██╗██╔══██╗██║
 ██║ █╗ ██║███████║██║   ██║██████╔╝██║
 ██║███╗██║██╔══██║██║   ██║██╔══██╗██║
 ╚███╔███╔╝██║  ██║╚██████╔╝██║  ██║███████╗
  ╚══╝╚══╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
  Loomy Bridge — {addr}
"""


def serve(host: str = "127.0.0.1", port: int = 8767) -> None:
    print(_BANNER.format(addr=f"http://{host}:{port}"))
    print("[whorl.bridge] modules:", {
        "core": bool(_core), "loom": bool(_loom), "memory": bool(_memory),
    })
    print(f"[whorl.bridge] listening on http://{host}:{port}\n")
    server = HTTPServer((host, port), LoomyBridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[whorl.bridge] shutting down")
        server.server_close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="whorl-bridge",
        description="HTTP bridge over the Loomy runtime & shared state",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args(argv)
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main(sys.argv[1:])
