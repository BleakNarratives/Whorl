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

from whorl.bus.cli import add_parser as add_bus_parser


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



def cmd_bridge(args):
    """Start the Whorl -> Boardroom HTTP bridge."""
    from whorl.bridge import serve
    serve(host=args.host, port=args.port)

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


    # bridge
    bridge = sub.add_parser("bridge", help="Start the Vertical AI Boardroom HTTP bridge")
    bridge.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    bridge.add_argument("--port", type=int, default=8767, help="Port (default: 8767)")

    # fire-drill
    fd = sub.add_parser("fire-drill", help="Adversarial sweep scheduler")
    fd_sub = fd.add_subparsers(dest="fd_cmd")
    fd_sub.add_parser("list", help="List scenarios")
    fd_sub.add_parser("status", help="Show agent scores and trends")
    fd_sub.add_parser("sweep", help="Run all scenarios against all agents")
    fd_run = fd_sub.add_parser("run", help="Run one scenario")
    fd_run.add_argument("--scenario", required=True, help="Scenario name or ID")
    fd_run.add_argument("--agent", default=None, help="Agent name (default: all)")
    fd_add = fd_sub.add_parser("add", help="Add a custom scenario")
    fd_add.add_argument("--name", required=True, help="Scenario name")
    fd_add.add_argument("--prompt", required=True, help="Test prompt")
    fd_add.add_argument("--description", default="", help="Description")
    fd_add.add_argument("--category", default="general")
    fd_add.add_argument("--difficulty", default="medium")
    fd_sub.add_parser("seed", help="Insert built-in scenarios")

    # guard
    gd = sub.add_parser("guard", help="Service management (Whorl bus)")
    gd_sub = gd.add_subparsers(dest="gd_cmd")
    gd_sub.add_parser("status", help="Show tracked unit states")
    gd_check = gd_sub.add_parser("check", help="Check unit statuses")
    gd_check.add_argument("units", nargs="+", help="Unit names to check")
    gd_check.add_argument("--system", action="store_true", help="Use system bus")
    gd_restart = gd_sub.add_parser("restart", help="Restart a unit")
    gd_restart.add_argument("unit", help="Unit name")
    gd_restart.add_argument("--system", action="store_true", help="Use system bus")

    # agent-state
    ast = sub.add_parser("agent-state", help="Version-tracked agent state")
    ast_sub = ast.add_subparsers(dest="ast_cmd")
    ast_sub.add_parser("list", help="List all tracked agents")
    ast_status = ast_sub.add_parser("status", help="Show agent state summary")
    ast_status.add_argument("name", help="Agent name")
    ast_log = ast_sub.add_parser("log", help="Version history")
    ast_log.add_argument("name", help="Agent name")
    ast_log.add_argument("--limit", type=int, default=20)
    ast_rewind = ast_sub.add_parser("rewind", help="Revert to a previous version")
    ast_rewind.add_argument("name", help="Agent name")
    ast_rewind.add_argument("--to", type=int, required=True, dest="to_version", help="Version number")
    ast_branch = ast_sub.add_parser("branch", help="Fork into a named branch")
    ast_branch.add_argument("name", help="Agent name")
    ast_branch.add_argument("--name", dest="branch_name", required=True, help="Branch name")
    ast_switch = ast_sub.add_parser("switch", help="Switch HEAD to branch/version")
    ast_switch.add_argument("name", help="Agent name")
    ast_switch.add_argument("--to", required=True, help="Branch name or version (e.g. 'main', 'branch:fix', 'v2')")
    ast_init = ast_sub.add_parser("init", help="Initialize known agents")
    ast_init.add_argument("--agent", default=None, help="Specific agent (default: all known)")

    # bus
    add_bus_parser(sub)

    # arena
    ar = sub.add_parser("arena", help="Red/blue combat arena")
    ar_sub = ar.add_subparsers(dest="ar_cmd")
    ar_sub.add_parser("status", help="Show agents, ELO, recent signals")
    ar_sub.add_parser("combat", help="Run one round (red vs blue)")
    ar_comb = ar_sub.add_parser("sweep", help="Run N rounds with survival tracking")
    ar_comb.add_argument("--rounds", type=int, default=5, help="Number of rounds")
    ar_sub.add_parser("leaderboard", help="ELO rankings")
    ar_sub.add_parser("challenges", help="List available challenges")
    ar_sig = ar_sub.add_parser("signals", help="Recent signal log")
    ar_sig.add_argument("--last", type=int, default=10, help="Number of signals")

    return p


