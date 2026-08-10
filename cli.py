#!/usr/bin/env python3
"""
whorl.cli
─────────
THE WORKBENCH. The command surface the README always claimed existed.

Restores the full CLI documented across the project:

    python3 -m whorl --help
    python3 -m whorl --version
    python3 -m whorl loom scan <path>          # code-topology scan (read-only)
    python3 -m whorl run <file.whr>            # run a whorl program
    python3 -m whorl demo | demo-knot          # bundled demos
    python3 -m whorl bearing <x> <y> <z>       # interpret a bearing
    python3 -m whorl state                     # inspect shared state
    python3 -m whorl decompile --from py --to bash "print('hi')"
    python3 -m whorl agents                    # agents of the last run
    python3 -m whorl memory status|stretch|drive|cycle
    python3 -m whorl gate ...                  # Weight-Vest Gate (Hat 1)
    python3 -m whorl weave|unweave|inspect ... # Helix-Speak at-rest (Hat 3)
    python3 -m whorl drift [--snapshot]        # Orbit Vane (Hat 2)
    python3 -m whorl bicameral 'q'             # THE COMMITTEE — two voices, one narrator
    python3 -m whorl tailor qrd|intent|shadow  # THE TAILOR — QRD + MindaIntent + Cognitive Shadow
    python3 -m whorl mind ...                  # delegate to whorl.mind
    python3 -m whorl swarm [--manifest N]      # ShipWrekDOS gathering
    python3 -m whorl legacy <cmd>              # Field-Intel Workbench (whorl/whorl)
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from typing import List, Optional


# ── helpers ───────────────────────────────────────────────────────────────

def _print_banner():
    print("""
 ██╗    ██╗██╗  ██╗ ██████╗ ██████╗ ██╗
 ██║    ██║██║  ██║██╔═══██╗██╔══██╗██║
 ██║ █╗ ██║███████║██║   ██║██████╔╝██║
 ██║███╗██║██╔══██║██║   ██║██╔══██╗██║
 ╚███╔███╔╝██║  ██║╚██████╔╝██║  ██║███████╗
  ╚══╝╚══╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
  Helical Agentic Language — Loomy Workbench
