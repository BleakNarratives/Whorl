# [DNA_TAG]
# ORIGIN: Moto4_A9
# PILLAR: cli
# DEPS: whorl.core, whorl.scouts, whorl.forge, whorl.hotseat, whorl.loom, whorl.agents, whorl.tailor, whorl.bridge
# ROLE: Whorl CLI — core command group (status/scout/forge/seat/loom/agent/tailor/db/bridge)
# LAST_SYNC: 2026-09-02T04:00:00Z
# [/DNA_TAG]

"""Core whorl commands: status, scout, forge, seat, loom, agent, tailor, db, bridge."""

from __future__ import annotations

import sys

from whorl.cli.runtime import boot


def cmd_status(args):
    from whorl.core import db, config
    from whorl.core.config import WHORL_DIR, DB_PATH, CONFIG_PATH

    boot()
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
    boot()
    from whorl.scouts import run_sweep
    run_sweep()


def cmd_scout_list(args):
    boot()
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
    boot()
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
    boot()
    from whorl.forge import list_pitches
    rows = list_pitches(limit=args.limit)
    if not rows:
        print("[forge] No pitches yet.")
        return
    for r in rows:
        print(f"[{r['timestamp'][:10]}] {r['target']} ({r['vertical']})  →  {r['hook'][:60]}")


def cmd_seat(args):
    boot()
    from whorl.hotseat import run, print_history
    if args.topic:
        run(args.topic)
    else:
        print_history()


def cmd_loom_scan(args):
    boot()
    from whorl.loom import scan
    scan(args.path)


def cmd_agent_yvette(args):
    boot()
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
    boot()
    from whorl.tailor import qrd, print_qrd
    if not args.text:
        print("[tailor] Provide text: whorl tailor qrd \"your wall of text\"")
        sys.exit(1)
    record = qrd(args.text)
    print_qrd(record)


def cmd_tailor_intent(args):
    boot()
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


def cmd_bridge(args):
    """Start the Whorl -> Boardroom HTTP bridge."""
    from whorl.bridge import serve
    serve(host=args.host, port=args.port)
