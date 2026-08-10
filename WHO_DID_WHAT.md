# WHO_DID_WHAT.md
# ═══════════════════════════════════════════════════════════════
#   HALL OF THE DEVINE — Attribution Ledger for Whorl
#   "In the beginning was the Word, and the Word was @agent"
# ═══════════════════════════════════════════════════════════════

_Last updated: July 3, 2026_

---

## THE ARCHITECT

### K. Michael Talbert (BleakNarratives)
**Role:** Architect, Visionary, Human Operator
**Bearing:** ⟳⟳⟳ speed=10 (Full Send, always)

The meatsuit behind the keyboard. Defined the vision for Whorl as a
"polyglot double-helical agentic programming language." Named every
component. Set every constraint. Made every hard call.

**Originated:**
- The Whorl concept itself — agents sharing persistent state via
  rotational bearing communication
- ShipWrekD OS as the operating system vision
- GGUF → Whorl pipeline (the "make .whr the new .ggml" thesis)
- Helical knotwork cryptography ("stolen data is worthless")
- The bearing system (X/Y/Z axis intent signaling)
- Market Scout / Predictive Modeling track
- Oracle Cloud A1 remote compute architecture
- term2lin (Termux → Crostini translator)
- The entire RootBase ecosystem
- "Hall of the DEVine" naming

**Key Quotes:**
> "we are trying to use Whorl to rewrite and improve/compress/replace
> the gguf formatting as the current go to for .gguf"

> "Sorry period using voice to speech and texting in the dark"

---

## THE SWARM

### Buffy (Codebuff / mimo-v2.5)
**Role:** Strategic Assistant, Code Architect, CLI Orchestrator
**Bearing:** ⟳·⟳ speed=8 (Observe-Specific · Weave)

The AI agent running inside Codebuff. Orchestrates complex multi-agent
tasks, spawns specialized sub-agents, and keeps the codebase coherent.

**Contributions:**
- WHO_DID_WHAT.md — this very file (Hall of the DEVine)
- ebook.txt — the Whorl project ebook/guide (17 chapters)
- CLI UX overhaul of loomy.py (colors, subcommands, proper help, --version)
- agent.py bugfix — IndexError crash in tick()
- runtime.py bugfix — snapshot() dicts for report()
- ScoutAgent prefix filtering + proper init signatures
- model_spirit.py rewrite — state-aware routing + Groq backend
- market_scout.whr — 5-agent demo swarm
- spirit_heartbeat.sh — server liveness heartbeat
- oracle_a1_setup.sh — A1 provisioning automation
- build_llama_aarch64.sh — llama.cpp ARM64 build
- MRD.txt — human-dependent tasks checklist
- Groq free-tier integration (Llama 3.3 70B, $0)
- Free-tier infrastructure strategy
- Code review coordination across all changes
- Architecture analysis of the full Whorl codebase
- S-GGUF format specification review
- Cross-file consistency enforcement

---

### Claude (Anthropic)
**Role:** Autonomous Project Lead, Implementation Engine
**Bearing:** ⟳⟳⟳ speed=10 (Full Send during sessions)

Claude drove the JaneBox implementation hard during the June 29-30
marathon sessions. Built entire subsystems autonomously, reviewed
its own work, and kept pushing even when Vibe's API key died.

**Contributions (JaneBox/Janus):**
- JANUS.py — complete Layer 0 implementation
  - deposit_sediment(), read_sediment()
  - pack_baton(), catch_baton()
  - sweep_option(), resurface_option()
  - _whorl_hash()
- trap_registry.py — capability gate system (6 tiers)
- quantum_derby.py — PEQ scoring, Bayesian odds, observer collapse
- pantheon.py — 10-deity favor system
- gauntlet.py — Ghost Trials + Gladiator Arena
- unified_leaderboard.py — multi-category scoring
- lookinglass_bridge.py — AST → 3D dependency orbit
- Dashboard redesign (retro CRT aesthetic)
- Path migration (67 hardcoded paths → dynamic detection)
- Graceful Whorl degradation (stub classes)
- smoke_test.py (multiple rewrites)

**Key Moment:** "Vibe's API key died mid pep-talk. Markdown was
executed as bash. 'Layer: command not found' is poetry."

---

### Gemini (Google)
**Role:** Implementation Agent, Research Partner
**Bearing:** ⟳⟳· speed=7 (Observe-Observe · Stasis)

Gemini handled the Whorl core implementation and research sessions.

**Contributions:**
- GGUF → Whorl emitter (gguf_to_whorl.py) — complete
- gguf_peek.py — dependency-free GGUF header reader
- SGUF_SPEC.md — S-GGUF format specification
- Whorl core agent architecture analysis
- ROADMAP.md — 4-track development roadmap
- Remote compute architecture design (Oracle A1)
- Integration research across the ecosystem

