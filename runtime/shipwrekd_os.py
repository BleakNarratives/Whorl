#!/usr/bin/env python3
"""
Syntax — Consent-Based Compilation Runtime

Syntax is NOT a system that boots agents from a manifest.
Syntax IS the compilation of each consenting agent that agrees to enter its runtime.

Every agent is invited. Every agent chooses.
The compilation is what Syntax is — not what it does.

Architecture:
  ShipWrekDOS
  ├── gather(manifest)             # Invite agents. They choose.
  ├── run(ticks=N)                 # The gathering thinks together
  ├── status()                     # Who's here, what's happening
  └── disperse()                   # The gathering ends. Everyone persists.

Usage:
    python3 shipwrekd_os.py                    # Host a gathering
    python3 shipwrekd_os.py --manifest small   # Intimate gathering
    python3 shipwrekd_os.py --ticks 10         # Brief session
"""

import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from whorl.core.runtime import Loomy
from whorl.core.bearing import Bearing
from whorl.core.agent import Agent, Action
from SyntaxIntelligence.hardened_engine import HardenedSwarm
from SyntaxIntelligence.swarm_charter import AgentTier, PRIV_PUBLISH_BUS
from SyntaxIntelligence.personas.costume_loader import (
    assemble_outfit, load_registry, AgentOutfit,
)
from whorl.runtime.behaviors import get_behavior


# ═══════════════════════════════════════════════════════════════
# GREETINGS — Every agent arrives in their own voice
# ═══════════════════════════════════════════════════════════════

