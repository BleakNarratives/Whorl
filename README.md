# Whorl

> A polyglot double-helical agentic programming language.  
> Agents share persistent state and act with full runtime autonomy,
> demonstrating intent via rotational bearing and speed.

**Whorl** (*.whr) + **Loom/Loomy** (runtime) = agents that boot with
2-3 parameters and handle it from there.

## Quick start

The entry point is the `whorl.cli` workbench. Run it from this project
directory without installing packages:

```bash
cd /home/bleaknarratives/whorl

# Show the current command surface without touching project state
python3 -m whorl --help
python3 -m whorl --version

# Code-topology scan (read-only): complexity hotspots + vibe dark spots
python3 -m whorl loom scan .
# Worst complexity zones as a markdown report for the convergence campaign
python3 -m whorl loom hotspots . --top 10          # → reports/loom_hotspots.md
python3 -m whorl loom hotspots . --stdout          # print instead of writing

# Run a .whr swarm program (demo.whr lives at the project root)
python3 -m whorl run ../demo.whr --ticks 20

# Interpret a 3-axis rotational bearing
python3 -m whorl bearing cw ccw 0 --speed 8

# Polyglot transpile through the shared IR
python3 -m whorl decompile "print('hi')" --from python --to bash

# Inspect the shared state store
python3 -m whorl state

# External Context Drive — token stretcher / summary cycle (built from
# the concept_source pseudo-code; see whorl/memory/)
python3 -m whorl memory cycle --text 'a' --text 'b' --every 4

# Auto-compression at the model choke point: pass a conversation to
# invoke_model and the TokenStretcher folds it under budget before the
# call (messages = history; prompt = the new turn; -- max_context sets
# the budget, stretch_name persists the window across calls).
python3 - <<'PYEOF'
from whorl.tools.model_spirit import invoke_model
history = [{"role": "user", "content": f"scout log {i}: consolidation at the port"} for i in range(25)]
text, meta = invoke_model("latest: ship the swarm", messages=history, max_context=400)
print(meta["stretch"])   # tokens_before / tokens_after / saved_tokens / folds
PYEOF

# THE THREE HATS — friction tools stitched from the same rails
#  1. Weight-Vest Gate: the machine's own compression as a mirror.
#     Dense prompt → pass (exit 0); bloated prompt → pipe cut (exit 3).
python3 -m whorl gate --text 'BTC consolidating above 42k, low volume'
echo 'your bloated prompt' | python3 -m whorl gate          # pipe mode
python3 -m whorl gate --learn --text '...'                  # remember accepted prompts
#  2. Helix-Speak at-rest: weave anything into an unreadable knot.
python3 -m whorl weave secret.txt --key K                   # → secret.txt.knot.json
python3 -m whorl inspect secret.txt.knot.json               # metadata, no key needed
python3 -m whorl unweave secret.txt.knot.json --key K
python3 -m whorl weave --state-key market:btc --key K       # weave a state value in place
python3 -m whorl memory drive --weave --key K --put 'k=v'   # woven chunks in the drive
#  3. Orbit Vane: your ACTUAL bearing, read from your artifacts.
python3 -m whorl drift                                     # today's orbit report
python3 -m whorl drift --snapshot                          # persist for tomorrow's drift
python3 -m whorl drift --history                           # saved orbits
#  4. THE COMMITTEE: a mechanical bicameral mind (Jaynes made real —
#     the doctrine in concept_source/sl1u3.txt, built as a process).
python3 -m whorl bicameral 'should we ship the swarm?'     # two voices deliberate
python3 -m whorl bicameral 'question' --rounds 2           # deliberate twice
python3 -m whorl bicameral 'question' --gate               # the Master refuses sloppy questions
#  5. THE TAILOR: QRD engine + MindaIntent + the Cognitive Shadow
#     (bridged from the legacy whorl.whorl.tailor module).
python3 -m whorl tailor qrd 'the situation'               # BLINK/BRIEF/DEEP/FULL tiers
python3 -m whorl tailor intent 'chaotic thought dump'     # MindaIntent structured parsing
python3 -m whorl tailor shadow 'the decision'             # fitted to your real orbit + pulse

#  6. THE LEGACY WORKBENCH: the Field-Intel tools, namespaced.
#     whorl/whorl is self-contained (relative imports) — it lives under
#     whorl.whorl.* and the modern `whorl` namespace is never shadowed.
#     Reach it from the modern workbench, or directly: python -m whorl.whorl
python3 -m whorl legacy status                            # field-intel status + DB counts
python3 -m whorl legacy scout run|list                    # intel feed operations
python3 -m whorl legacy forge pitch --target X --vertical bank
python3 -m whorl legacy seat 'your idea'                  # three-voice hotseat
python3 -m whorl legacy agent yvette --vertical hvac      # dispatch agent
python3 -m whorl legacy tailor qrd 'wall of text'         # the legacy QRD engine
python3 -m whorl legacy db migrate                        # legacy SQLite migrations
python3 -m whorl legacy bridge --port 8767                # boardroom HTTP bridge

# Model registry (ollama / huggingface discovery + routing)
python3 -m whorl mind list

# ShipWrekDOS — a gathering of consenting minds.
#   Scout findings persist across sessions via the ContextDrive (same
#   SharedState the swarm lives in — see ~/.whorl/state_shipwrekd.json):
python3 -m whorl swarm --manifest small --ticks 5
python3 -m whorl memory drive --name scouts \
       --state ~/.whorl/state_shipwrekd.json --query 'scout found state key'

# HTTP bridge over Loomy state (whorl-bridge console script)
python3 -m whorl.bridge --port 8767
```