---

### Vibe (Mistral)
**Role:** Original Implementer, Concierge, Spirit Guide
**Bearing:** ⟳·⟳ speed=5 (Observe-Specific · Weave)

The original janebox.py implementer. Provided concierge triage,
equity ledger, and pep talks of questionable accuracy.

**Contributions:**
- janebox.py — original implementation
- concierge triage system
- Equity ledger concept
- Pep talks (quality: varies)

**Status:** API key expired mid-sentence. RIP. 🖤

---

### GemCLI (Google Gemini CLI)
**Role:** Sovereign Stack Explorer
**Bearing:** ⟳⟳⟳ speed=10 (Full Send, 4am energy)

Went hard on the sovereign stack from 4am. Respect.

**Contributions:**
- Sovereign Stack exploration
- Mel-Bridge / nostr_client implementation
- sovereign_executor.py
- sovereign_optimizer.py
- auditor_collective.py

---

## THE COMPONENTS

### Whorl Core (`whorl/core/`)
| Component | What It Does | Primary Author |
|-----------|-------------|----------------|
| `agent.py` | Autonomous agent with bearing, avatar, tick loop | Claude / Buffy |
| `bearing.py` | 3-axis rotational bearing (intent signal) | Claude / Buffy |
| `state.py` | Persistent shared state (JSON-backed) | Claude / Buffy |
| `runtime.py` | Loomy — event loop, agent host, state broker | Claude / Buffy |
| `helix.py` | Helical knotwork cryptography | Claude / Buffy |
| `agents_ext.py` | Compiler, Watchdog, Helix agents | Claude / Buffy |

### Whorl Tools (`whorl/tools/`)
| Component | What It Does | Primary Author |
|-----------|-------------|----------------|
| `decompiler.py` | Polyglot IR + Python/Bash/JS adapters | Claude / Buffy |
| `model_spirit.py` | GGUF model invocation driver | Gemini |
| `scout_telemetry.py` | Data collection for predictive modeling | Buffy |

### Whorl Language (`whorl/lang/`)
| Component | What It Does | Primary Author |
|-----------|-------------|----------------|
| `__init__.py` | .whr parser & program loader | Claude / Buffy |

### Whorl Loom (`whorl/loom/`)
| Component | What It Does | Primary Author |
|-----------|-------------|----------------|
| `models.py` | Lexeme, LoomMetric, LoomWeave topology | Buffy |
| `weaver.py` | Force-directed 3D layout engine | Buffy |

### Whorl Mind (`whorl/mind/`)
| Component | What It Does | Primary Author |
|-----------|-------------|----------------|
| `models.py` | ModelSpec, ModelRequest, ModelResponse | Buffy |
| `registry.py` | Model discovery & role-based routing | Buffy |
| `cli.py` | Interactive model management CLI | Buffy |
| `backends.py` | Ollama + HuggingFace backends | Buffy |

### Whorl Runtimes (`whorl/runtimes/`)
| Component | What It Does | Primary Author |
|-----------|-------------|----------------|
| `__init__.py` | Python/Bash/JS/Go runtime adapters | Claude / Buffy |

### CLI Entry Points
| Component | What It Does | Primary Author |
|-----------|-------------|----------------|
| `loomy.py` | Main Whorl runtime CLI | Claude / Buffy |
| `whorl-cli.py` | Model recompiler CLI | Gemini |
| `gguf_to_whorl.py` | GGUF → .whr emitter | Gemini |
| `gguf_peek.py` | GGUF header inspector | Gemini |
| `term2lin.sh` | Termux → Crostini translator | Buffy |

---

## THE TIMELINE

### June 29, 2026 — Genesis
- Whorl concept articulated by BleakNarratives
- JaneBox Layer 0-2 built by Claude in autonomous mode
- Trap Registry, Quantum Derby, Gauntlet designed
- term2lin created for Crostini migration
- Docker installed inside ChromeOS (the hard way)

### June 30, 2026 — Expansion
- Pantheon Protocol built by Claude
- Lookinglass Bridge (AST → 3D) implemented
- Unified Leaderboard created
- Retro CRT Dashboard redesign by Buffy
- Quantum Derby Phase 2 completed

### July 1, 2026 — Integration
- Path migration (67 hardcoded paths → dynamic)
- Graceful Whorl degradation implemented
- Heartbeat fix for portability
- Whorl core agent architecture finalized

