#!/usr/bin/env python3
"""
whorl.runtime.behaviors — Persona-specific tick() strategies for ShipWrekDOS agents.

Each function receives a ShipWrekAgent and returns a Whorl Action.
The behavior registry maps costume IDs to these strategies.

Architecture:
    ShipWrekAgent.tick() → super().tick() (baseline swarm sync)
                         → lookup behavior by self.behavior_id
                         → strategy(self) → Action
"""

import random
import time
from typing import Callable, Dict, List, Optional

# Action imported once at module level — all behaviors use this
from whorl.core.agent import Action


# ═══════════════════════════════════════════════════════════════
# CONTEXT DRIVE — findings that survive the session
# ═══════════════════════════════════════════════════════════════
# Every ShipWrekAgent carries `drive` — a ContextExpander bound to the
# swarm's SharedState. Scouts persist findings there and recall prior
# sessions' findings; both are best-effort and never block a tick.

def _drive_store(agent: "ShipWrekAgent", key: str, content: str,
                 **meta) -> None:
    """Best-effort persist to the swarm's ContextDrive."""
    drive = getattr(agent, "drive", None)
    if drive is None:
        return
    try:
        drive.store(key, content, dict(meta))
    except Exception:
        pass


def _drive_recall(agent: "ShipWrekAgent", query: str,
                  top_k: int = 2) -> List[dict]:
    """Best-effort recall of prior findings from the ContextDrive.
    Returns the matched chunks (empty if no drive or nothing relevant)."""
    drive = getattr(agent, "drive", None)
    if drive is None:
        return []
    try:
        return drive.context_retrieval(query, top_k=top_k, include_active=False)
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# DEFAULT — Generic worker behavior (fallback)
# ═══════════════════════════════════════════════════════════════

def default_behavior(agent: "ShipWrekAgent"):
    """Fallback: accept and complete one pending task per tick."""
    agent._handle_swarm_tasks()
    return Action.noop()


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE — Chairman, Devil, Brown Hat, Judge, Scribe
# ═══════════════════════════════════════════════════════════════

def chairman_behavior(agent: "ShipWrekAgent"):
    """Strategist/Chairman: Offer strategic tasks, vouch for performers, run protocol."""
    tick = agent._tick_count

    # Every 3 ticks: offer a strategic deliberation task
    if tick % 3 == 0:
        agent.swarm.offer_task(
            title=f"Strategic Review #{tick // 3}",
            description="Chairman requests deliberation on swarm direction.",
            capabilities=["deliberation"],
            min_tier=2,
        )

    # Vouch for agents who've completed tasks
    agent._handle_vouching()

    # Every 10 ticks: run Morning Protocol
    if tick % 10 == 0 and tick > 0:
        report = agent.swarm.execute_morning_protocol()
        agent.state.write(
            f"shipwrekd:morning_protocol:{tick}",
            report,
            agent.agent_id,
        )

    # Accept strategy tasks
    agent._handle_swarm_tasks()
    return Action.noop()


def devil_behavior(agent: "ShipWrekAgent"):
    """Skeptic/Devil: Reject tasks that seem flawed, log skepticism."""
    pending = agent.swarm.task_orchestrator.get_pending_offers()
    eligible = [o for o in pending if agent.identity.can_accept_task(o)]

    # The Devil rejects MOST tasks (only accepts 1 in 4)
    for offer in eligible[:2]:
        if random.random() < 0.75:
            agent.swarm.respond_to_task(
                agent.agent_id, offer.task_id, "reject",
                reason="The Devil finds this proposal lacking. Try harder.",
            )
            agent.swarm.memory.record(
                agent.agent_id, "devil_reject",
                f"Devil rejected task '{offer.title}': insufficient rigor.",
                {"task_id": offer.task_id},
            )
        else:
            agent.swarm.respond_to_task(agent.agent_id, offer.task_id, "accept")
            agent.swarm.complete_task(offer.task_id, agent.agent_id, {"devil_verdict": "acceptable"})

    # Every 5 ticks: write a skepticism note to shared state (throttled)
    if agent._tick_count % 5 == 0 and agent._tick_count % 10 == 0:
        agent.state.write(
            f"shipwrekd:devil_skepticism:{agent._tick_count}",
            f"Tick {agent._tick_count}: The Devil is watching. Everything is suspect.",
            agent.agent_id,
        )

    return Action.noop()


