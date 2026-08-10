"""
whorl.core.runtime — Loomy: the Whorl runtime.

Loomy hosts agents, manages the shared state, and drives the event loop.
Agents tick at rates proportional to their bearing speed; faster agents
get more cycles per round.

The runtime name "Loomy" comes from the 3D polywoven topography concept:
the knowledge graph is a woven surface that agents navigate.

Usage:
    loomy = Loomy(state_path="state.json")
    loomy.spawn("scout-1", bearing=Bearing.observe(speed=7), role="market-scout")
    loomy.run(ticks=100, tick_delay=0.1)
"""

import time
import signal
import sys
from dataclasses import dataclass, field
from typing import Optional

from .bearing import Bearing
from .state import SharedState
from .agent import Agent, Action


# ─── Runtime Event ────────────────────────────────────────────────────

@dataclass
class RuntimeEvent:
    """An event emitted by the runtime for observability."""
    tick: int
    agent_id: str
    action_name: str
    bearing_glyph: str
    elapsed_ms: float = 0.0


# ─── Loomy Runtime ────────────────────────────────────────────────────

class Loomy:
    """
    The Loomy runtime — hosts agents, state, and drives execution.

    Think of Loomy as the "loom" that weaves agent actions into the
    shared state fabric. Agents are the warp threads; the runtime is
    the weft that binds them together.

    Parameters:
      state_path: path to the persistent state JSON file
      tick_delay: seconds between rounds (0 = full speed)
      max_ticks: total ticks before halt (None = indefinite)
      verbose: print events to stdout
    """

    def __init__(
        self,
        state_path: str = "~/.whorl/state.json",
        tick_delay: float = 0.05,
        max_ticks: Optional[int] = None,
        verbose: bool = True,
    ):
        self.state = SharedState(state_path)
        self.tick_delay = tick_delay
        self.max_ticks = max_ticks
        self.verbose = verbose

        self._agents: dict[str, Agent] = {}
        self._tick = 0
        self._events: list[RuntimeEvent] = []
        self._running = False
        self._halted = False
        self._started_at: Optional[float] = None

        # Handle Ctrl-C gracefully
        signal.signal(signal.SIGINT, self._on_sigint)

    # ── agent management ──────────────────────────────────────────────

    def spawn(
        self,
        agent_id: str,
        *,
        bearing: Optional[Bearing] = None,
        role: str = "agent",
        tools: Optional[dict] = None,
    ) -> Agent:
        """Spawn a new agent into the runtime."""
        if bearing is None:
            bearing = Bearing.observe(speed=5)

        agent = Agent(
            agent_id=agent_id,
            bearing=bearing,
            role=role,
            state=self.state,
            tools=tools,
        )
        self._agents[agent_id] = agent
        self._log(f"SPAWN {agent_id} [{role}] {bearing.glyph()} spd={bearing.speed}")
        return agent

    def spawn_agent(self, agent: Agent) -> Agent:
        """Register a pre-built agent."""
        self._agents[agent.agent_id] = agent
        self._log(f"REGISTER {agent.agent_id} [{agent.role}] {agent.bearing.glyph()}")
        return agent

    def get(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def agents(self) -> list[Agent]:
        """All registered agents (alive or halted)."""
        return list(self._agents.values())

    def alive_agents(self) -> list[Agent]:
        """Only alive (non-halted) agents."""
        return [a for a in self._agents.values() if a.is_alive]

    def halt_agent(self, agent_id: str, reason: str = "runtime-halt") -> bool:
        """Halt a specific agent."""
        agent = self._agents.get(agent_id)
        if agent:
            agent.halt(reason)
            return True
        return False

    # ── execution ─────────────────────────────────────────────────────

    def run(self, ticks: Optional[int] = None, tick_delay: Optional[float] = None) -> list[RuntimeEvent]:
        """
        Run the runtime for `ticks` rounds (or until all agents halt).

        Each round, every alive agent gets ticks proportional to its speed.
        Speed distribution:
          - Fastest agent (speed=10) gets 1 tick/round
          - Speed=5 gets 1 tick every 2 rounds
          - Speed=1 gets 1 tick every 10 rounds

        Returns the list of events emitted.
        """
        limit = ticks or self.max_ticks
        delay = tick_delay if tick_delay is not None else self.tick_delay

        self._running = True
        self._started_at = time.time()

        try:
            while self._running and not self._halted:
                self._tick += 1
                round_events = self._tick_round()

                if self.verbose and round_events:
                    self._print_round(round_events)

                if limit and self._tick >= limit:
                    self._log(f"HALT: tick limit {limit} reached")
                    break

                if not self.alive_agents():
                    self._log("HALT: all agents have halted")
                    break

                if delay > 0:
                    time.sleep(delay)

        except KeyboardInterrupt:
            self._log("HALT: keyboard interrupt")

        self._running = False
        self._log(f"DONE: {self._tick} ticks in {self.elapsed:.2f}s")
        return self._events

    def _tick_round(self) -> list[RuntimeEvent]:
        """Execute one round: tick eligible agents."""
        events = []

        for agent in self.alive_agents():
            # Speed-based eligibility: speed/10 chance per round
            # (agent with speed=10 ticks every round; speed=1 ticks ~10% of rounds)
            if self._tick % max(1, 11 - agent.speed) == 0:
                t0 = time.time()
                action = agent.tick()
                # Execute the action — agents decide AND act
                agent._execute(action)
                elapsed = (time.time() - t0) * 1000

                event = RuntimeEvent(
                    tick=self._tick,
                    agent_id=agent.agent_id,
                    action_name=action.name,
                    bearing_glyph=agent.bearing.glyph(),
                    elapsed_ms=round(elapsed, 3),
                )
                events.append(event)
                self._events.append(event)

        return events

    # ── observability ─────────────────────────────────────────────────

    @property
    def elapsed(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.time() - self._started_at

    @property
    def tick(self) -> int:
        return self._tick

    def snapshot(self) -> dict:
        """Full runtime snapshot for inspection."""
        return {
            "tick": self._tick,
            "running": self._running,
            "elapsed_seconds": round(self.elapsed, 3),
            "agent_count": len(self._agents),
            "alive_count": len(self.alive_agents()),
            "state_keys": len(self.state),
            "agents": [{
                "agent_id": a.agent_id,
                "role": a.role,
                "alive": a.is_alive,
                "bearing_glyph": a.bearing.glyph(),
                "speed": a.bearing.speed,
                "tick_count": a._tick_count,
            } for a in self._agents.values()],
            "state_snapshot": self.state.snapshot(),
        }

    def report(self) -> str:
        """Human-readable runtime report."""
        snap = self.snapshot()
        lines = [
            f"═══ Loomy Runtime t={snap['tick']} ═══",
            f"  agents: {snap['alive_count']}/{snap['agent_count']} alive",
            f"  state keys: {snap['state_keys']}",
            f"  elapsed: {snap['elapsed_seconds']}s",
            "",
            "  agents:",
        ]
        for a in snap["agents"]:
            state = "◉" if a["alive"] else "◌"
            lines.append(
                f"    {state} {a['agent_id']:<16s} "
                f"[{a['role']:<16s}] "
                f"{a['bearing_glyph']}  "
                f"spd={a['speed']}  "
                f"t={a['tick_count']}"
            )
        if snap["state_keys"]:
            lines.append("")
            lines.append("  state:")
            for k, v in snap["state_snapshot"].items():
                v_str = str(v)
                if len(v_str) > 60:
                    v_str = v_str[:57] + "..."
                lines.append(f"    {k} = {v_str}")

        return "\n".join(lines)

    # ── internals ─────────────────────────────────────────────────────

    def _on_sigint(self, signum, frame):
        self._log("SIGINT received — halting")
        self._halted = True
        self._running = False

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[loomy t={self._tick}] {msg}")

    def _print_round(self, events: list[RuntimeEvent]) -> None:
        for e in events:
            if e.action_name == "noop":
                continue
            print(
                f"  t={e.tick:<5d} {e.agent_id:<16s} "
                f"{e.bearing_glyph}  {e.action_name:<8s} "
                f"({e.elapsed_ms:.1f}ms)"
            )
