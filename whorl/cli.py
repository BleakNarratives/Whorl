#!/usr/bin/env python3
"""
whorl.cli
─────────
THE WORKBENCH. One command. Everything reachable.

Usage:
  whorl status
  whorl scout run
  whorl scout list
  whorl forge pitch --target "RCB Bank" --vertical bank
  whorl forge list
  whorl seat "your idea here"
  whorl seat history
  whorl loom scan ./path/to/code
  whorl agent yvette [--vertical hvac]
  whorl tailor qrd "wall of text"
  whorl tailor intent "raw thought dump"
  whorl db migrate
"""

from __future__ import annotations
import argparse
import sys
from typing import List


# ── Helpers ────────────────────────────────────────────────────────────────

def _banner():
    print("""
 ██╗    ██╗██╗  ██╗ ██████╗ ██████╗ ██╗
 ██║    ██║██║  ██║██╔═══██╗██╔══██╗██║
 ██║ █╗ ██║███████║██║   ██║██████╔╝██║
 ██║███╗██║██╔══██║██║   ██║██╔══██╗██║
 ╚███╔███╔╝██║  ██║╚██████╔╝██║  ██║███████╗
  ╚══╝╚══╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
  Field Intelligence & Agent Deployment Workbench
""")


def _boot():
    """Initialize DB on first run."""
    from whorl.core import db as _db
    _db.migrate()


# ── Subcommand handlers ────────────────────────────────────────────────────

def cmd_status(args):
    from whorl.core import db, config
    from whorl.core.config import WHORL_DIR, DB_PATH, CONFIG_PATH

    _boot()
    cfg = config.cfg()

    print("\n─── WHORL STATUS ───")
    print(f"  Config:   {CONFIG_PATH}")
    print(f"  Database: {DB_PATH}")
    print(f"  Ollama:   {cfg.ollama_url}")
    print(f"  Nostr:    {cfg.nostr_relay}")
    print()

    tables = ["signals", "pitches", "hotseat_sessions", "qrds", "agents"]
    for t in tables:
        try:
            n = db.count(t)
            print(f"  {t:<22} {n:>5} records")
        except Exception:
            print(f"  {t:<22}  (table not found)")
    print()


def cmd_scout_run(args):
    _boot()
    from whorl.scouts import run_sweep
    run_sweep()


def cmd_scout_list(args):
    _boot()
    from whorl.scouts import list_signals
    rows = list_signals(limit=args.limit)
    if not rows:
        print("[scouts] No signals yet.")
        return
    for r in rows:
        print(f"\n[{r['timestamp'][:16]}] {r['signal_class'].upper()} — {r['region']}")
        print(f"  {r['headline']}")
        print(f"  ACTION: {r['action']}")


def cmd_forge_pitch(args):
    _boot()
    from whorl.forge import generate, print_pitch
    from whorl.core.models import Vertical

    try:
        vertical = Vertical(args.vertical.lower())
    except ValueError:
        valid = [v.value for v in Vertical]
        print(f"[forge] Unknown vertical '{args.vertical}'. Choose: {valid}")
        sys.exit(1)

    print(f"[forge] Generating pitch for '{args.target}' ({vertical.value}) ...")
    pitch = generate(
        target    = args.target,
        vertical  = vertical,
        signal_context = args.signal or "",
        extra_context  = args.context or "",
    )
    print_pitch(pitch)


def cmd_forge_list(args):
    _boot()
    from whorl.forge import list_pitches
    rows = list_pitches(limit=args.limit)
    if not rows:
        print("[forge] No pitches yet.")
        return
    for r in rows:
        print(f"[{r['timestamp'][:10]}] {r['target']} ({r['vertical']})  →  {r['hook'][:60]}")


def cmd_seat(args):
    _boot()
    from whorl.hotseat import run, print_history
    if args.topic:
        run(args.topic)
    else:
        print_history()


def cmd_loom_scan(args):
    _boot()
    # CodeCity-Bench lives in whorl/loom — import when ready
    print(f"[loom] Scanning {args.path} ...")
    print("[loom] (CodeCity-Bench integration — see whorl/loom/)")


def cmd_agent_yvette(args):
    _boot()
    from whorl.agents.yvette import interactive_session
    from whorl.core.models import Vertical

    vertical = Vertical.HVAC
    if args.vertical:
        try:
            vertical = Vertical(args.vertical.lower())
        except ValueError:
            pass

    interactive_session(vertical=vertical)


def cmd_tailor_qrd(args):
    _boot()
    from whorl.tailor import qrd, print_qrd
    if not args.text:
        print("[tailor] Provide text: whorl tailor qrd \"your wall of text\"")
        sys.exit(1)
    record = qrd(args.text)
    print_qrd(record)