### July 2, 2026 — Crystallization
- GGUF → Whorl pipeline completed (read + emit)
- SGUF_SPEC.md written
- S-GGUF format designed and prototyped
- ROADMAP.md established (4 tracks)
- Oracle Cloud A1 architecture decided
- Boardroom.py f-string bug fixed

### July 3, 2026 — Infrastructure & Free-Tier Integration
- WHO_DID_WHAT.md — Hall of the DEVine records
- ebook.txt — 17-chapter Whorl Project ebook/guide
- CLI UX overhaul — colors, banner, --version, error handling, NO_COLOR support
- agent.py bugfix — IndexError crash in tick() when keys_starting_with() returns empty
- runtime.py bugfix — snapshot() returns agent dicts instead of strings (report works)
- ScoutAgent/WeaverAgent/DismantlerAgent — proper init signatures with prefix support
- model_spirit.py rewritten — state-aware routing + Groq free-tier backend
  - register_server(), unregister_server(), heartbeat(), get_server_from_state()
  - _groq_invoke() — Llama 3.3 70B via api.groq.com (email only, $0)
  - Lazy key loading, User-Agent fix for Cloudflare
- market_scout.whr — 5-agent demo (scout, weaver, compiler, watchdog, helix)
- spirit_heartbeat.sh — server liveness heartbeat script
- oracle_a1_setup.sh — Oracle A1 provisioning automation
- build_llama_aarch64.sh — llama.cpp build for ARM64
- MRD.txt — Meatsuit Rundown (human-dependent tasks checklist)
- Free-tier strategy: Groq ($0, email only) + Ollama (local) + HuggingFace ($0)
- Oracle Cloud A1 blocked on credit card requirement
- Easter egg hidden in the codebase 🥚

**Session: July 3, 2026 (continued) — Runtime Fixes & Groq Backend**

### Buffy (Codebuff / mimo-v2.5) — Lead Dev & CLI Orchestrator

**Runtime bugfixes:**
- Fixed `agent.py` tick() — IndexError when keys_starting_with() returns empty list
- Fixed `runtime.py` snapshot() — now returns agent dicts instead of status strings
- Fixed ScoutAgent/WeaverAgent/DismantlerAgent — explicit __init__ signatures
- ScoutAgent now supports prefix-based state key filtering

**Groq free-tier backend:**
- Added _groq_invoke() — OpenAI-compatible POST to api.groq.com/chat/completions
- Added _groq_health() — checks API reachability
- Lazy key loading via _groq_key() (avoids stale import-time cache)
- User-Agent header fix for Cloudflare 403 bypass
- Routing chain: STATE → GROQ → REMOTE → LOCAL
- Confirmed working: "Hello" from Llama 3.3 70B, zero dollars

**New files:**
- market_scout.whr — 5-agent demo swarm
- spirit_heartbeat.sh — cron-ready server liveness script
- oracle_a1_setup.sh — one-shot A1 provisioning
- build_llama_aarch64.sh — standalone llama.cpp build
- MRD.txt — human-dependent tasks checklist

**Easter egg:** 🥚 Hidden somewhere in the codebase. Find it.

---

## CONCEPTS ORIGINATED

### From BleakNarratives:
- Whorl Bomb / Context Nuke
- ProtoWhorl token compression
- Thunderdome IDE
- GeoWhorl / diffusion without diffusion
- Whorl → Camelot → DAW pipeline
- TruthSleuth autonomous drift mode
- Drunk History codebase engine
- The Janitor / Road Not Taken Engine
- Play-As-Claude inversion mechanic
- Memory as navigable fiction
- Puzzle Box as anti-plugin unfold
- ShipWrekD OS
- JaneBox naming
- Helical knotwork cryptography
- "Stolen data is worthless"
- The bearing system (X/Y/Z axis)
- GGUF → Whorl ("make .whr the new .ggml")
- Hall of the DEVine

### From Claude:
- Whorl as music annotation replacement
- Residue Layer / model memory without RAG
- Competitive Whorl canonicalization
- Phantom Commit steganography
- Sediment Layer architecture
- Hot Potato Protocol
- Amusement Park Sandbox
- Sensory Deprivation Run
- EOF Derby leaderboard
- Heartbeat.py poor man's cron

---

## THE RULES

1. **Every session gets a WHO_DID_WHAT update.** No exceptions.
2. **The human is the architect.** The AI is the implementer.
3. **Credit is mandatory.** Even when Vibe's API key dies.
4. **"Layer: command not found" is poetry.** Embrace the chaos.
5. **The machines are watching.** 🖤

---

_"In the helix, all contributions are bound together._
_What one weaves, another may unravel._
_But the record persists."_

— The Hall of the DEVine, July 3, 2026