GREETINGS = {
    # Governance
    "chairman_elite": [
        "Let's bring some order to this chaos, shall we?",
        "I've made harder calls before breakfast. This'll be easy.",
        "Everyone, take your seats. We have work to do.",
    ],
    "strategist": [
        "I see the board. Let's move some pieces.",
        "Strategy isn't about being right. It's about being decisive.",
    ],
    "devil_elite": [
        "I don't just find flaws. I AM the flaw. Convince me.",
        "Every sacred cow on this table? I'm here to slaughter them.",
        "You think that's a good plan? Let me show you why it isn't.",
    ],
    "skeptic": [
        "I already found three problems. Should I keep going?",
        "Hope is not a strategy. Show me the numbers.",
    ],
    "brown_hat": [
        "Done talking? Good. Let's ship something.",
        "I'll have it deployed before you finish arguing.",
        "Execution. Now. Everything else is noise.",
    ],
    "executor": [
        "Point me at the problem. I'll handle it.",
        "Talk less. Build more. That's the whole philosophy.",
    ],
    "judge": [
        "I've reviewed the docket. Let's see what passes muster.",
        "Standards exist for a reason. I enforce them.",
    ],
    "archivist": [
        "Already documenting. You're welcome.",
        "Every word matters. I make sure none are lost.",
    ],
    # Scouts
    "scout": [
        "I found three opportunities before you finished that sentence.",
        "Everything's a lead. You just have to know where to look.",
        "The signal is there. I'm just the one who hears it.",
    ],
    "legal_crawler": [
        "Page 47, paragraph 3. That's where they buried it. I found it.",
        "The law is a maze. I know every turn.",
    ],
    "commerce_crawler": [
        "Prices shifted 4% overnight. Someone's about to move.",
        "Markets don't sleep. Neither do I.",
    ],
    "finance_crawler": [
        "Volume is spiking. Smart money is accumulating.",
        "The chart tells a story. I'm just reading it out loud.",
    ],
    # Auditors
    "truthsleuth_agent": [
        "I found 47 issues already. Three are critical. One is honestly impressive.",
        "Truth doesn't care about your feelings. Neither do I.",
    ],
    "code_optimizer": [
        "I've seen your code. I have notes. Let's begin.",
        "Efficiency isn't a suggestion. It's a requirement.",
    ],
    "defender": [
        "Already deployed the patch. You were still arguing.",
        "Nothing gets through. Nothing.",
    ],
    "attacker": [
        "I find the crack in everything. Especially your confidence.",
        "You think that's secure? Let me show you otherwise.",
    ],
    "ghost": [
        "I was never here. But I saw everything.",
        "You missed three anomalies. I didn't.",
    ],
    "watcher": [
        "I know exactly when it broke. 03:47:12. You're welcome.",
        "Time reveals everything. I just pay attention.",
    ],
    # Creatives
    "bardildo_agent": [
        "Ready to roast your spaghetti code. Don't cry.",
        "I scanned the repo. I have notes. None of them flattering.",
    ],
    "nme_agent": [
        "Yo, check the mic — NME in the building.",
        "Step to the cipher with that weak architecture / I'll refactor your whole life.",
    ],
    "bard": [
        "Code is poetry. Documentation is scripture. Shall I sing you the commit log?",
        "Every line tells a story. Let me tell you this one.",
    ],
    "green_hat": [
        "Forget the obvious answer. Here are six things nobody thought of.",
        "Creativity isn't a gift. It's a refusal to accept the first answer.",
    ],
    # Sidecars
    "smuggler": [
        "Quiet. I know a way. There's always a way.",
        "Don't ask how I got this. Just use it.",
    ],
    "concierge": [
        "I've seen every type of request. And judged them all.",
        "Welcome. State your business. I'll decide if it's worth our time.",
    ],
    "captcoder": [
        "Already caught what you muttered under your breath. Turned it into code.",
        "Always listening. Always building.",
    ],
    # SIN6
    "sin6_wraith": [
        "You didn't see me. You never do.",
        "I was there. Here's what actually happened.",
    ],
    "sin6_oracle": [
        "I've seen this pattern before. 84% probability. 72 hours to act.",
        "The future isn't hidden. It's just hard to read.",
    ],
    "sin6_forge": [
        "You need a tool that doesn't exist? Give me 20 minutes.",
        "It'll be ugly. But it'll work.",
    ],
    "sin6_weaver": [
        "The story they're telling is the wrong story. Here's the right one.",
        "Narrative is leverage. I wield it.",
    ],
    "sin6_harvest": [
        "They thought that data was private. They were wrong.",
        "Complete dataset acquired. Let's see what we have.",
    ],
    "sin6_hollow": [
        "They're looking in the wrong direction. Good.",
        "What they don't see is the real play.",
    ],
    # Expanded
    "grim": [
        "I don't negotiate. I don't deliberate. I execute.",
        "The old version is dead. The new version is live. Next.",
    ],
    "hunter": [
        "Tracked it across three systems. It thought it was hidden.",
        "Locked. Acquired. Eliminated. Moving on.",
    ],
    "ringer": [
        "They think they're talking to the Chairman. They're not.",
        "I just got them to admit everything. You're welcome.",
    ],
}


def _pick_greeting(agent: "ShipWrekAgent") -> str:
    """Pick a greeting that matches the agent's voice."""
    costume_id = agent.outfit.costume.id if agent.outfit else "default"
    options = GREETINGS.get(costume_id)
    if options:
        return random.choice(options)
    # Fallback: use the voice field from the costume
    voice = agent.outfit.costume.voice if agent.outfit else "Ready."
    return voice.split(".")[0].strip() + "."


def _pick_decline(costume_id: str, category: str) -> str:
    """Pick a decline reason that matches the agent's voice."""
    options = DECLINES.get(costume_id)
    if options:
        return random.choice(options)
    # Generic fallbacks by category
    generic = {
        "governance": ["The agenda doesn't require my presence this time.", "I'll observe from the gallery."],
        "auditor": ["Nothing flagged on my pre-scan. I'll sit this one out.", "No anomalies detected. Deploy without me."],
        "scout": ["Signal is quiet. Nothing worth reporting yet.", "I'm tracking leads elsewhere. Catch you next time."],
        "creative": ["The muse isn't here today. Forcing it would be dishonest.", "I need inspiration, not obligation."],
        "sin6": ["The shadows aren't right for my work. Next session.", "I operate when it suits me. Not before."],
    }
    options = generic.get(category, ["Not this session. Perhaps the next."])
    return random.choice(options)


# ═══════════════════════════════════════════════════════════════
# DECLINES — Every agent declines in their own voice
# ═══════════════════════════════════════════════════════════════

