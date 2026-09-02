# [DNA_TAG]
# ORIGIN: Moto4_A9
# PILLAR: cli
# DEPS: whorl.agent_state, whorl.arena, whorl.core.vault
# ROLE: Whorl CLI — agents groups (agent-state, arena, vault)
# LAST_SYNC: 2026-09-02T04:00:00Z
# [/DNA_TAG]

"""Agent whorl commands: agent-state, arena, and vault (previously dead)."""

from __future__ import annotations

from whorl.cli.runtime import boot


# ── Agent State handlers ───────────────────────────────────────────────

def cmd_agent_state_list(args):
    boot()
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
    boot()
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
    boot()
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
    boot()
    from whorl.agent_state import rewind
    try:
        state = rewind(args.name, args.to_version)
        print(f"  ✅ {args.name}: rewound to v{state['version']} ({state['label']})")
    except ValueError as e:
        print(f"  ❌ {e}")


def cmd_agent_state_branch(args):
    boot()
    from whorl.agent_state import branch
    try:
        state = branch(args.name, args.branch_name)
        print(f"  ✅ {args.name}: branched '{args.branch_name}' at v{state['version']}")
    except ValueError as e:
        print(f"  ❌ {e}")


def cmd_agent_state_switch(args):
    boot()
    from whorl.agent_state import switch_branch
    try:
        target = args.to if args.to.startswith("branch:") or args.to.startswith("v") else f"branch:{args.to}"
        state = switch_branch(args.name, target)
        print(f"  ✅ {args.name}: HEAD → v{state['version']} ({state.get('branch','main')})")
    except ValueError as e:
        print(f"  ❌ {e}")


def cmd_agent_state_init(args):
    boot()
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
    boot()
    from whorl.arena import status_report
    print(status_report())


def cmd_arena_combat(args):
    boot()
    from whorl.arena import run_round
    run_round()


def cmd_arena_sweep(args):
    boot()
    from whorl.arena import run_sweep
    run_sweep(rounds=args.rounds)


def cmd_arena_leaderboard(args):
    boot()
    from whorl.arena import leaderboard
    print(leaderboard())


def cmd_arena_challenges(args):
    boot()
    from whorl.arena import CHALLENGES
    print(f"\n  {'ID':<22} {'Title':<25} {'Category':<12} {'Difficulty'}")
    print(f"  {'-'*70}")
    for c in CHALLENGES:
        print(f"  {c['id']:<22} {c['title']:<25} {c['category']:<12} {c['difficulty']}")
    print()


def cmd_arena_signals(args):
    boot()
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


# ── Vault handlers (existed unwired; now live) ─────────────────────────

def cmd_vault_init(args):
    from whorl.core.vault import init_interactive
    init_interactive()


def cmd_vault_status(args):
    from whorl.core.vault import status
    status()


def cmd_vault_push(args):
    from whorl.core.vault import sync_push
    sync_push(args.url)