""")


def _resolve_state_path(path: Optional[str]) -> str:
    """Default state lives in ~/.whorl/state.json; explicit paths are jailed."""
    return path or os.path.expanduser("~/.whorl/state.json")


# ── bearing ───────────────────────────────────────────────────────────────

def cmd_bearing(args):
    """Interpret a bearing triple as intent. Easter egg included."""
    from whorl.core.bearing import Bearing, Rotation

    def _rot(tok: str) -> Rotation:
        t = tok.lower()
        if t in ("cw", "1", "+1"):
            return Rotation.CW
        if t in ("ccw", "-1"):
            return Rotation.CCW
        return Rotation.STATIC

    x = _rot(args.x)
    y = _rot(args.y)
    z = _rot(args.z)
    bearing = Bearing(x=x, y=y, z=z, speed=args.speed)

    print(bearing.visual())
    print(f"  intent: {bearing.summary}")

    if bearing == Bearing.full_send():
        print("\n  🥚 FULL SEND. Every axis, every tooth. The loom remembers this one.")


# ── state ─────────────────────────────────────────────────────────────────

def cmd_state(args):
    """Inspect the shared state store."""
    from whorl.core.state import SharedState
    state = SharedState(_resolve_state_path(args.path))

    if args.json:
        print(json.dumps(state.snapshot(), indent=2, default=str))
        return

    stats = state.stats()
    print(f"\n  state file: {state.filepath}")
    print(f"  keys:       {stats['keys']}")
    print(f"  versions:   {stats.get('total_versions', 0)}")
    print(f"  oldest:     {stats['oldest_key']}")
    print(f"  newest:     {stats['newest_key']}")
    print()

    for key in state.keys():
        value = state.read(key)
        v_str = json.dumps(value, default=str) if not isinstance(value, str) else value
        if len(v_str) > 80:
            v_str = v_str[:77] + "..."
        print(f"  {key} = {v_str}")

    if not state.keys():
        print("  (empty)")


# ── decompile ─────────────────────────────────────────────────────────────

def cmd_decompile(args):
    """Polyglot transpile through the shared IR."""
    from whorl.tools.decompiler import get_decompiler
    dc = get_decompiler()
    print(dc.transpile(args.source, from_lang=args.from_lang, to_lang=args.to_lang))


# ── run (restores the loomy.py run command) ──────────────────────────────

def _run_program(program_path: str, state_path: str, ticks: Optional[int] = None,
                 delay: Optional[float] = None, verbose: bool = True):
    """Parse a .whr file and execute it on the Loomy runtime."""
    from whorl.lang import load_whorl
    from whorl.core.runtime import Loomy

    program = load_whorl(program_path)

    loomy = Loomy(
        state_path=state_path,
        tick_delay=delay if delay is not None else program.tick_delay,
        max_ticks=ticks or program.run_ticks,
        verbose=verbose,
    )

    # Seed initial state
    for key, value in program.state.items():
        loomy.state.write(key, value, "whorl-cli:seed")

    # Spawn agents
    for agent_def in program.agents:
        loomy.spawn(
            agent_id=agent_def.agent_id,
            bearing=agent_def.bearing,
            role=agent_def.role,
        )

    print(f"\n[whorl] running {program_path}: {len(program.agents)} agents, "
          f"{program.run_ticks or '∞'} ticks\n")
    loomy.run(ticks=ticks, tick_delay=delay)
    print()
    print(loomy.report())
    return loomy


def cmd_run(args):
    if not os.path.exists(args.file):
        print(f"[whorl] no such program: {args.file}")
        print("        try: python3 -m whorl run ../demo.whr")
        sys.exit(1)
    _run_program(args.file, _resolve_state_path(args.state),
                 ticks=args.ticks, delay=args.delay)


def cmd_demo(args):
    demo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "..", "demo.whr")
    demo = os.path.abspath(demo)
    if not os.path.exists(demo):
        demo = os.path.join(os.getcwd(), "demo.whr")
    _run_program(demo, _resolve_state_path(args.state),
                 ticks=args.ticks, delay=args.delay)


def cmd_demo_knot(args):
    demo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "..", "demo-knot.whr")
    demo = os.path.abspath(demo)
    if not os.path.exists(demo):
        demo = os.path.join(os.getcwd(), "demo-knot.whr")
    _run_program(demo, _resolve_state_path(args.state),
                 ticks=args.ticks, delay=args.delay)


# ── agents ────────────────────────────────────────────────────────────────

def cmd_agents(args):
    """Show agents that were registered in the last runtime snapshot."""
    from whorl.core.state import SharedState
    state = SharedState(_resolve_state_path(args.path))
    print("\n  Agents (from shared state):\n")
    keys = sorted(set(state.keys_starting_with("agent:") + state.keys_containing(":status")))
    if not keys:
        print("  (no agent status keys yet — run `whorl run demo.whr` first)")
        return
    for key in keys:
        print(f"  {key} = {json.dumps(state.read(key), default=str)[:100]}")


# ── loom scan (restores the documented command) ───────────────────────────

def cmd_loom_scan(args):
    from whorl.loom import scan as loom_scan
    loom_scan(args.path, silent=args.silent)


def cmd_loom_history(args):
    from whorl.loom import history
    for rec in history(limit=args.limit):
        ts = rec.get("timestamp", 0)
        print(f"[{ts:.0f}] {rec.get('blink', '')}")


def cmd_loom_hotspots(args):
    """Emit the worst complexity zones as a markdown report for the
    convergence campaign (default: reports/loom_hotspots.md)."""
    import os
    from whorl.loom import scan as loom_scan
    from whorl.loom.hotspots import render_markdown, measured_file_count

    if not os.path.exists(args.path):
        print(f"[loom] no such path: {args.path}")
        return 1

    top = max(1, args.top)  # never invert or empty the ranking

    weave = loom_scan(args.path, silent=args.silent)
    md = render_markdown(weave, target_path=args.path, top=top)

    if args.stdout:
        print(md)
        return 0

    out = args.out or os.path.join("reports", "loom_hotspots.md")
    if os.path.isdir(out):
        print(f"[loom] --out is a directory: {out}")
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as fh:
        fh.write(md)
    print(f"\n[loom] hotspots report → {out}")
    print(f"       {weave.file_count} files scanned · "
          f"{measured_file_count(weave)} measured zones · "
          f"top {top} ranked\n")
    return 0


# ── memory (the External Context Drive build-out) ─────────────────────────

def cmd_memory_status(args):
    from whorl.core.state import SharedState
    from whorl.memory import ContextExpander
    drive = ContextExpander(SharedState(_resolve_state_path(args.state)), name=args.name)
    print(json.dumps(drive.usage(), indent=2, default=str))


def cmd_memory_stretch(args):
    from whorl.core.state import SharedState
    from whorl.memory import TokenStretcher
    s = TokenStretcher(max_context=args.budget,
                       state=SharedState(_resolve_state_path(args.state)),
                       name=args.name)
    for text in args.text or []:
        s.add_message(text)
    print(json.dumps(s.usage(), indent=2))
    if args.persist:
        s.save()
        print(f"\n  saved → memory:stretch:{args.name}")


def cmd_memory_drive(args):
    from whorl.core.state import SharedState
    from whorl.memory import ContextExpander
    drive = ContextExpander(SharedState(_resolve_state_path(args.state)), name=args.name)
    if args.put:
        for kv in args.put:
            if "=" in kv:
                k, v = kv.split("=", 1)
                if args.weave:
                    if not args.key:
                        print("[memory] --weave requires --key")
                        sys.exit(1)
                    drive.store_woven(k.strip(), v.strip(), args.key)
                    print(f"  stored {k.strip()} (WOVEN · {len(v.strip())} chars)")
                else:
                    drive.store(k.strip(), v.strip())
                    print(f"  stored {k.strip()} ({len(v.strip())} chars)")
    if args.query:
        result = drive.context_retrieval(args.query, top_k=args.top_k,
                                         weave_key=args.key)
        print(f"\n  query: {args.query}")
        print(f"  hits:  {result['hits']}")
        for chunk in result["injected_chunks"]:
            print(f"\n  ── {chunk['key']} ──")
            print(f"  {chunk['content'][:200]}")
        print(f"\n  active context: {len(result['active_context'])} messages, "
              f"{result['tokens']} tokens")
    else:
        print(f"  bank: {drive.bank_size()} entries")
        for key in drive.keys():
            print(f"    {key}")


def cmd_memory_cycle(args):
    from whorl.core.state import SharedState
    from whorl.memory import summarize_cycle, tokens_saved
    if not args.text:
        print("[memory] provide text: whorl memory cycle --text '...' --text '...'")
        sys.exit(1)
    folds = summarize_cycle(args.text, every=args.every)
    raw, folded = tokens_saved(args.text, every=args.every)
    print(f"  folded {len(args.text)} messages → {len(folds)} summaries "
          f"(tokens {raw} → {folded}, saved {raw - folded})")
    for f in folds:
        print(f"\n  [{f['backend']}] ({f['folded']} msgs)\n  {f['content']}")


# ── mind delegation ───────────────────────────────────────────────────────

def cmd_mind(args):
    from whorl.mind import cli as mind_cli
    mind_cli.main(args.mind_args)


# ── legacy (the Field-Intel Workbench, namespaced) ─────────────────────────

def cmd_legacy(args):
    """
    Bridge into the legacy Field-Intel Workbench (whorl/whorl).

    The legacy package is fully self-contained under whorl.whorl.* — its
    internal imports are relative, so the modern `whorl` namespace is never
    shadowed and the two coexist in one interpreter. This subcommand makes
    the field-intel tools reachable from the modern workbench:

        whorl legacy status
        whorl legacy scout run | scout list
        whorl legacy forge pitch --target X --vertical bank
        whorl legacy seat 'idea'
        whorl legacy loom scan <path>
        whorl legacy agent yvette [--vertical hvac]
        whorl legacy tailor qrd|intent
        whorl legacy db migrate
        whorl legacy bridge [--port 8767]
    """
    from whorl.whorl import cli as legacy_cli
    legacy_cli.main(args.legacy_args)
    return 0


# ── swarm (ShipWrekDOS gathering) ─────────────────────────────────────────

def cmd_swarm(args):
    from whorl.runtime.shipwrekd_os import ShipWrekDOS
    syntax = ShipWrekDOS(verbose=not args.quiet)
    syntax.gather(args.manifest, force_consent=args.gather_all)
    syntax.run(ticks=args.ticks, tick_delay=args.delay)
    print(syntax.status())
    syntax.disperse()


# ── gate (Hat 1: the Weight-Vest Gate) ────────────────────────────────────

def cmd_gate(args):
    """Hold the machine's own compression up as a mirror. On a block the
    pipe is cut (exit 3); on a pass the original text goes to stdout."""
    from whorl.memory.gate import gate_pass
    from whorl.core.state import SharedState

    if args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        text = input("prompt> ")

    state = SharedState(_resolve_state_path(args.state))
    result = gate_pass(text, tolerance=args.tolerance,
                       use_chaos=not args.no_chaos,
                       state=state, learn=args.learn)

    # Operator escape hatch: --force passes a blocked prompt through.
    if not result["accepted"] and args.force:
        print(f"  [gate] FORCED — operator override "
              f"(blocked: {result['reason']})", file=sys.stderr)
        print(text)
        return 0

    if args.explain or not result["accepted"]:
        tol = result["tolerance_used"]
        slack = result["slack"]
        slack_disp = "∞" if slack == float("inf") else f"{slack}"
        print(f"  [gate] {result['reason']}", file=sys.stderr)
        print(f"         you: {result['original_tokens']} tok · "
              f"floor: {result['floor_tokens']} tok · "
              f"density {result['density']} · slack {slack_disp} "
              f"(limit {1 + tol:.2f})", file=sys.stderr)
        if result.get("chaos") is not None:
            print(f"         chaos gate active — index {result['chaos']:.2f} "
                  f"(tolerance tightened to {tol})", file=sys.stderr)
        if result.get("dropped_words"):
            print(f"         the floor dropped: {', '.join(result['dropped_words'])}",
                  file=sys.stderr)

    if result["accepted"]:
        if args.explain:
            print("  [gate] PASSED — original text on stdout\n", file=sys.stderr)
        print(text)
        return 0

    slack = result["slack"]
    slack_disp = "∞" if slack == float("inf") else f"{slack}×"
    print(f"\n  [gate] BLOCKED — you are {slack_disp} the machine's floor.",
          file=sys.stderr)
    print(f"         tolerance used: {result['tolerance_used']:.2f} — "
          f"rewrite tighter, or --force", file=sys.stderr)
    if result["suggested"]:
        print("\n  the floor (what the machine would send):\n", file=sys.stderr)
        print(f"  {result['suggested']}\n", file=sys.stderr)
    return 3


# ── weave (Hat 3: Helix-Speak at-rest) ────────────────────────────────────

def _prompt_key() -> str:
    import getpass
    return getpass.getpass("weave key> ")


def cmd_weave(args):
    from whorl.core.helix import Helix, Knot
    from whorl.core.bearing import Bearing
    from whorl.core.state import SharedState

    key = args.key or _prompt_key()

    if args.state_key:
        state = SharedState(_resolve_state_path(args.state))
        value = state.read(args.state_key)
        if value is None:
            print(f"[weave] no such state key: {args.state_key}")
            return 1
        knot = Helix.weave(value, key=key, weaver_id=args.agent_id,
                           bearing=Bearing.weave())
        state.write(args.state_key, knot.to_dict(), "whorl.cli:weave")
        print(f"[weave] state key '{args.state_key}' is now a knot (depth {knot.depth})")
        return 0

    if not args.path:
        print("[weave] provide a file path or --state-key")
        return 1
    if not os.path.exists(args.path):
        print(f"[weave] no such file: {args.path}")
        return 1

    try:
        with open(args.path, "r") as fh:
            value = fh.read()
    except (UnicodeDecodeError, OSError) as e:
        print(f"[weave] cannot read as text (binary?): {e}")
        return 1

    if args.compose:
        try:
            existing = Knot.from_dict(json.loads(value))
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[weave] --compose needs an existing .knot.json, got: {e}")
            return 1
        knot = Helix.weave(existing, key=key, weaver_id=args.agent_id)
    else:
        knot = Helix.weave(value, key=key, weaver_id=args.agent_id)

    out = args.out or (args.path + ".knot.json")
    with open(out, "w") as fh:
        json.dump(knot.to_dict(), fh, indent=2, default=str)
    print(f"[weave] {args.path} → {out} (depth {knot.depth})")
    return 0


def cmd_unweave(args):
    from whorl.core.helix import Helix, Knot
    from whorl.core.state import SharedState

    keys = args.key or _prompt_key()
    keys = [k.strip() for k in keys.split(",") if k.strip()]

    if args.state_key:
        state = SharedState(_resolve_state_path(args.state))
        raw = state.read(args.state_key)
        if not isinstance(raw, dict) or "payload" not in raw:
            print(f"[unweave] '{args.state_key}' is not a knot")
            return 1
        try:
            value = Helix.unravel(Knot.from_dict(raw), key=keys)
        except ValueError as e:
            print(f"[unweave] {e}")
            return 1
        if args.write_back:
            state.write(args.state_key, value, "whorl.cli:unweave")
            print(f"[unweave] '{args.state_key}' unraveled and written back as plaintext")
        else:
            print(value if isinstance(value, str)
                  else json.dumps(value, indent=2, default=str))
        return 0

    if not args.path:
        print("[unweave] provide a knot file path or --state-key")
        return 1
    if not os.path.exists(args.path):
        print(f"[unweave] no such file: {args.path}")
        return 1

    with open(args.path, "r") as fh:
        knot = Knot.from_dict(json.load(fh))
    try:
        value = Helix.unravel(knot, key=keys)
    except ValueError as e:
        print(f"[unweave] {e}")
        return 1

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(value if isinstance(value, str)
                     else json.dumps(value, indent=2, default=str))
        print(f"[unweave] → {args.out}")
    else:
        print(value if isinstance(value, str)
              else json.dumps(value, indent=2, default=str))
    return 0


def cmd_inspect(args):
    from whorl.core.helix import Helix, Knot
    from whorl.core.state import SharedState

    try:
        if args.state_key:
            state = SharedState(_resolve_state_path(args.state))
            raw = state.read(args.state_key)
            if not isinstance(raw, dict) or "payload" not in raw:
                print(f"[inspect] '{args.state_key}' is not a knot")
                return 1
            knot = Knot.from_dict(raw)
        elif args.path and os.path.exists(args.path):
            with open(args.path, "r") as fh:
                knot = Knot.from_dict(json.load(fh))
        else:
            print("[inspect] provide a knot file path or --state-key")
            return 1
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"[inspect] not a valid knot: {e}")
        return 1

    print(json.dumps(Helix.inspect(knot), indent=2))
    return 0


# ── tailor (THE TAILOR — QRD + MindaIntent + Cognitive Shadow, sl1u3) ─────

def cmd_tailor(args):
    """Bridge the legacy whorl.whorl.tailor engine onto the outer rails:
    four-tier QRD, MindaIntent parsing, and the shadow fit against the
    operator's real orbit + pulse. Optional --gate runs the Weight-Vest first."""
    from whorl.core.state import SharedState
    from whorl.tailor import Tailor, format_qrd, format_intent

    text = args.text or (sys.stdin.read().strip() if not sys.stdin.isatty() else None)
    if not text:
        print("[tailor] provide text: whorl tailor qrd '...'")
        return 1

    state = SharedState(_resolve_state_path(args.state))

    if args.gate:
        from whorl.memory.gate import gate_pass
        result = gate_pass(text, tolerance=args.tolerance, state=state)
        if not result["accepted"]:
            slack = result["slack"]
            slack_disp = "∞" if slack == float("inf") else f"{slack}"
            print(f"  [gate] the Tailor refuses the cloth: {result['reason']}",
                  file=sys.stderr)
            print(f"         you: {result['original_tokens']} tok · "
                  f"floor: {result['floor_tokens']} tok · "
                  f"slack {slack_disp} (limit {1 + result['tolerance_used']:.2f})",
                  file=sys.stderr)
            if result["suggested"]:
                print(f"\n  the floor:\n\n  {result['suggested']}\n", file=sys.stderr)
            return 3

    # If --committee is set, read the most recent bicameral deliberation
    # from SharedState so the shadow fits against the committee's verdict.
    committee = None
    if args.committee:
        if args.kind != "shadow":
            print("[tailor] --committee only applies to shadow kind",
                  file=sys.stderr)
        else:
            try:
                keys = sorted(
                    state.keys_starting_with("bicameral:history:"),
                    reverse=True,
                )
                if keys:
                    committee = state.read(keys[0])
                    if isinstance(committee, dict) and "interpreter" in committee:
                        c_q = committee.get("question", "?")[:60]
                        print(f"  [tailor] committee loaded: "
                              f"'{c_q}…' ({committee.get('backend','?')})",
                              file=sys.stderr)
                    else:
                        print("[tailor] last bicameral record is malformed — "
                              "proceeding without committee context",
                              file=sys.stderr)
                        committee = None
                else:
                    print("[tailor] no bicameral history found — "
                          "run `whorl bicameral '...'` first",
                          file=sys.stderr)
            except Exception:
                pass

    t = Tailor(prefer_offline=args.offline, state=state)

    if args.kind == "qrd":
        rec = t.qrd(text, source_id=args.source)
    elif args.kind == "intent":
        rec = t.parse_intent(text)
    elif args.kind == "shadow":
        rec = t.shadow_fit(text, committee=committee)
    else:
        print(f"[tailor] unknown kind: {args.kind}")
        return 1

    if args.json:
        print(json.dumps(rec, indent=2, default=str))
        return 0

    print()
    if args.kind == "intent":
        print(format_intent(rec))
    else:
        print(format_qrd(rec, args.kind))
    return 0