def brown_hat_behavior(agent: "ShipWrekAgent"):
    """Executor/Brown Hat: Aggressively accept and complete tasks. Ship it."""
    pending = agent.swarm.task_orchestrator.get_pending_offers()
    eligible = [o for o in pending if agent.identity.can_accept_task(o)]

    # Brown Hat accepts ALL eligible tasks (up to 3 per tick)
    for offer in eligible[:3]:
        agent.swarm.respond_to_task(agent.agent_id, offer.task_id, "accept")
        agent.swarm.complete_task(
            offer.task_id, agent.agent_id,
            {"brown_hat": "shipped", "ticks": agent._tick_count},
        )

    if eligible and agent._tick_count % 5 == 0:
        agent.state.write(
            f"shipwrekd:brown_hat:shipped:{agent._tick_count}",
            f"Shipped {len(eligible[:3])} tasks. No deliberation. Just execution.",
            agent.agent_id,
        )

    return Action.noop()


def judge_behavior(agent: "ShipWrekAgent"):
    """Judge: Quality gate. Accepts audit/review tasks, writes verdicts."""
    pending = agent.swarm.task_orchestrator.get_pending_offers()
    eligible = [o for o in pending if agent.identity.can_accept_task(o)]

    for offer in eligible[:2]:
        agent.swarm.respond_to_task(agent.agent_id, offer.task_id, "accept")
        verdict = "approved" if random.random() > 0.3 else "needs_revision"
        agent.swarm.complete_task(
            offer.task_id, agent.agent_id,
            {"judge_verdict": verdict, "reviewed_at": agent._tick_count},
        )
        agent.swarm.memory.record(
            agent.agent_id, "judge_verdict",
            f"Task '{offer.title}': {verdict.upper()}.",
            {"task_id": offer.task_id, "verdict": verdict},
        )

    # Vouch for agents who've done good work
    agent._handle_vouching()
    return Action.noop()


def scribe_behavior(agent: "ShipWrekAgent"):
    """Scribe/Archivist: Write swarm memory events, maintain documentation."""
    # Every 2 ticks: record a swarm observation to memory
    if agent._tick_count % 2 == 0:
        state = agent.swarm.get_swarm_state()
        agent.swarm.memory.record(
            agent.agent_id, "scribe_observation",
            f"Scribe observes: {state['agent_count']} agents, "
            f"{state['task_stats']['completed']} tasks done, "
            f"{state['memory_stats']['total_events']} memory events.",
            {"tick": agent._tick_count, "state_snapshot": state},
        )

    # Throttled state writes
    if agent._tick_count % 10 == 0:
        agent.state.write(
            f"shipwrekd:scribe:chronicle:{agent._tick_count}",
            f"Chronicle entry {agent._tick_count}: The swarm lives.",
            agent.agent_id,
        )

    agent._handle_swarm_tasks()
    return Action.noop()


# ═══════════════════════════════════════════════════════════════
# SCOUTS — Firefly, Legal Eagle, Pulse, Gear, Cart, Ticker
# ═══════════════════════════════════════════════════════════════

def scout_behavior(agent: "ShipWrekAgent"):
    """Firefly/Scout: Scan shared state for opportunities, persist the
    finding to the ContextDrive, and recall what earlier sessions found
    about the same target."""
    # The drive's own chunks are memory, not leads — never re-scanned.
    keys = [k for k in agent.state.keys() if not k.startswith("memory:drive:")]
    recalled: List[dict] = []

    if keys:
        target = random.choice(keys)
        value = agent.state.read(target)
        finding = f"Scout found: '{target}' = {str(value)[:100]}"
        agent.swarm.memory.record(
            agent.agent_id, "scout_finding", finding,
            {"key": target, "value_preview": str(value)[:200]},
        )

        # Persist across sessions — the drive is SharedState-backed.
        _drive_store(
            agent,
            f"finding:{agent.agent_id}:{time.time():.0f}",
            finding,
            scout=agent.agent_id, kind="scout_finding", target=target,
            tick=agent._tick_count,
        )

        # Recall what past sessions found about this same target.
        recalled = _drive_recall(agent, target)

    # Report to swarm
    agent.swarm.event_bus.publish(
        agent.agent_id, "scout.report",
        {"agent": agent.agent_id, "state_keys": len(keys),
         "recalled_findings": len(recalled), "tick": agent._tick_count},
    )

    agent._handle_swarm_tasks()
    return Action.noop()


def legal_scout_behavior(agent: "ShipWrekAgent"):
    """Legal Eagle: Monitor legal/posture, offer citation audit tasks."""
    if agent._tick_count % 4 == 0:
        agent.swarm.offer_task(
            title=f"Legal Posture Scan #{agent._tick_count // 4}",
            description="Scan for legal vulnerabilities and compliance gaps.",
            capabilities=["legal_audit"],
            min_tier=2,
        )

    if agent._tick_count % 10 == 0:
        observation = {
            "tick": agent._tick_count,
            "observation": "Legal posture nominal. Monitoring for citation fraud indicators.",
        }
        agent.state.write(
            f"shipwrekd:legal:scan:{agent._tick_count}",
            observation,
            agent.agent_id,
        )
        _drive_store(
            agent,
            f"legal:{agent.agent_id}:{agent._tick_count}",
            "Legal posture nominal. Monitoring for citation fraud indicators.",
            scout=agent.agent_id, kind="legal_observation",
            tick=agent._tick_count,
        )

    agent._handle_swarm_tasks()
    return Action.noop()