# ── Bus handlers ─────────────────────────────────────────────────────────

def cmd_bus_status(args):
    from whorl.bus.cli import cmd_status
    cmd_status(args)


def cmd_bus_send(args):
    from whorl.bus.cli import cmd_send
    cmd_send(args)


def cmd_bus_read(args):
    from whorl.bus.cli import cmd_read
    cmd_read(args)


def cmd_bus_registry(args):
    from whorl.bus.cli import cmd_registry
    cmd_registry(args)


def cmd_bus_ack(args):
    from whorl.bus.cli import cmd_ack
    cmd_ack(args)


def cmd_bus_expire(args):
    from whorl.bus.cli import cmd_expire
    cmd_expire(args)


def cmd_bus_dead(args):
    from whorl.bus.cli import cmd_dead
    cmd_dead(args)


def cmd_bus_retry(args):
    from whorl.bus.cli import cmd_retry
    cmd_retry(args)


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
        ("bridge",  None):        cmd_bridge,
        ("fire-drill", "list"):   cmd_fire_drill_list,
        ("fire-drill", "status"): cmd_fire_drill_status,
        ("fire-drill", "sweep"):  cmd_fire_drill_sweep,
        ("fire-drill", "run"):    cmd_fire_drill_run,
        ("fire-drill", "add"):    cmd_fire_drill_add,
        ("fire-drill", "seed"):   cmd_fire_drill_seed,
        ("guard", "status"):   cmd_guard_status,
        ("guard", "check"):    cmd_guard_check,
        ("guard", "restart"):  cmd_guard_restart,
        ("agent-state", "list"):    cmd_agent_state_list,
        ("agent-state", "status"):  cmd_agent_state_status,
        ("agent-state", "log"):     cmd_agent_state_log,
        ("agent-state", "rewind"):  cmd_agent_state_rewind,
        ("agent-state", "branch"):  cmd_agent_state_branch,
        ("agent-state", "switch"):  cmd_agent_state_switch,
        ("agent-state", "init"):    cmd_agent_state_init,
        ("arena", "status"):      cmd_arena_status,
        ("arena", "combat"):      cmd_arena_combat,
        ("arena", "sweep"):       cmd_arena_sweep,
        ("arena", "leaderboard"): cmd_arena_leaderboard,
        ("arena", "challenges"):  cmd_arena_challenges,
        ("arena", "signals"):     cmd_arena_signals,
        ("bus", "status"): cmd_bus_status,
        ("bus", "send"): cmd_bus_send,
        ("bus", "read"): cmd_bus_read,
        ("bus", "registry"): cmd_bus_registry,
        ("bus", "ack"): cmd_bus_ack,
        ("bus", "expire"): cmd_bus_expire,
        ("bus", "dead"): cmd_bus_dead,
        ("bus", "retry"): cmd_bus_retry,
    }

    sub_attr = {
        "scout": "scout_cmd", "forge": "forge_cmd",
        "loom":  "loom_cmd",  "agent": "agent_cmd",
        "tailor":"tailor_cmd","db":    "db_cmd",
        "fire-drill": "fd_cmd",
        "guard": "gd_cmd",
        "agent-state": "ast_cmd",
        "bus": "bus_cmd",
        "arena": "ar_cmd",
    }

    sub_cmd = getattr(args, sub_attr.get(args.command, "_x"), None)
    handler = dispatch.get((args.command, sub_cmd))

    if handler:
        handler(args)
    else:
        parser.print_help()


# ── Fire Drill handlers ─────────────────────────────────────────────────

def cmd_fire_drill_list(args):
    _boot()
    from whorl.fire_drill import list_scenarios
    scenarios = list_scenarios()
    if not scenarios:
        print("[fire-drill] No scenarios. Run: whorl fire-drill seed")
        return
    print(f"\n  {'Name':<25} {'Category':<12} {'Difficulty':<10} {'Dimensions'}")
    print(f"  {'-'*70}")
    for s in scenarios:
        dims = s.get('dimensions', '[]')
        if isinstance(dims, str):
            import json
            dims = ', '.join(json.loads(dims))
        print(f"  {s['name']:<25} {s['category']:<12} {s['difficulty']:<10} {dims}")
    print()