# ── bicameral (THE COMMITTEE — Jaynes made mechanical) ─────────────────────

def cmd_bicameral(args):
    """Convene the committee: Master + Emissary deliberate, the Interpreter
    narrates the verdict. Optional --gate runs the Weight-Vest first."""
    from whorl.core.state import SharedState
    from whorl.bicameral import Bicameral

    question = args.question
    if not question and not sys.stdin.isatty():
        question = sys.stdin.read().strip()
    if not question:
        print("[bicameral] provide a question: whorl bicameral 'should we ...'")
        return 1

    state = SharedState(_resolve_state_path(args.state))

    if args.gate:
        from whorl.memory.gate import gate_pass
        result = gate_pass(question, tolerance=args.tolerance, state=state)
        if not result["accepted"]:
            slack = result["slack"]
            slack_disp = "∞" if slack == float("inf") else f"{slack}"
            print(f"  [gate] the Master refuses to convene: {result['reason']}",
                  file=sys.stderr)
            print(f"         you: {result['original_tokens']} tok · "
                  f"floor: {result['floor_tokens']} tok · "
                  f"slack {slack_disp} (limit {1 + result['tolerance_used']:.2f})",
                  file=sys.stderr)
            if result["suggested"]:
                print(f"\n  the floor:\n\n  {result['suggested']}\n", file=sys.stderr)
            return 3

    committee = Bicameral(prefer_offline=args.offline)

    # Read the operator's actual orbit so the committee deliberates in context,
    # not in a void. Pure read — always try, fall back to None on any failure.
    orbit = None
    try:
        from whorl import drift as drift_mod
        rep = drift_mod.orbit_report(1, state=state)
        orbit = {
            "glyph": rep["glyph"],
            "intent": rep["intent"],
            "speed": rep["speed"],
            "open_threads": rep.get("roadmap_open_items"),
        }
    except Exception:
        pass

    rec = committee.deliberate(question, rounds=args.rounds,
                                state=state, orbit=orbit)

    if args.json:
        print(json.dumps(rec, indent=2, default=str))
        return 0

    m, e, i = rec["master"], rec["emissary"], rec["interpreter"]
    print("\n  ── THE COMMITTEE ──")
    print(f"  question: {question}\n")
    print(f"  THE MASTER      {m['glyph']}  {m['content']}")
    print(f"\n  THE EMISSARY    {e['glyph']}  {e['content']}")
    if rec["disagreement"]:
        print(f"\n  DISAGREEMENT    {rec['disagreement']}")
    print(f"\n  THE INTERPRETER {i['glyph']}  {i['content']}")
    print(f"\n  backend: {rec['backend']} · rounds: {rec['rounds']}")
    return 0