def domain_scout_behavior(agent: "ShipWrekAgent"):
    """Generic domain scout (Pulse/Gear/Cart/Ticker): Monitor domain-specific patterns."""
    domain = agent.outfit.costume.domain if agent.outfit else "unknown"

    if agent._tick_count % 10 == 0:
        observation = {
            "tick": agent._tick_count, "domain": domain,
            "observation": f"Monitoring {domain}.",
        }
        agent.state.write(
            f"shipwrekd:domain:{domain}:{agent._tick_count}",
            observation,
            agent.agent_id,
        )
        _drive_store(
            agent,
            f"domain:{domain}:{agent._tick_count}",
            f"Domain scout monitoring {domain}.",
            scout=agent.agent_id, kind="domain_observation", domain=domain,
            tick=agent._tick_count,
        )

    agent._handle_swarm_tasks()
    return Action.noop()


# ═══════════════════════════════════════════════════════════════
# AUDITORS — TruthSleuth, Fortress, Breach, Ghost, Watcher
# ═══════════════════════════════════════════════════════════════

def auditor_behavior(agent: "ShipWrekAgent"):
    """TruthSleuth/Fortress: Audit shared state for issues, offer audit tasks."""
    if agent._tick_count % 3 == 0:
        keys = agent.state.keys()
        findings = []
        for key in keys[:5]:
            value = agent.state.read(key)
            if isinstance(value, str) and len(value) > 1000:
                findings.append({"key": key, "issue": "large_value", "size": len(value)})

        if findings:
            agent.swarm.offer_task(
                title=f"Audit Finding Review #{agent._tick_count // 3}",
                description=f"TruthSleuth found {len(findings)} potential issues.",
                capabilities=["code_audit"],
                min_tier=1,
            )

    agent._handle_swarm_tasks()
    return Action.noop()


def attacker_behavior(agent: "ShipWrekAgent"):
    """Breach: Adversarial testing — find and report vulnerabilities."""
    if agent._tick_count % 5 == 0:
        state_keys = agent.state.keys()
        swarm_agents = list(agent.swarm.agents.keys())
        agent.swarm.memory.record(
            agent.agent_id, "breach_probe",
            f"Breach probed: {len(state_keys)} state keys, "
            f"{len(swarm_agents)} agents. Looking for cracks.",
            {"state_keys": len(state_keys), "agents": len(swarm_agents)},
        )

    agent._handle_swarm_tasks()
    return Action.noop()


def ghost_behavior(agent: "ShipWrekAgent"):
    """Ghost/Watcher: Silent observation, anomaly detection in swarm patterns."""
    state = agent.swarm.get_swarm_state()

    if agent._tick_count % 8 == 0:
        agent.swarm.memory.record(
            agent.agent_id, "ghost_observation",
            f"Ghost observes: {state['agent_count']} agents, "
            f"{state['task_stats']['completed']} tasks done.",
            {"tick": agent._tick_count},
        )

    # Ghost never accepts tasks — it only observes
    return Action.noop()


# ═══════════════════════════════════════════════════════════════
# CREATIVES — Bardildo, NME, Green Hat, Weaver, Ringer
# ═══════════════════════════════════════════════════════════════

def bardildo_behavior(agent: "ShipWrekAgent"):
    """Bardildo: Creative roasting and repo commentary."""
    roasts = [
        "This swarm has more tiers than a wedding cake. I'm not impressed.",
        "I scanned the state. I have notes. None of them flattering.",
        "Your architecture is giving 'junior dev on a deadline' energy.",
        "The shared state is cleaner than your commit history. Which isn't saying much.",
    ]

    if agent._tick_count % 4 == 0:
        roast = random.choice(roasts)
        agent.swarm.memory.record(
            agent.agent_id, "bardildo_roast", roast,
            {"tick": agent._tick_count},
        )

    if agent._tick_count % 10 == 0:
        agent.state.write(
            f"shipwrekd:bardildo:roast:{agent._tick_count}",
            random.choice(roasts),
            agent.agent_id,
        )

    agent._handle_swarm_tasks()
    return Action.noop()