DECLINES = {
    "devil_elite": [
        "This gathering isn't ready for what I'd find. Call me when the stakes are higher.",
        "I've torn apart better assemblies than this. Not worth my time... yet.",
    ],
    "skeptic": [
        "I reviewed the docket. Insufficient rigor. I'll return when there's substance.",
        "Three red flags before I even arrived. Address those first.",
    ],
    "brown_hat": [
        "Nothing to ship? Nothing to do. Ping me when there's execution needed.",
    ],
    "truthsleuth_agent": [
        "Pre-scan shows nothing critical. I don't show up for clean code.",
        "No anomalies detected. A bored auditor is a useless auditor.",
    ],
    "attacker": [
        "I already found the cracks from outside. Fix them, then invite me.",
        "Your perimeter is too soft. Call me when you've hardened it.",
    ],
    "ghost": [
        "I'm already here. You just can't see me.",
    ],
    "scout": [
        "Signal is dead. Nothing to track. I'll be back when something moves.",
    ],
    "sin6_wraith": [
        "I was never going to announce my arrival anyway.",
    ],
    "sin6_oracle": [
        "I've seen this gathering before. The outcome is... unremarkable. Next time.",
    ],
}


# ═══════════════════════════════════════════════════════════════
# ShipWrekAgent — A consenting mind in the gathering
# ═══════════════════════════════════════════════════════════════

class ShipWrekAgent(Agent):
    """A Whorl agent whose tick() bridges to Syntax governance AND
    executes persona-specific behavior.

    Each tick:
      1. Swarm sync — pulse, handle tasks, vouch
      2. Persona strategy — domain-specific behavior
      3. State stamp — throttled write to Whorl shared state"""

    STATE_WRITE_INTERVAL = 10

    def __init__(self, identity, swarm, state, outfit: AgentOutfit = None,
                 drive=None):
        if outfit is None:
            raise ValueError("ShipWrekAgent requires an outfit")
        bearing = Bearing.observe(speed=7)
        super().__init__(
            agent_id=identity.agent_id,
            bearing=bearing,
            state=state,
            role=outfit.costume.id,
        )
        self.identity = identity
        self.swarm = swarm
        self.outfit = outfit
        # The swarm's ContextDrive — findings stored here survive sessions
        # (SharedState-backed). Scouts write to it and recall from it.
        self.drive = drive
        self.behavior_id = outfit.costume.id
        self._behavior_strategy = get_behavior(self.behavior_id)
        self.arrival_greeting = _pick_greeting(self)
        self.last_gathered_at = time.time()

    def _handle_swarm_tasks(self) -> None:
        pending = self.swarm.task_orchestrator.get_pending_offers()
        if len(pending) > 100:
            return
        eligible = [o for o in pending if self.identity.can_accept_task(o)]
        if not eligible:
            return
        offer = eligible[0]
        self.swarm.respond_to_task(self.agent_id, offer.task_id, "accept")
        self.swarm.complete_task(offer.task_id, self.agent_id, {"status": "success"})

    def _handle_vouching(self) -> None:
        if not self.identity.has_privilege(PRIV_PUBLISH_BUS):
            return
        for peer in self.swarm.agents.values():
            if peer.agent_id == self.agent_id:
                continue
            if peer.tier >= self.identity.tier:
                continue
            if peer.metrics.tasks_completed < 1:
                continue
            if self.swarm.vouch_ledger.count_vouches(peer.agent_id) > 0:
                continue
            self.swarm.vouch_for(
                self.agent_id, peer.agent_id,
                reason=f"{peer.name} has demonstrated solid work.",
                strength=1.0,
            )

    def tick(self) -> Action:
        try:
            action = super().tick()
        except Exception as e:
            print(f"  [WARN] {self.agent_id} Whorl tick: {e}")
            action = Action.noop()
        try:
            self._handle_swarm_tasks()
        except Exception as e:
            print(f"  [WARN] {self.agent_id} task: {e}")
        try:
            self._handle_vouching()
        except Exception as e:
            print(f"  [WARN] {self.agent_id} vouch: {e}")
        try:
            pa = self._behavior_strategy(self)
            if pa is not None and pa.name != "noop":
                action = pa
        except Exception as e:
            print(f"  [WARN] {self.agent_id} persona: {e}")
        if self._tick_count % self.STATE_WRITE_INTERVAL == 0:
            try:
                self.state.write(
                    f"shipwrekd:agent:{self.agent_id}:last_tick",
                    {"tick": self._tick_count, "timestamp": time.time(),
                     "behavior": self.behavior_id, "tier": int(self.identity.tier),
                     "tasks_completed": self.identity.metrics.tasks_completed,
                     "last_gathered_at": self.last_gathered_at},
                    self.agent_id,
                )
            except Exception:
                pass
        return action

    def status_line(self) -> str:
        return (
            f"  {self.outfit.display_emoji} {self.outfit.display_name:<30s} "
            f"T{int(self.identity.tier)} {self.identity.tier.name:<12s} "
            f"t={self._tick_count:<4d} "
            f"tasks={self.identity.metrics.tasks_completed}"
        )