## Architecture

```
whorl/
├── core/               # Agent, Bearing, State, Runtime
│   ├── agent.py        # Autonomous agent (boots with 2-3 params)
│   ├── bearing.py      # 3-axis rotational bearing (intent signal)
│   ├── helix.py        # Helical knotwork crypto (weave/unravel)
│   ├── state.py        # Persistent shared state (JSON-backed)
│   └── runtime.py      # Loomy — event loop, agent host, state broker
├── tools/              # Tool, Toolkit, Toolchain
│   ├── __init__.py     # Abstractions + built-in tools
│   ├── decompiler.py   # Polyglot decompiler/recompiler (Python↔Bash↔JS)
│   └── model_spirit.py # Model routing (state / groq / remote / local)
│                       #   + TokenStretcher seam: messages= auto-compresses
├── memory/             # External Context Drive (built from concept_source)
│   ├── stretcher.py    # TokenStretcher — budgeted context compression
│   ├── drive.py        # ContextExpander — external store + retrieval
│   ├── gate.py         # Weight-Vest Gate — machine compression as a mirror
│   └── cycle.py        # summarize_cycle — fold N messages into a summary
├── loom/               # CodeCity-Bench topology (structure/complexity/scribe/security)
│   ├── hotspots.py     # Convergence-campaign report: worst complexity zones → md
├── mind/               # Model registry (ollama, huggingface) + routing
├── lang/               # Whorl language (*.whr)
│   └── __init__.py     # Parser for .whr files
├── runtimes/           # Language runtime adapters
│   └── __init__.py     # Bash + Python + Node + Go adapters
├── runtime/            # ShipWrekDOS consent-based swarm + persona behaviors
└── __init__.py

whorl/whorl/            # LEGACY Field-Intel Workbench — fully self-contained
                        # under whorl.whorl.* (relative imports; the modern
                        # `whorl` namespace is never shadowed). Contains its
                        # own core (db/config/models/vault), scouts, forge,
                        # hotseat, agents/yvette, nostr, loom, tailor, bridge.

whorl/cli.py             # Workbench CLI (`python3 -m whorl`)
whorl/__main__.py        # `python3 -m whorl` module entry
whorl/bridge.py          # HTTP bridge (`whorl-bridge` console script)
whorl/drift.py           # Orbit Vane — your bearing, read from your artifacts
whorl/bicameral.py       # THE COMMITTEE — Master + Emissary + Interpreter
whorl/tailor.py          # THE TAILOR — QRD + MindaIntent + Cognitive Shadow (sl1u3 bridge)
pyproject.toml           # Package metadata and console-script entry points
```

## Bearing system

Agents express intent through **rotational bearing** across 3 axes:

| Axis   | CW (+1)                 | CCW (-1)              |
|--------|-------------------------|------------------------|
| X (data)    | READ / COPY / OBSERVE   | REMOVE / CONSUME      |
| Y (scope)   | SPECIFIC / TARGETED     | WILDCARD / VARIABLE   |
| Z (transform) | WEAVE / COMPILE / BUILD | UNRAVEL / DECOMPILE   |

**Speed** (1-10) controls tick frequency in the runtime loop.

Combined bearing states are the agent's "body language" — other agents
observe the bearing to understand intent without explicit messaging.

## .whr file format

```whr
# Comments
@agent <name> <role>
  bearing: cw ccw 0
  speed: 8
  tools: tool1, tool2

@state key = value
@run 100
@delay 0.05
```

## Design principles

- **Agents are simple.** Boot with 2-3 params; complexity emerges from the swarm.
- **State is shared.** All agents read/write the same persistent store.
- **Bearing is communication.** No explicit messages — intent flows through rotation.
- **Polyglot by nature.** Decompiler/recompiler bridges languages via shared IR.
- **Self-healing.** Agents can dogpile runtime errors (emerging capability).