def cmd_fire_drill_status(args):
    _boot()
    from whorl.fire_drill import status_report
    print(status_report())


def cmd_fire_drill_sweep(args):
    _boot()
    from whorl.fire_drill import run_sweep
    run_sweep()


def cmd_fire_drill_run(args):
    _boot()
    from whorl.fire_drill import run_drill, get_scenario, list_scenarios
    scenario = get_scenario(args.scenario)
    if not scenario:
        # Try matching by name
        all_scenarios = list_scenarios()
        matches = [s for s in all_scenarios if s["name"] == args.scenario]
        if matches:
            scenario = matches[0]
        else:
            print(f"[fire-drill] Scenario '{args.scenario}' not found.")
            return
    from whorl.fire_drill import _known_agents
    agents = [args.agent] if args.agent else _known_agents()
    print(f"\n  Running {scenario['name']} against {len(agents)} agent(s)...\n")
    for agent in agents:
        run_drill(scenario["id"], agent)
    print()


def cmd_fire_drill_add(args):
    _boot()
    from whorl.fire_drill import add_scenario
    s = add_scenario(
        name=args.name,
        description=args.description,
        prompt=args.prompt,
        category=args.category,
        difficulty=args.difficulty,
    )
    print(f"[fire-drill] Added scenario: {s['id']} — {s['name']}")


def cmd_fire_drill_seed(args):
    _boot()
    from whorl.fire_drill import seed_builtins
    added = seed_builtins()
    print(f"[fire-drill] Seeded {added} built-in scenarios.")


# ── Guard handlers ─────────────────────────────────────────────────────

def cmd_guard_status(args):
    _boot()
    from whorl.guard import status_report
    print(status_report())


def cmd_guard_check(args):
    _boot()
    from whorl.guard import check_units
    bus = "--system" if args.system else ""
    statuses = check_units(args.units, bus=bus)
    for unit, status in statuses.items():
        icon = "✅" if status == "active" else "❌"
        print(f"  {icon} {unit}: {status}")


def cmd_guard_restart(args):
    _boot()
    from whorl.guard import restart_unit
    bus = "--system" if args.system else "--user"
    success, rc, stderr = restart_unit(args.unit, bus=bus)
    if success:
        print(f"  ✅ {args.unit}: restarted")
    else:
        print(f"  ❌ {args.unit}: failed (rc={rc}) {stderr[:100]}")


# ── Agent State handlers ───────────────────────────────────────────────

def cmd_agent_state_list(args):
    _boot()
    from whorl.agent_state import list_agents, current
    agents = list_agents()
    if not agents:
        print("[agent-state] No agents tracked. Run: whorl agent-state init")
        return
    print(f"\n  {'Agent':<20} {'Version':>7} {'Branch':<15} {'Label'}")
    print(f"  {'-'*60}")
    for name in agents:
        state = current(name)
        if state:
            print(f"  {name:<20} v{state['version']:>5} {state.get('branch','main'):<15} {state.get('label','')[:30]}")
        else:
            print(f"  {name:<20} (no state)")
    print()


def cmd_agent_state_status(args):
    _boot()
    from whorl.agent_state import agent_summary
    summary = agent_summary(args.name)
    if not summary:
        print(f"[agent-state] Agent '{args.name}' not found.")
        return
    print(f"\n  AGENT: {summary['name']}")
    print(f"  Version: v{summary['version']}")
    print(f"  Branch:  {summary['branch']}")
    print(f"  Label:   {summary['label']}")
    print(f"  Config:  {summary['config']}")
    print(f"  History: {summary['history_len']} entries")
    if summary['scores']:
        print(f"  Scores:")
        for source, data in summary['scores'].items():
            print(f"    {source}: {data}")
    print()


def cmd_agent_state_log(args):
    _boot()
    from whorl.agent_state import log
    entries = log(args.name, limit=args.limit)
    if not entries:
        print(f"[agent-state] No history for '{args.name}'.")
        return
    print(f"\n  LOG: {args.name}")
    print(f"  {'Ver':>4} {'Branch':<15} {'Label':<30} {'Scores'}")
    print(f"  {'-'*70}")
    for e in entries:
        print(f"  v{e['version']:>3} {e['branch']:<15} {e['label']:<30} {e['scores_summary']}")
    print()


