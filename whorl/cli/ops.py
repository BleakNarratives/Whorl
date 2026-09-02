# [DNA_TAG]
# ORIGIN: Moto4_A9
# PILLAR: cli
# DEPS: whorl.fire_drill, whorl.guard
# ROLE: Whorl CLI — ops command groups (fire-drill, guard)
# LAST_SYNC: 2026-09-02T04:00:00Z
# [/DNA_TAG]

"""Ops whorl commands: fire-drill and guard."""

from __future__ import annotations

from whorl.cli.runtime import boot


# ── Fire Drill handlers ─────────────────────────────────────────────────

def cmd_fire_drill_list(args):
    boot()
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
    boot()
    from whorl.fire_drill import status_report
    print(status_report())


def cmd_fire_drill_sweep(args):
    boot()
    from whorl.fire_drill import run_sweep
    run_sweep()


def cmd_fire_drill_run(args):
    boot()
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
    boot()
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
    boot()
    from whorl.fire_drill import seed_builtins
    added = seed_builtins()
    print(f"[fire-drill] Seeded {added} built-in scenarios.")


# ── Guard handlers ─────────────────────────────────────────────────────

def cmd_guard_status(args):
    boot()
    from whorl.guard import status_report
    print(status_report())


def cmd_guard_check(args):
    boot()
    from whorl.guard import check_units
    bus = "--system" if args.system else ""
    statuses = check_units(args.units, bus=bus)
    for unit, status in statuses.items():
        icon = "✅" if status == "active" else "❌"
        print(f"  {icon} {unit}: {status}")


def cmd_guard_restart(args):
    boot()
    from whorl.guard import restart_unit
    bus = "--system" if args.system else "--user"
    success, rc, stderr = restart_unit(args.unit, bus=bus)
    if success:
        print(f"  ✅ {args.unit}: restarted")
    else:
        print(f"  ❌ {args.unit}: failed (rc={rc}) {stderr[:100]}")
