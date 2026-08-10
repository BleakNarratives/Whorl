#!/usr/bin/env python3
"""
Whorl <-> SyntaxIntelligence Helical Runtime (Multi-Agent)

Demonstrates multiple helical agents hosted in Whorl's Loomy runtime,
holding registered identities in SyntaxIntelligence's HardenedSwarm.

Agents complete the Whorl helical cycle while syncing with the Swarm:
  - pulse / accept / complete tasks
  - higher-tier agents vouch for lower-tier peers
  - tier progression is evaluated after completions and vouches
"""

import os
import sys
import time
from pathlib import Path

# Ensure we can import from the project root when run directly
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from whorl.core.runtime import Loomy
from whorl.core.bearing import Bearing
from whorl.core.agent import Agent, Action
from SyntaxIntelligence.hardened_engine import HardenedSwarm
from SyntaxIntelligence.swarm_charter import AgentTier, PRIV_PUBLISH_BUS


class SyntaxHelicalAgent(Agent):
    """
    A Whorl agent whose tick cycle is bridged to SyntaxIntelligence.

    It completes the Whorl helical loop while syncing with the
    HardenedSwarm: pulse, accept offered tasks, complete them, and
    (if privileged) vouch for lower-tier peers.
    """

    def __init__(self, identity, swarm, state):
        super().__init__(
            agent_id=identity.agent_id,
            bearing=Bearing.observe(speed=10),
            state=state,
            role="syntax-worker",
        )
        self.identity = identity
        self.swarm = swarm

    def _handle_swarm_tasks(self) -> None:
        """Accept and complete one pending task per tick, if eligible."""
        pending_offers = self.swarm.task_orchestrator.get_pending_offers()
        eligible_offers = [o for o in pending_offers if self.identity.can_accept_task(o)]
        if not eligible_offers:
            print("  └─> [DECIDE] No eligible tasks to accept")
            return

        offer = eligible_offers[0]
        print(f"  └─> [DECIDE] Accepting task: '{offer.title}'")
        self.swarm.respond_to_task(self.agent_id, offer.task_id, "accept")
        print(f"  └─> [ACT] Completing task: '{offer.title}'")
        self.swarm.complete_task(offer.task_id, self.agent_id, {"status": "success"})

    def _handle_vouching(self) -> None:
        """If this agent can publish on the bus, vouch for competent peers."""
        print(f"  DEBUG {self.agent_id} tier={self.identity.tier} privs={self.identity.get_privileges()} has_publish={self.identity.has_privilege(PRIV_PUBLISH_BUS)}")
        if not self.identity.has_privilege(PRIV_PUBLISH_BUS):
            return

        for peer in self.swarm.agents.values():
            if peer.agent_id == self.agent_id:
                continue
            if peer.tier >= self.identity.tier:
                continue  # Only vouch for agents at a lower tier
            if peer.metrics.tasks_completed < 1:
                continue  # Wait until the peer has actually done something

            # Vouch once per peer per session
            existing_vouches = self.swarm.vouch_ledger.count_vouches(peer.agent_id)
            if existing_vouches > 0:
                continue

            reason = f"{peer.name} has demonstrated solid work."
            print(f"  └─> [VOUCH] {self.agent_id} vouches for {peer.agent_id}")
            result = self.swarm.vouch_for(self.agent_id, peer.agent_id, reason, strength=1.0)
            if result.get("status") != "vouched":
                print(f"  └─> [VOUCH DENIED] {result.get('reason', 'unknown')}")

    def tick(self) -> Action:
        # Whorl base helical cycle: observe -> decide -> act -> signal
        try:
            action = super().tick()
        except Exception as exc:
            print(f"  └─> [WARN] Whorl tick error: {exc}")
            action = Action.noop()

        # Sync with SyntaxIntelligence swarm identity
        print(f"[{self.avatar.glyph} PULSE] {self.agent_id} ({self.identity.tier.name}) syncing with HardenedSwarm...")

        try:
            self._handle_swarm_tasks()
        except Exception as exc:
            print(f"  └─> [WARN] Swarm task handling error: {exc}")

        try:
            self._handle_vouching()
        except Exception as exc:
            print(f"  └─> [WARN] Swarm vouching error: {exc}")

        return action