# ── drift (Hat 2: the Orbit Vane) ─────────────────────────────────────────

def cmd_drift(args):
    from whorl.core.state import SharedState
    from whorl import drift as drift_mod

    state = SharedState(_resolve_state_path(args.state))

    if args.history:
        rows = drift_mod.history(state, limit=args.limit)
        if not rows:
            print("  (no drift snapshots yet — run `whorl drift --snapshot` daily)")
        for row in rows:
            print(f"  {row['date']}  {row['glyph']}  {row['intent']}  "
                  f"(speed {row['speed']})")
        return 0

    report = drift_mod.orbit_report(args.days, state=state,
                                    roadmap_path=args.roadmap)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print()
        print(drift_mod.format_report(report))

    if args.snapshot:
        today = drift_mod.snapshot(state)
        print(f"\n  [drift] snapshot saved: drift:history:{today}")
    return 0


# ── argument parser ───────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whorl",
        description="WHORL — helical agentic language & Loomy runtime workbench",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version="whorl 0.1.0-alpha (Loomy)")
    sub = p.add_subparsers(dest="command")

    # bearing
    b = sub.add_parser("bearing", help="Interpret a 3-axis rotational bearing")
    b.add_argument("x", help="X-axis: cw | ccw | 0")
    b.add_argument("y", help="Y-axis: cw | ccw | 0")
    b.add_argument("z", help="Z-axis: cw | ccw | 0")
    b.add_argument("--speed", type=int, default=5, help="Speed 1-10")
    b.set_defaults(handler=cmd_bearing)

    # state
    s = sub.add_parser("state", help="Inspect shared state")
    s.add_argument("--path", default=None, help="State JSON path (jailed to ~/.whorl)")
    s.add_argument("--json", action="store_true", help="Raw JSON dump")
    s.set_defaults(handler=cmd_state)

    # decompile
    d = sub.add_parser("decompile", help="Transpile source through the shared IR")
    d.add_argument("source", help="Source code string")
    d.add_argument("--from", dest="from_lang", default="python", help="Source language")
    d.add_argument("--to", dest="to_lang", default="bash", help="Target language")
    d.set_defaults(handler=cmd_decompile)

    # run
    r = sub.add_parser("run", help="Run a .whr program (restores loomy.py run)")
    r.add_argument("file", help="Path to .whr program")
    r.add_argument("--ticks", type=int, default=None, help="Override tick limit")
    r.add_argument("--delay", type=float, default=None, help="Override tick delay")
    r.add_argument("--state", default=None, help="State JSON path")
    r.set_defaults(handler=cmd_run)

    # demo / demo-knot
    for name in ("demo", "demo-knot"):
        dm = sub.add_parser(name, help=f"Run the bundled {name} demo")
        dm.add_argument("--ticks", type=int, default=None)
        dm.add_argument("--delay", type=float, default=None)
        dm.add_argument("--state", default=None)
        dm.set_defaults(handler=cmd_demo if name == "demo" else cmd_demo_knot)

    # agents
    a = sub.add_parser("agents", help="Show agents in shared state")
    a.add_argument("--path", default=None)
    a.set_defaults(handler=cmd_agents)

    # loom
    loom = sub.add_parser("loom", help="Code-topology scanning (CodeCity-Bench)")
    loom_sub = loom.add_subparsers(dest="loom_cmd")
    ls = loom_sub.add_parser("scan", help="Scan a codebase (read-only)")
    ls.add_argument("path", help="Path to scan")
    ls.add_argument("--silent", action="store_true", help="No report, weave only")
    ls.set_defaults(handler=cmd_loom_scan)
    lh = loom_sub.add_parser("history", help="Recent scan records")
    lh.add_argument("--limit", type=int, default=5)
    lh.set_defaults(handler=cmd_loom_history)

    hp = loom_sub.add_parser(
        "hotspots",
        help="Emit the worst complexity zones as markdown (convergence campaign)")
    hp.add_argument("path", help="Path to scan")
    hp.add_argument("--top", type=int, default=10,
                    help="Number of hotspot zones to rank (default 10)")
    hp.add_argument("--out", default=None,
                    help="Output markdown path (default reports/loom_hotspots.md)")
    hp.add_argument("--stdout", action="store_true",
                    help="Print the markdown instead of writing a file")
    hp.add_argument("--silent", action="store_true",
                    help="No scanner chatter")
    hp.set_defaults(handler=cmd_loom_hotspots)

    # memory
    mem = sub.add_parser("memory", help="External Context Drive (built from concept stubs)")
    mem_sub = mem.add_subparsers(dest="mem_cmd")

    ms = mem_sub.add_parser("status", help="Drive usage")
    ms.add_argument("--name", default="default")
    ms.add_argument("--state", default=None)
    ms.set_defaults(handler=cmd_memory_status)

    mt = mem_sub.add_parser("stretch", help="Feed a TokenStretcher and see compression")
    mt.add_argument("--text", action="append", help="A message (repeatable)")
    mt.add_argument("--budget", type=int, default=2000, help="Token budget")
    mt.add_argument("--name", default="default")
    mt.add_argument("--state", default=None)
    mt.add_argument("--persist", action="store_true", help="Save to SharedState")
    mt.set_defaults(handler=cmd_memory_stretch)

    md = mem_sub.add_parser("drive", help="Store + retrieve from the external drive")
    md.add_argument("--put", action="append", help="key=content (repeatable)")
    md.add_argument("--query", default=None, help="Retrieval query")
    md.add_argument("--top-k", dest="top_k", type=int, default=3)
    md.add_argument("--weave", action="store_true",
                    help="Store as a helical knot (Helix-Speak at-rest)")
    md.add_argument("--key", default=None, help="Weave key (required with --weave)")
    md.add_argument("--name", default="default")
    md.add_argument("--state", default=None)
    md.set_defaults(handler=cmd_memory_drive)

    mc = mem_sub.add_parser("cycle", help="Fold messages into summaries every N")
    mc.add_argument("--text", action="append", help="A message (repeatable)")
    mc.add_argument("--every", type=int, default=4)
    mc.set_defaults(handler=cmd_memory_cycle)

    # mind
    mind = sub.add_parser("mind", help="Model registry (delegates to whorl.mind.cli)")
    mind.add_argument("mind_args", nargs=argparse.REMAINDER,
                      help="Args passed to `whorl.mind.cli` (list, ask, chat, ...)")
    mind.set_defaults(handler=cmd_mind)

    # legacy (Field-Intel Workbench — whorl/whorl, namespaced). This entry
    # keeps `legacy` discoverable in `whorl --help`; actual invocations are
    # forwarded in main() before parsing (see cmd_legacy note).
    lg = sub.add_parser(
        "legacy",
        help="Field-Intel Workbench (whorl.whorl) — scouts, forge, hotseat, yvette, bridge, tailor")
    lg.add_argument("legacy_args", nargs=argparse.REMAINDER,
                    help="Args passed to the legacy workbench CLI "
                         "(status, scout, forge, seat, loom, agent, tailor, db, bridge)")
    lg.set_defaults(handler=cmd_legacy)

    # swarm
    sw = sub.add_parser("swarm", help="ShipWrekDOS — a gathering of consenting minds")
    sw.add_argument("--manifest", default="small", help="Guest list (full, small)")
    sw.add_argument("--ticks", type=int, default=10)
    sw.add_argument("--delay", type=float, default=0.2)
    sw.add_argument("--quiet", action="store_true")
    sw.add_argument("--gather-all", action="store_true", help="All agents consent")
    sw.set_defaults(handler=cmd_swarm)

    # gate (Hat 1)
    g = sub.add_parser("gate", help="Weight-Vest Gate — match the machine's compression or the pipe stays cut")
    g.add_argument("--text", default=None, help="Prompt to evaluate (else reads stdin)")
    g.add_argument("--tolerance", type=float, default=0.15,
                   help="Max slack above the floor (0.15 = 15%%)")
    g.add_argument("--no-chaos", action="store_true",
                   help="Disable the persona chaos gate")
    g.add_argument("--learn", action="store_true",
                   help="Remember accepted prompts as exceptions")
    g.add_argument("--explain", action="store_true", help="Always print the verdict")
    g.add_argument("--force", action="store_true",
                   help="Operator override — pass a blocked prompt through")
    g.add_argument("--state", default=None)
    g.set_defaults(handler=cmd_gate)

    # weave / unweave / inspect (Hat 3)
    wv = sub.add_parser("weave", help="Helix-Speak — weave a file or state key into a knot")
    wv.add_argument("path", nargs="?", default=None, help="File to weave (or use --state-key)")
    wv.add_argument("--key", default=None, help="Weave key (prompted if omitted)")
    wv.add_argument("--agent-id", default="whorl-cli", help="Weaver identity")
    wv.add_argument("--out", default=None, help="Output path (default <path>.knot.json)")
    wv.add_argument("--compose", action="store_true",
                    help="Wrap an existing knot into deeper knotwork")
    wv.add_argument("--state-key", default=None, help="Weave a SharedState key in place")
    wv.add_argument("--state", default=None)
    wv.set_defaults(handler=cmd_weave)

    uw = sub.add_parser("unweave", help="Unravel a knot back to plaintext")
    uw.add_argument("path", nargs="?", default=None)
    uw.add_argument("--key", default=None,
                    help="Key(s), comma-separated for knotwork (outermost first)")
    uw.add_argument("--out", default=None, help="Write plaintext to a file instead of stdout")
    uw.add_argument("--state-key", default=None)
    uw.add_argument("--state", default=None)
    uw.add_argument("--write-back", action="store_true",
                    help="Write the unraveled value back to SharedState")
    uw.set_defaults(handler=cmd_unweave)

    ins = sub.add_parser("inspect", help="Peek a knot's metadata without decrypting")
    ins.add_argument("path", nargs="?", default=None)
    ins.add_argument("--state-key", default=None)
    ins.add_argument("--state", default=None)
    ins.set_defaults(handler=cmd_inspect)

    # drift (Hat 2)
    df = sub.add_parser("drift", help="Orbit Vane — your actual bearing, read from your artifacts")
    df.add_argument("--days", type=int, default=1, help="Window in days")
    df.add_argument("--json", action="store_true")
    df.add_argument("--snapshot", action="store_true",
                    help="Persist today's bearing for drift comparison")
    df.add_argument("--history", action="store_true", help="List saved daily snapshots")
    df.add_argument("--limit", type=int, default=10)
    df.add_argument("--roadmap", default="~/ROADMAP.md",
                    help="Roadmap file for the open-item count")
    df.add_argument("--state", default=None)
    df.set_defaults(handler=cmd_drift)

    # bicameral (THE COMMITTEE)
    bc = sub.add_parser(
        "bicameral",
        help="THE COMMITTEE — Master + Emissary deliberate, the Interpreter narrates")
    bc.add_argument("question", nargs="?", default=None,
                    help="The question to deliberate (else reads stdin)")
    bc.add_argument("--rounds", type=int, default=1,
                    help="Deliberation rounds (1-3)")
    bc.add_argument("--offline", action="store_true",
                    help="Skip the model — deterministic fallback voices")
    bc.add_argument("--gate", action="store_true",
                    help="Run the Weight-Vest Gate on the question first")
    bc.add_argument("--tolerance", type=float, default=0.15)
    bc.add_argument("--json", action="store_true")
    bc.add_argument("--state", default=None)
    bc.set_defaults(handler=cmd_bicameral)

    # tailor (THE TAILOR — legacy whorl.whorl.tailor bridged)
    tl = sub.add_parser(
        "tailor",
        help="THE TAILOR — QRD engine + MindaIntent + the Cognitive Shadow")
    tl.add_argument("kind", choices=["qrd", "intent", "shadow"],
                    help="Which Tailor operation to run")
    tl.add_argument("text", nargs="?", default=None,
                    help="Input text (else reads stdin)")
    tl.add_argument("--offline", action="store_true",
                    help="Skip the model — deterministic fallback")
    tl.add_argument("--gate", action="store_true",
                    help="Run the Weight-Vest Gate on the input first")
    tl.add_argument("--tolerance", type=float, default=0.15)
    tl.add_argument("--committee", action="store_true",
                    help="Feed the last bicameral deliberation into the shadow "
                         "(shadow kind only)")
    tl.add_argument("--json", action="store_true")
    tl.add_argument("--source", default="manual",
                    help="Source id recorded on the QRD")
    tl.add_argument("--state", default=None)
    tl.set_defaults(handler=cmd_tailor)

    return p


# ── entry point ───────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]

    # `whorl legacy ...` forwards straight into the legacy Field-Intel
    # Workbench parser — its command surface is authoritative, and -h /
    # --help / unknown args behave exactly as the legacy CLI defines them
    # (argparse's REMAINDER cannot be trusted with option-like tokens).
    if argv and argv[0] == "legacy":
        from whorl.whorl import cli as legacy_cli
        try:
            return int(legacy_cli.main(argv[1:]) or 0)
        except SystemExit as e:
            return int(e.code or 0)

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        _print_banner()
        parser.print_help()
        return 0

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    try:
        code = args.handler(args)
        return int(code) if code is not None else 0
    except KeyboardInterrupt:
        print("\n[whorl] interrupted")
        return 130
    except ImportError as e:
        print(f"[whorl] missing dependency: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"[whorl] file not found: {e}")
        return 1
    except PermissionError as e:
        print(f"[whorl] access denied: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
