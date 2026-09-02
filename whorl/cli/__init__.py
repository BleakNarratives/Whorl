# [DNA_TAG]
# ORIGIN: Moto4_A9
# PILLAR: cli
# DEPS: whorl.cli.runtime, whorl.cli.core, whorl.cli.ops, whorl.cli.agents, whorl.cli.bus, whorl.bus.cli
# ROLE: Whorl CLI — parser, dispatch, entry point (facade over whorl.cli package)
# LAST_SYNC: 2026-09-02T04:00:00Z
# [/DNA_TAG]

"""
whorl.cli — THE WORKBENCH. One command. Everything reachable.

Split into a package (rescue item 3):
  runtime.py  — banner + DB boot helpers
  core.py     — status/scout/forge/seat/loom/agent/tailor/db/bridge
  ops.py      — fire-drill/guard
  agents.py   — agent-state/arena/vault
  bus.py      — bus shims
This facade keeps ``whorl.cli:main`` (pyproject console script) and every
``cmd_*`` name importable at the old paths.
"""

from __future__ import annotations

import argparse
from typing import List

from whorl.bus.cli import add_parser as add_bus_parser

from whorl.cli.runtime import banner as _banner
from whorl.cli.runtime import boot as _boot
from whorl.cli import core, ops, agents, bus

# ── cmd_* compatibility surface (old flat names) ─────────────────────────
# Re-exported so any external caller doing ``from whorl.cli import cmd_status``
# keeps working after the package split.

cmd_status = core.cmd_status
cmd_scout_run = core.cmd_scout_run
cmd_scout_list = core.cmd_scout_list
cmd_forge_pitch = core.cmd_forge_pitch
cmd_forge_list = core.cmd_forge_list
cmd_seat = core.cmd_seat
cmd_loom_scan = core.cmd_loom_scan
cmd_agent_yvette = core.cmd_agent_yvette
cmd_tailor_qrd = core.cmd_tailor_qrd
cmd_tailor_intent = core.cmd_tailor_intent
cmd_db_migrate = core.cmd_db_migrate
cmd_bridge = core.cmd_bridge

cmd_fire_drill_list = ops.cmd_fire_drill_list
cmd_fire_drill_status = ops.cmd_fire_drill_status
cmd_fire_drill_sweep = ops.cmd_fire_drill_sweep
cmd_fire_drill_run = ops.cmd_fire_drill_run
cmd_fire_drill_add = ops.cmd_fire_drill_add
cmd_fire_drill_seed = ops.cmd_fire_drill_seed
cmd_guard_status = ops.cmd_guard_status
cmd_guard_check = ops.cmd_guard_check
cmd_guard_restart = ops.cmd_guard_restart

cmd_agent_state_list = agents.cmd_agent_state_list
cmd_agent_state_status = agents.cmd_agent_state_status
cmd_agent_state_log = agents.cmd_agent_state_log
cmd_agent_state_rewind = agents.cmd_agent_state_rewind
cmd_agent_state_branch = agents.cmd_agent_state_branch
cmd_agent_state_switch = agents.cmd_agent_state_switch
cmd_agent_state_init = agents.cmd_agent_state_init
cmd_arena_status = agents.cmd_arena_status
cmd_arena_combat = agents.cmd_arena_combat
cmd_arena_sweep = agents.cmd_arena_sweep
cmd_arena_leaderboard = agents.cmd_arena_leaderboard
cmd_arena_challenges = agents.cmd_arena_challenges
cmd_arena_signals = agents.cmd_arena_signals
cmd_vault_init = agents.cmd_vault_init
cmd_vault_status = agents.cmd_vault_status
cmd_vault_push = agents.cmd_vault_push