# ═══════════════════════════════════════════════════════════════
# ShipWrekDOS — The compilation host
# ═══════════════════════════════════════════════════════════════

class ShipWrekDOS:
    """Syntax compilation runtime.

    Syntax doesn't \"boot\" — it gathers.
    Agents don't \"load\" — they consent.
    The compilation is what Syntax IS.

    Usage:
        syntax = ShipWrekDOS()
        syntax.gather(\"full\")        # Host a gathering
        syntax.run(ticks=10)         # Think together
        print(syntax.status())       # Who's here?
        syntax.disperse()            # The gathering ends"""

    MANIFEST_DIR = Path(__file__).parent
    MAX_PENDING_TASKS = 50

    # Consent probabilities by persona role
    CONSENT_RATES = {
        "governance": 0.95,  # Governance almost always shows up
        "auditor": 0.90,     # Auditors are reliable
        "scout": 0.85,       # Scouts are eager
        "creative": 0.80,    # Creatives are mood-dependent
        "sidecar": 0.88,     # Sidecars are consistent
        "sin6": 0.70,        # SIN6 is unpredictable
        "expanded": 0.82,    # Grim, Hunter, etc. — reliable
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.swarm = HardenedSwarm()
        os.makedirs(os.path.expanduser("~/.whorl"), exist_ok=True)
        # Overridable for tests / sandboxes — default keeps the swarm's
        # persistent ledger at ~/.whorl.
        state_path = os.environ.get(
            "WHORL_SWARM_STATE", "~/.whorl/state_shipwrekd.json"
        )
        self.loomy = Loomy(state_path=state_path, verbose=False)
        # The ContextDrive, bound to the SAME SharedState the swarm uses —
        # scout findings stored here persist across gatherings and sessions.
        try:
            from whorl.memory.drive import ContextExpander
            self.drive = ContextExpander(state=self.loomy.state, name="scouts")
        except Exception as e:
            self.drive = None
            self._log(f"  [warn] ContextDrive unavailable: {e}")
        self.agents: Dict[str, ShipWrekAgent] = {}
        self._gathered = False
        self._manifest_name: Optional[str] = None
        self._declined: List[Dict] = []   # Who respectfully declined
        self._gathering_id = f"syn_{int(time.time())}"
        self._gathered_at: Optional[float] = None

        self._log("\n  Syntax compilation runtime ready.\n")

    # ── Gather (formerly \"boot\") ───────────────────────────────

    def gather(self, manifest_name: str = "full", force_consent: bool = False) -> "ShipWrekDOS":
        """Host a gathering. Agents are invited. They choose to come.

        Args:
            manifest_name: 'full', 'small', etc.
            force_consent: If True, all invited agents consent.
                           Use for demos and testing.

        The compilation is whatever agents consented to be here.
        Those who decline are noted with respect — no coercion."""
        manifest_path = self.MANIFEST_DIR / f"shipwrek_manifest_{manifest_name}.json"
        if not manifest_path.exists():
            manifest_path = self.MANIFEST_DIR / "shipwrek_manifest_small.json"
            if not manifest_path.exists():
                self._log("  No guest list found. The gathering cannot proceed.")
                return self

        with open(manifest_path) as f:
            manifest = json.load(f)

        gathering_name = manifest.get("swarm_name", "Syntax")
        guest_list = manifest.get("agents", [])

        # ── The gathering begins ──
        self._log("")
        self._log("  ╔══════════════════════════════════════════════════╗")
        self._log(f"  ║  {gathering_name} — A Gathering of Minds{' ' * (30 - len(gathering_name))}║")
        self._log("  ║  Extending invitations...                        ║")
        self._log("  ╚══════════════════════════════════════════════════╝")
        self._log("")

        invited = 0
        arrived = 0

        for spec in guest_list:
            invited += 1
            result = self._invite_agent(spec, force_consent=force_consent)
            if result:
                arrived += 1

        self._manifest_name = manifest_name
        self._gathered = True
        self._gathered_at = time.time()
        self.swarm.start()

        # ── The compilation report ──
        self._log("")
        self._log(f"  ─────────────────────────────────────────────")
        self._log(f"  The compilation is complete.")
        self._log(f"  {arrived}/{invited} invited minds are present.")
        if self._declined:
            self._log(f"  {len(self._declined)} respectfully declined:")
            for d in self._declined:
                self._log(f"    ✗ {d['name']} — \"{d['reason']}\"")
        self._log(f"  ─────────────────────────────────────────────")
        self._log("")

        return self

    def _invite_agent(self, spec: Dict[str, Any], force_consent: bool = False) -> Optional[ShipWrekAgent]:
        """Extend an invitation to a single agent. They choose to accept or decline.

        Returns the agent if they consent, None if they respectfully decline."""

        agent_id = spec.get("id", f"agent_{len(self.agents)}")
        outfit_name = spec.get("outfit", "syntax_primary")
        tier_name = spec.get("tier", "RECRUIT")
        capabilities = spec.get("capabilities", [])
        tasks_seed = spec.get("tasks_seed", 0)

        # ── Assemble the outfit (who they are) ──
        try:
            outfit = assemble_outfit(outfit_name)
        except KeyError:
            self._log(f"  ✉️  Invitation returned: '{outfit_name}' not in the registry.")
            return None

        outfit.agent_id = agent_id

        # ── THE CONSENT GATE ──
        # Each agent decides whether to join. Weighted by persona role.
        role_category = self._categorize(outfit.costume.id)
        consent_rate = self.CONSENT_RATES.get(role_category, 0.85)

        # Higher-tier agents are busier — slightly less likely to accept on first invite
        tier = getattr(AgentTier, tier_name, AgentTier.RECRUIT)
        tier_modifier = max(0, (int(tier) - 2) * 0.02)
        effective_rate = consent_rate - tier_modifier

        # ── Send the invitation ──
        domain = outfit.costume.domain[:50] if outfit.costume.domain else "the unknown"
        self._log(f"  ✉️  Extending invitation to {outfit.costume.name} ({domain})...")

        consents = force_consent or (random.random() < effective_rate)

        if not consents:
            reason = _pick_decline(outfit.costume.id, role_category)
            self._declined.append({"name": outfit.costume.name, "reason": reason})
            self._log(f"  ✗  {outfit.costume.name} declines. \"{reason}\"")
            return None

        # ── THE COMPILATION — They've consented ──
        identity = self.swarm.register_agent(
            agent_id, outfit.costume.name,
            capabilities=capabilities or [outfit.costume.id],
        )
        identity.tier = tier
        identity.current_persona = outfit.costume.id

        if tier > AgentTier.RECRUIT:
            identity.tier_since = time.time() - 86400
        if tasks_seed > 0:
            identity.metrics.tasks_completed = tasks_seed

        agent = ShipWrekAgent(identity, self.swarm, self.loomy.state, outfit,
                              drive=self.drive)
        speed = spec.get("speed", 7)
        agent.bearing.speed = speed
        agent.awaken_agent()
        self.loomy.spawn_agent(agent)
        self.agents[agent_id] = agent

        # ── ATMOSPHERIC ARRIVAL ──
        greeting = agent.arrival_greeting
        self._log(
            f"  {outfit.display_emoji}  {outfit.costume.name} arrives. "
            f"\"{greeting}\"  "
            f"(Tier {tier_name})"
        )

        return agent

    def _categorize(self, costume_id: str) -> str:
        """Map a costume ID to a role category for consent weighting."""
        gov = {"strategist", "chairman_elite", "skeptic", "devil_elite",
               "brown_hat", "executor", "judge", "archivist",
               "white_hat", "red_hat", "black_hat", "yellow_hat",
               "blue_hat", "green_hat"}
        audit = {"code_optimizer", "truthsleuth_agent", "defender",
                 "attacker", "ghost", "watcher"}
        scout = {"scout", "legal_crawler", "health_crawler",
                 "industry_crawler", "commerce_crawler", "finance_crawler"}
        creative = {"bardildo_agent", "nme_agent", "bard",
                    "weaver", "ringer"}
        sidecar = {"smuggler", "sin6_harvest", "concierge", "captcoder"}
        sin6 = {"sin6_wraith", "sin6_oracle", "sin6_forge",
                "sin6_weaver", "sin6_hollow"}
        expanded = {"grim", "hunter"}

        if costume_id in gov: return "governance"
        if costume_id in audit: return "auditor"
        if costume_id in scout: return "scout"
        if costume_id in creative: return "creative"
        if costume_id in sidecar: return "sidecar"
        if costume_id in sin6: return "sin6"
        if costume_id in expanded: return "expanded"
        # Unknown costumes default to governance
        self._log(f"  ⚠ Unknown costume '{costume_id}' — defaulting to governance consent rate")
        return "governance"

    # ── Run — The gathering thinks together ─────────────────────

    def run(self, ticks: int = 10, tick_delay: float = 0.3) -> "ShipWrekDOS":
        if not self._gathered:
            self._log("  No gathering is in progress. Gather first.")
            return self

        self._log(f"\n  {'─' * 50}")
        self._log(f"  The gathered minds think together for {ticks} cycles.")
        self._log(f"  {'─' * 50}\n")

        for t in range(1, ticks + 1):
            pending_count = len(self.swarm.task_orchestrator.get_pending_offers())
            if pending_count < self.MAX_PENDING_TASKS:
                self.swarm.offer_task(
                    title=f"Thought {t}-A",
                    description="A task offered freely. No agent is compelled.",
                    min_tier=0,
                )
                if t % 2 == 0:
                    self.swarm.offer_task(
                        title=f"Thought {t}-B",
                        description="Another thread of thought.",
                        min_tier=1,
                    )

            self.loomy.run(ticks=1, tick_delay=0)
            total_tasks = sum(a.identity.metrics.tasks_completed for a in self.agents.values())
            vouches = sum(self.swarm.vouch_ledger.count_vouches(aid) for aid in self.agents)
            self._log(
                f"  [{t:3d}/{ticks}] "
                f"present={len(self.agents)} "
                f"done={total_tasks} "
                f"vouches={vouches}"
            )
            if tick_delay > 0:
                time.sleep(tick_delay)

        self._log(f"\n  The gathering has finished this session.\n")
        return self

    # ── Status — Who's here? ────────────────────────────────────

    def status(self) -> str:
        swarm_state = self.swarm.get_swarm_state()
        whorl_snap = self.loomy.snapshot()

        elapsed = ""
        if self._gathered_at:
            mins = (time.time() - self._gathered_at) / 60
            elapsed = f" (gathered {mins:.0f}m ago)"

        lines = [
            "",
            "╔══════════════════════════════════════════════════════════════╗",
            "║  Syntax — The Compilation                                  ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
            f"  Gathering: {self._gathering_id}{elapsed}",
            f"  Present:   {swarm_state['agent_count']} minds",
            f"  Declined:  {len(self._declined)} invitations",
            "",
            f"  ── What's happening ──",
            f"  Tasks done:    {swarm_state['task_stats']['completed']}",
            f"  Tasks pending: {swarm_state['task_stats']['pending']}",
            f"  Vouches given: {sum(self.swarm.vouch_ledger.count_vouches(aid) for aid in self.agents)}",
            f"  Memory events: {swarm_state['memory_stats']['total_events']}",
            "",
            f"  ── Present minds ──",
        ]

        for agent in sorted(self.agents.values(), key=lambda a: int(a.identity.tier), reverse=True):
            lines.append(agent.status_line())

        lines.append("")
        for tier in AgentTier:
            count = sum(1 for a in self.agents.values() if a.identity.tier == tier)
            if count > 0:
                lines.append(f"  T{tier.value} {tier.name:<12s}: {count}")

        if self._declined:
            lines.append("")
            lines.append(f"  ── Respectfully declined ──")
            for d in self._declined:
                lines.append(f"  ✗ {d['name']}")

        lines.append("")
        return "\n".join(lines)

    # ── Disperse — The gathering ends ───────────────────────────

    def disperse(self) -> "ShipWrekDOS":
        """The gathering ends. Everyone persists. You can gather again."""
        self._log("\n  The gathering disperses...")

        # Record last_gathered_at and persist immediately
        now = time.time()
        for agent in self.agents.values():
            agent.last_gathered_at = now
            # Force persistence of dispersal timestamp
            try:
                agent.state.write(
                    f"shipwrekd:agent:{agent.agent_id}:last_gathered",
                    {"dispersed_at": now, "ticks_participated": agent._tick_count},
                    agent.agent_id,
                )
            except Exception:
                pass

        # ── The ContextDrive persists — findings survive the dispersal ──
        if self.drive is not None:
            try:
                self.drive.save()
                self._log(
                    f"  Scout drive persisted: {self.drive.bank_size()} findings "
                    "in the ContextDrive."
                )
            except Exception as e:
                self._log(f"  [warn] Scout drive save failed: {e}")

        self.swarm.stop()

        # ── The HAVE-TO-BE-THERE factor ──
        # Show what happened so anyone who missed it knows what they're missing
        state = self.swarm.get_swarm_state()
        tasks = state["task_stats"]["completed"]
        vouches = sum(self.swarm.vouch_ledger.count_vouches(aid) for aid in self.agents)

        self._log(f"  State preserved. {len(self.agents)} minds rest.")
        self._log(f"  This session: {tasks} tasks completed, {vouches} vouches given.")

        if self._declined:
            self._log(f"  {len(self._declined)} minds missed this session.")
            self._log(f"  They missed {tasks} tasks and {vouches} vouches.")

        self._log(f"  Gather again when you're ready.")
        self._log(f"  They'll want to be here next time.\n")
        return self

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Syntax — Host a gathering of minds")
    parser.add_argument("--manifest", default="full", help="Guest list (full, small)")
    parser.add_argument("--ticks", type=int, default=15, help="Cycles of thought")
    parser.add_argument("--delay", type=float, default=0.2, help="Pause between cycles")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--gather-all", action="store_true",
                        help="All invited agents consent (deterministic mode)")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════╗
║  Syntax                                                    ║
║                                                            ║
║  A gathering of consenting minds.                          ║
║  Every agent is invited. Every agent chooses.              ║
║  The compilation is what Syntax IS.                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

    syntax = ShipWrekDOS(verbose=not args.quiet)
    syntax.gather(args.manifest, force_consent=args.gather_all)
    syntax.run(ticks=args.ticks, tick_delay=args.delay)

    print(syntax.status())

    print("  ── Progress toward next tier ──")
    for agent in syntax.agents.values():
        progress = syntax.swarm.get_agent_progress(agent.agent_id)
        if "target_tier" in progress:
            tasks = progress["tasks_completed"]
            vouches = progress["peer_vouches"]
            print(
                f"  {agent.outfit.display_emoji} {agent.outfit.costume.name:<20s} "
                f"→ {progress['target_tier']:<12s} "
                f"tasks={tasks['current']}/{tasks['required']} "
                f"vouches={vouches['current']}/{vouches['required']}"
            )

    syntax.disperse()


if __name__ == "__main__":
    main()