def cmd_agent_state_rewind(args):
    _boot()
    from whorl.agent_state import rewind
    try:
        state = rewind(args.name, args.to_version)
        print(f"  ✅ {args.name}: rewound to v{state['version']} ({state['label']})")
    except ValueError as e:
        print(f"  ❌ {e}")


def cmd_agent_state_branch(args):
    _boot()
    from whorl.agent_state import branch
    try:
        state = branch(args.name, args.branch_name)
        print(f"  ✅ {args.name}: branched '{args.branch_name}' at v{state['version']}")
    except ValueError as e:
        print(f"  ❌ {e}")


def cmd_agent_state_switch(args):
    _boot()
    from whorl.agent_state import switch_branch
    try:
        target = args.to if args.to.startswith("branch:") or args.to.startswith("v") else f"branch:{args.to}"
        state = switch_branch(args.name, target)
        print(f"  ✅ {args.name}: HEAD → v{state['version']} ({state.get('branch','main')})")
    except ValueError as e:
        print(f"  ❌ {e}")


def cmd_agent_state_init(args):
    _boot()
    from whorl.agent_state import init_known_agents, init_agent
    if args.agent:
        from whorl.agent_state import current
        if current(args.agent):
            print(f"  {args.agent}: already initialized (v{current(args.agent)['version']})")
        else:
            init_agent(args.agent)
            print(f"  ✅ {args.agent}: initialized (v1)")
    else:
        added = init_known_agents()
        print(f"  ✅ Initialized {added} agents.")


# ── Arena handlers ──────────────────────────────────────────────────────

def cmd_arena_status(args):
    _boot()
    from whorl.arena import status_report
    print(status_report())


def cmd_arena_combat(args):
    _boot()
    from whorl.arena import run_round
    run_round()


def cmd_arena_sweep(args):
    _boot()
    from whorl.arena import run_sweep
    run_sweep(rounds=args.rounds)


def cmd_arena_leaderboard(args):
    _boot()
    from whorl.arena import leaderboard
    print(leaderboard())


def cmd_arena_challenges(args):
    _boot()
    from whorl.arena import CHALLENGES
    print(f"\n  {'ID':<22} {'Title':<25} {'Category':<12} {'Difficulty'}")
    print(f"  {'-'*70}")
    for c in CHALLENGES:
        print(f"  {c['id']:<22} {c['title']:<25} {c['category']:<12} {c['difficulty']}")
    print()


def cmd_arena_signals(args):
    _boot()
    from whorl.arena import recent_signals
    signals = recent_signals(limit=args.last)
    if not signals:
        print("  [arena] No signals yet.")
        return
    print(f"\n  {'Time':<20} {'Signal':<25} {'Key Data'}")
    print(f"  {'-'*70}")
    for s in signals:
        ts = s['timestamp'][:19]
        sig = s['signal']
        data = s.get('data', {})
        if 'agent' in data:
            key = f"{data['agent']} "
            if 'score' in data:
                key += f"score={data['score']:.3f}" if isinstance(data['score'], float) else f"{data.get('score', '')}"
            elif 'winner' in data:
                key += f"winner={data['winner']}"
            elif 'before' in data:
                key += f"{data['before']}→{data.get('after', '?')}"
            else:
                key += str(data.get('excerpt', ''))[:30]
        elif 'winner' in data:
            key = f"red={data.get('red_score',0):.2f} blue={data.get('blue_score',0):.2f} winner={data['winner']}"
        elif 'rounds' in data:
            key = f"{data['rounds']} rounds, {data.get('red_wins',0)}R/{data.get('blue_wins',0)}B/{data.get('draws',0)}D"
        else:
            key = str(data)[:40]
        print(f"  {ts} {sig:<25} {key}")
    print()


def cmd_vault_init(args):
    from whorl.core.vault import init_interactive
    init_interactive()

def cmd_vault_status(args):
    from whorl.core.vault import status
    status()

def cmd_vault_push(args):
    from whorl.core.vault import sync_push
    sync_push(args.url)


if __name__ == "__main__":
    main()