def cmd_tailor_intent(args):
    _boot()
    from whorl.tailor import parse_intent
    import json
    if not args.thought:
        print("[tailor] Provide thought: whorl tailor intent \"I need to...\"")
        sys.exit(1)
    result = parse_intent(args.thought)
    print(json.dumps(result, indent=2))


def cmd_db_migrate(args):
    from whorl.core import db
    db.migrate()
    print("[db] Migrations applied.")


# ── Argument parser ────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whorl",
        description="WHORL — Field Intelligence & Agent Deployment Workbench",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version="whorl 0.1.0")
    sub = p.add_subparsers(dest="command")

    # status
    sub.add_parser("status", help="Show system status and DB record counts")

    # scout
    scout = sub.add_parser("scout", help="Intelligence feed operations")
    scout_sub = scout.add_subparsers(dest="scout_cmd")
    scout_sub.add_parser("run", help="Run a scout sweep")
    sl = scout_sub.add_parser("list", help="List recent signals")
    sl.add_argument("--limit", type=int, default=10)

    # forge
    forge = sub.add_parser("forge", help="Pitch generation engine")
    forge_sub = forge.add_subparsers(dest="forge_cmd")
    fp = forge_sub.add_parser("pitch", help="Generate a pitch")
    fp.add_argument("--target",   required=True, help="Business name")
    fp.add_argument("--vertical", required=True, help="bank|restaurant|hvac|plumber|realestate|general")
    fp.add_argument("--signal",   help="Optional signal context")
    fp.add_argument("--context",  help="Optional extra context")
    fl = forge_sub.add_parser("list", help="List recent pitches")
    fl.add_argument("--limit", type=int, default=10)

    # seat
    seat = sub.add_parser("seat", help="Run an idea through Hotseat")
    seat.add_argument("topic", nargs="?", default=None,
                      help="The idea to stress-test (omit for history)")

    # loom
    loom = sub.add_parser("loom", help="CodeCity-Bench code topology")
    loom_sub = loom.add_subparsers(dest="loom_cmd")
    ls = loom_sub.add_parser("scan", help="Scan a codebase")
    ls.add_argument("path", help="Path to scan")

    # agent
    agent = sub.add_parser("agent", help="Deploy and interact with agents")
    agent_sub = agent.add_subparsers(dest="agent_cmd")
    ay = agent_sub.add_parser("yvette", help="Interactive session with Yvette")
    ay.add_argument("--vertical", default="hvac",
                    help="hvac|plumber|restaurant (default: hvac)")

    # tailor
    tailor = sub.add_parser("tailor", help="QRD engine and intent parser")
    tailor_sub = tailor.add_subparsers(dest="tailor_cmd")
    tq = tailor_sub.add_parser("qrd", help="Generate a Quick Rundown")
    tq.add_argument("text", help="Text to summarize")
    ti = tailor_sub.add_parser("intent", help="Parse a raw thought into a plan")
    ti.add_argument("thought", help="Raw thought to parse")

    # db
    dbc = sub.add_parser("db", help="Database operations")
    db_sub = dbc.add_subparsers(dest="db_cmd")
    db_sub.add_parser("migrate", help="Run pending DB migrations")

    return p


# ── Entry point ────────────────────────────────────────────────────────────

def main(argv: List[str] = None):
    parser = build_parser()
    args   = parser.parse_args(argv)

    if not args.command:
        _banner()
        parser.print_help()
        return

    dispatch = {
        ("status",  None):        cmd_status,
        ("scout",   "run"):       cmd_scout_run,
        ("scout",   "list"):      cmd_scout_list,
        ("forge",   "pitch"):     cmd_forge_pitch,
        ("forge",   "list"):      cmd_forge_list,
        ("seat",    None):        cmd_seat,
        ("loom",    "scan"):      cmd_loom_scan,
        ("agent",   "yvette"):    cmd_agent_yvette,
        ("tailor",  "qrd"):       cmd_tailor_qrd,
        ("tailor",  "intent"):    cmd_tailor_intent,
        ("db",      "migrate"):   cmd_db_migrate,
    }

    sub_attr = {
        "scout": "scout_cmd", "forge": "forge_cmd",
        "loom":  "loom_cmd",  "agent": "agent_cmd",
        "tailor":"tailor_cmd","db":    "db_cmd",
    }

    sub_cmd = getattr(args, sub_attr.get(args.command, "_x"), None)
    handler = dispatch.get((args.command, sub_cmd))

    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

def cmd_vault_init(args):
    from whorl.core.vault import init_interactive
    init_interactive()

def cmd_vault_status(args):
    from whorl.core.vault import status
    status()

def cmd_vault_push(args):
    from whorl.core.vault import sync_push
    sync_push(args.url)