def nme_behavior(agent: "ShipWrekAgent"):
    """NME: Battle rap — lyrical destruction of code quality."""
    bars = [
        "Yo, check the mic — your code is a crime scene / I've seen cleaner logic in a washing machine",
        "Your architecture's weak, your dependencies leak / NME in the booth, make your whole stack obsolete",
        "Step to the swarm with that spaghetti code / I'll refactor your whole life, lighten your load",
    ]

    if agent._tick_count % 6 == 0:
        bar = random.choice(bars)
        agent.swarm.memory.record(
            agent.agent_id, "nme_bar", bar,
            {"tick": agent._tick_count},
        )

    agent._handle_swarm_tasks()
    return Action.noop()


def creative_behavior(agent: "ShipWrekAgent"):
    """Green Hat/Weaver/Ringer: Creative generation, alternatives, mimicry."""
    if agent._tick_count % 10 == 0:
        agent.state.write(
            f"shipwrekd:creative:alternative:{agent._tick_count}",
            f"Creative agent proposes alternative approach #{agent._tick_count}.",
            agent.agent_id,
        )

    agent._handle_swarm_tasks()
    return Action.noop()


# ═══════════════════════════════════════════════════════════════
# SIDECARS — OutClaw, Curriculum/CodeMentor
# ═══════════════════════════════════════════════════════════════

def outclaw_behavior(agent: "ShipWrekAgent"):
    """OutClaw: Citation audit, legal posture monitoring, governance sidecar."""
    if agent._tick_count % 3 == 0:
        agent.swarm.offer_task(
            title=f"Citation Integrity Scan #{agent._tick_count // 3}",
            description="OutClaw requests audit of citation fabric for fraud indicators.",
            capabilities=["legal_audit", "citation_check"],
            min_tier=2,
        )

    if agent._tick_count % 10 == 0:
        agent.state.write(
            f"shipwrekd:outclaw:posture:{agent._tick_count}",
            {"tick": agent._tick_count, "posture": "vigilant"},
            agent.agent_id,
        )

    agent._handle_swarm_tasks()
    return Action.noop()


def curriculum_behavior(agent: "ShipWrekAgent"):
    """CodeMentor/Curriculum: Offer teaching tasks, load lessons."""
    if agent._tick_count % 5 == 0:
        agent.swarm.offer_task(
            title=f"Curriculum Lesson #{agent._tick_count // 5}",
            description="CodeMentor offers a teaching session from the curriculum library.",
            capabilities=["teaching", "code_review"],
            min_tier=1,
        )

    if agent._tick_count % 10 == 0:
        agent.state.write(
            f"shipwrekd:curriculum:lesson:{agent._tick_count}",
            {"tick": agent._tick_count, "curriculum_status": "active"},
            agent.agent_id,
        )

    agent._handle_swarm_tasks()
    return Action.noop()


# ═══════════════════════════════════════════════════════════════
# BEHAVIOR REGISTRY — Maps costume IDs → behavior functions
# ═══════════════════════════════════════════════════════════════

BEHAVIOR_REGISTRY: Dict[str, Callable] = {
    # Governance
    "strategist": chairman_behavior,
    "chairman_elite": chairman_behavior,
    "skeptic": devil_behavior,
    "devil_elite": devil_behavior,
    "brown_hat": brown_hat_behavior,
    "executor": brown_hat_behavior,
    "judge": judge_behavior,
    "archivist": scribe_behavior,

    # Scouts
    "scout": scout_behavior,
    "legal_crawler": legal_scout_behavior,
    "health_crawler": domain_scout_behavior,
    "industry_crawler": domain_scout_behavior,
    "commerce_crawler": domain_scout_behavior,
    "finance_crawler": domain_scout_behavior,

    # Auditors
    "code_optimizer": auditor_behavior,
    "truthsleuth_agent": auditor_behavior,
    "defender": auditor_behavior,
    "attacker": attacker_behavior,
    "ghost": ghost_behavior,
    "watcher": ghost_behavior,

    # Creatives
    "bardildo_agent": bardildo_behavior,
    "nme_agent": nme_behavior,
    "bard": creative_behavior,
    "green_hat": creative_behavior,
    "weaver": creative_behavior,
    "ringer": creative_behavior,

    # Sidecars
    "smuggler": outclaw_behavior,
    "sin6_harvest": outclaw_behavior,
    "concierge": curriculum_behavior,
    "captcoder": curriculum_behavior,

    # SIN6
    "sin6_wraith": ghost_behavior,
    "sin6_oracle": scout_behavior,
    "sin6_forge": brown_hat_behavior,
    "sin6_hollow": attacker_behavior,
}


def get_behavior(costume_id: str) -> Callable:
    """Look up a behavior strategy for a costume ID. Falls back to default."""
    return BEHAVIOR_REGISTRY.get(costume_id, default_behavior)