def spawn_runtime_agent(swarm, loomy, agent_id, name, tier, capabilities=None):
    """Register a SyntaxIntelligence identity and spawn its Whorl agent."""
    identity = swarm.register_agent(agent_id, name, capabilities=capabilities or ["demo"])
    identity.tier = tier
    # DEMO SHORTCUT: backdate tier_since so the demo can show advancement
    # without waiting for real-world hours to pass. In a production runtime
    # the agent would naturally satisfy the time-in-tier requirement.
    identity.tier_since = time.time() - 86400

    bridge = SyntaxHelicalAgent(identity, swarm, loomy.state)
    bridge.awaken_agent()
    loomy.spawn_agent(bridge)
    return identity, bridge


def main():
    print("=== Booting Whorl <-> SyntaxIntelligence Multi-Agent Runtime ===\n")

    # 1. Initialize SyntaxIntelligence swarm
    swarm = HardenedSwarm()

    # 2. Initialize Whorl Loomy runtime (state must live under ~/.whorl)
    os.makedirs(os.path.expanduser("~/.whorl"), exist_ok=True)
    loomy = Loomy(state_path="~/.whorl/state_syntax_bridge.json", verbose=False)

    # 3. Register a small swarm of agents at different tiers.
    #    The Specialist can vouch for the Workers.
    #    Workers are seeded near the Specialist threshold so a single
    #    vouch can advance them in the demo.
    roster = [
        ("syn-supervisor", "Supervisor", AgentTier.SPECIALIST),
        ("syn-worker-a", "Worker Alpha", AgentTier.WORKER),
        ("syn-worker-b", "Worker Beta", AgentTier.WORKER),
    ]

    print("--- Registering agents ---")
    for agent_id, name, tier in roster:
        spawn_runtime_agent(swarm, loomy, agent_id, name, tier)
        print(f"  Registered {agent_id} as {tier.name}")

    # Seed the workers with enough completed tasks that a single vouch can
    # push them over the WORKER -> SPECIALIST threshold in this short demo.
    for agent_id, _, _ in roster:
        if agent_id != "syn-supervisor":
            swarm.agents[agent_id].metrics.tasks_completed = 10
            print(f"  Seeded {agent_id} with 10 prior completed tasks")

    # 4. Run the bridged helical loop.
    #    Each tick offers a couple of demo tasks, then pulses all agents.
    for tick_num in range(1, 6):
        print(f"\n--- Tick {tick_num} ---")
        swarm.offer_task(title=f"Demo Routine {tick_num}-A", description="A bridged test task", min_tier=0)
        swarm.offer_task(title=f"Demo Routine {tick_num}-B", description="A bridged test task", min_tier=0)
        loomy.run(ticks=1, tick_delay=0)

    # 5. Report runtime status
    print("\n=== Whorl Loomy Runtime Report ===")
    print(loomy.report())

    print("\n=== SyntaxIntelligence Agent Metrics ===")
    for agent_id, name, _ in roster:
        agent_state = swarm.agents.get(agent_id)
        if not agent_state:
            continue
        vouches = swarm.vouch_ledger.count_vouches(agent_id)
        print(f"\n  {agent_id} — {agent_state.name}")
        print(f"    Tier:        {agent_state.tier.name}")
        print(f"    Completed:   {agent_state.metrics.tasks_completed} tasks")
        print(f"    Vouches:     {vouches} received, {agent_state.metrics.peer_vouches_given} given")
        progress = swarm.get_agent_progress(agent_id)
        if "target_tier" in progress:
            print(f"    Progress to {progress['target_tier']}: tasks={progress['tasks_completed']['current']}/{progress['tasks_completed']['required']}, vouches={progress['peer_vouches']['current']}/{progress['peer_vouches']['required']}")

    print("\n=== Vouch Ledger ===")
    for agent_id, _, _ in roster:
        vouches = swarm.vouch_ledger.get_vouches_for(agent_id)
        if vouches:
            print(f"  {agent_id} was vouched for by:")
            for v in vouches:
                print(f"    - {v['from']}: {v['reason']}")

    print("\nHelical runtime stub shutting down.")


if __name__ == "__main__":
    main()