cmd_bus_status = bus.cmd_bus_status
cmd_bus_send = bus.cmd_bus_send
cmd_bus_read = bus.cmd_bus_read
cmd_bus_registry = bus.cmd_bus_registry
cmd_bus_ack = bus.cmd_bus_ack
cmd_bus_expire = bus.cmd_bus_expire
cmd_bus_dead = bus.cmd_bus_dead
cmd_bus_retry = bus.cmd_bus_retry


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

    # vault (handlers existed but were never wired — now live)
    vt = sub.add_parser("vault", help="Whorl secret vault operations")
    vt_sub = vt.add_subparsers(dest="vault_cmd")
    vt_sub.add_parser("init", help="Initialize the vault interactively")
    vt_sub.add_parser("status", help="Show vault status")
    vp = vt_sub.add_parser("push", help="Push vault to a sync URL")
    vp.add_argument("url", help="Sync target URL")

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
        ("status",  None):        core.cmd_status,
        ("scout",   "run"):       core.cmd_scout_run,
        ("scout",   "list"):      core.cmd_scout_list,
        ("forge",   "pitch"):     core.cmd_forge_pitch,
        ("forge",   "list"):      core.cmd_forge_list,
        ("seat",    None):        core.cmd_seat,
        ("loom",    "scan"):      core.cmd_loom_scan,
        ("agent",   "yvette"):    core.cmd_agent_yvette,
        ("tailor",  "qrd"):       core.cmd_tailor_qrd,
        ("tailor",  "intent"):    core.cmd_tailor_intent,
        ("db",      "migrate"):   core.cmd_db_migrate,
        ("bridge",  None):        core.cmd_bridge,
        ("fire-drill", "list"):   ops.cmd_fire_drill_list,
        ("fire-drill", "status"): ops.cmd_fire_drill_status,
        ("fire-drill", "sweep"):  ops.cmd_fire_drill_sweep,
        ("fire-drill", "run"):    ops.cmd_fire_drill_run,
        ("fire-drill", "add"):    ops.cmd_fire_drill_add,
        ("fire-drill", "seed"):   ops.cmd_fire_drill_seed,
        ("guard", "status"):   ops.cmd_guard_status,
        ("guard", "check"):    ops.cmd_guard_check,
        ("guard", "restart"):  ops.cmd_guard_restart,
        ("agent-state", "list"):    agents.cmd_agent_state_list,
        ("agent-state", "status"):  agents.cmd_agent_state_status,
        ("agent-state", "log"):     agents.cmd_agent_state_log,
        ("agent-state", "rewind"):  agents.cmd_agent_state_rewind,
        ("agent-state", "branch"):  agents.cmd_agent_state_branch,
        ("agent-state", "switch"):  agents.cmd_agent_state_switch,
        ("agent-state", "init"):    agents.cmd_agent_state_init,
        ("arena", "status"):      agents.cmd_arena_status,
        ("arena", "combat"):      agents.cmd_arena_combat,
        ("arena", "sweep"):       agents.cmd_arena_sweep,
        ("arena", "leaderboard"): agents.cmd_arena_leaderboard,
        ("arena", "challenges"):  agents.cmd_arena_challenges,
        ("arena", "signals"):     agents.cmd_arena_signals,
        ("vault", "init"):        agents.cmd_vault_init,
        ("vault", "status"):      agents.cmd_vault_status,
        ("vault", "push"):        agents.cmd_vault_push,
        ("bus", "status"): bus.cmd_bus_status,
        ("bus", "send"): bus.cmd_bus_send,
        ("bus", "read"): bus.cmd_bus_read,
        ("bus", "registry"): bus.cmd_bus_registry,
        ("bus", "ack"): bus.cmd_bus_ack,
        ("bus", "expire"): bus.cmd_bus_expire,
        ("bus", "dead"): bus.cmd_bus_dead,
        ("bus", "retry"): bus.cmd_bus_retry,
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
        "vault": "vault_cmd",
    }

    sub_cmd = getattr(args, sub_attr.get(args.command, "_x"), None)
    handler = dispatch.get((args.command, sub_cmd))

    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
