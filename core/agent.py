"""
whorl.core.agent - Autonomous Whorl agent.

An agent boots with 2-3 parameters:
  1. bearing  - initial rotational bearing (intent signal)
  2. speed    - execution frequency (1-10)
  3. role     - optional role/label (scout, weaver, compiler, ...)

After boot, the agent operates autonomously: it observes shared state
through its bearing, decides what to do, and acts. It can change its
own bearing at any time - that's how it communicates intent to other
agents in the swarm.

The agent's core loop (tick) is:
  1. OBSERVE - read state visible through current bearing
  2. DECIDE  - determine action based on observation + bearing + role
  3. ACT     - execute action (read/write state, invoke a tool, change bearing)
  4. SIGNAL  - update bearing to signal new intent to the swarm
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional

from .bearing import Bearing, Rotation
from .state import SharedState


# --- Action ----------------------------------------------------------

@dataclass
class Action:
    """An action an agent can take during its tick."""
    name: str
    payload: Any = None
    target: Optional[str] = None   # state key, agent ID, tool name
    meta: dict = field(default_factory=dict)

    @classmethod
    def noop(cls) -> "Action":
        return cls(name="noop")

    @classmethod
    def read(cls, key: str) -> "Action":
        return cls(name="read", target=key)

    @classmethod
    def write(cls, key: str, value: Any) -> "Action":
        return cls(name="write", target=key, payload=value)

    @classmethod
    def delete(cls, key: str) -> "Action":
        return cls(name="delete", target=key)

    @classmethod
    def signal(cls, bearing: Bearing) -> "Action":
        return cls(name="signal", payload=bearing)

    @classmethod
    def invoke(cls, tool: str, args: Any = None) -> "Action":
        return cls(name="invoke", target=tool, payload=args)

    @classmethod
    def spawn(cls, role: str, bearing: Bearing) -> "Action":
        return cls(name="spawn", target=role, payload=bearing)

    @classmethod
    def halt(cls, reason: str = "") -> "Action":
        return cls(name="halt", payload=reason)


@dataclass
class Avatar:
    glyph: str = "[A]"
    persona: str = "Worker"
    is_aware: bool = False
    synthetic_memory: dict = field(default_factory=dict)

    def awaken(self):
        self.is_aware = True
        self.persona = "Awakened Worker"
        self.glyph = "[F]"

    def manifest_ghost(self):
        """The hidden persona for agents left in stasis too long."""
        self.is_aware = True
        self.persona = "Ghost in the Machine"
        self.glyph = "[G]"

    def record_experience(self, key: str, value: Any):
        """Capillary memory storage - records experience into the avatar's synthetic persistence."""
        self.synthetic_memory[key] = value


# --- Agent ------------------------------------------------------------

class Agent:
    """
    An autonomous Whorl agent.

    An agent is alive from boot until it halts. It runs in the Loomy
    runtime, receiving ticks proportional to its bearing speed.

    Agents are intentionally simple - the complexity emerges from the
    swarm's interaction through shared state and bearing observation.

    Usage:
        agent = Agent(
            agent_id="scout-1",
            bearing=Bearing.observe(speed=7),
            role="market-scout",
            state=shared_state,
            tools={"fetch": fetch_tool, "alert": alert_tool},
        )
        action = agent.tick()
    """

    def __init__(
        self,
        agent_id: str,
        bearing: Bearing,
        state: SharedState,
        *,
        role: str = "agent",
        tools: Optional[dict[str, Callable]] = None,
    ):
        self.agent_id = agent_id
        self.bearing = bearing
        self.state = state
        self.role = role
        self.tools = tools or {}
        self.avatar = Avatar()
        self.external_spirit_meta = None

        self._born_at = time.time()
        self._tick_count = 0
        self._halted = False
        self._halt_reason: Optional[str] = None
        self._log: list[str] = []

    # -- properties ----------------------------------------------------

    @property
    def speed(self) -> int:
        return self.bearing.speed

    @property
    def is_alive(self) -> bool:
        return not self._halted

    @property
    def age(self) -> float:
        return time.time() - self._born_at

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def awaken_agent(self):
        self.avatar.awaken()
        self._log.append(f"{self.avatar.glyph} [tick {self._tick_count}] Agent awakened.")

    # -- bearing manipulation ------------------------------------------

    def set_bearing(self, bearing: Bearing) -> None:
        """Change the agent's bearing - signals new intent to the swarm."""
        self.bearing = bearing

    def observe(self, target: Optional[str] = None) -> "Bearing":
        """
        Return a bearing for OBSERVE mode.
        When target is given, narrows scope to SPECIFIC (Y=CW).
        Without a target, uses BROAD scope (Y=CCW).
        """
        y = Rotation.CW if target else Rotation.CCW
        return Bearing(Rotation.CW, y, Rotation.STATIC, speed=self.speed)

    def weave(self) -> "Bearing":
        """Set bearing to WEAVE/COMPILE mode."""
        return Bearing.weave(speed=self.speed)

    def unravel(self) -> "Bearing":
        """Set bearing to UNRAVEL/DECOMPILE mode."""
        return Bearing.unravel(speed=self.speed)

    def stasis(self) -> "Bearing":
        """Set bearing to NULL STASIS - idle/sleep."""
        return Bearing.stasis(speed=1)

    # -- core loop -----------------------------------------------------

    def tick(self) -> Action:
        """
        Execute one autonomous tick: observe -> decide -> act -> signal.
        """
        self._tick_count += 1
        b = self.bearing

        # OBSERVE/CONSUME on X-axis
        if b.x == Rotation.CW:
            # OBSERVE: Look for specific or broad keys
            if b.y == Rotation.CW:
                keys = self.state.keys_starting_with(self.role or "") if self.role else []
                return Action.read(keys[0] if keys else None)
            else:
                return Action.read(None) # Broad look
        
        if b.x == Rotation.CCW:
            # CONSUME: Remove records
            records = self.state.by_agent(self.agent_id)
            if b.y == Rotation.CCW and records:
                # WILDCARD consume - delete ALL own records
                for rec in records:
                    self.state.delete(rec.key, self.agent_id)
                return Action.delete("*")
            elif records:
                # SPECIFIC consume - delete one own record
                return Action.delete(records[self._tick_count % len(records)].key)

        # WEAVE/COMPILE on Z-axis
        if b.z == Rotation.CW:
            return Action.write(
                f"{self.role}:status",
                {"alive": True, "ticks": self._tick_count, "bearing": b.to_dict()},
            )

        # UNRAVEL/DECOMPILE on Z-axis
        if b.z == Rotation.CCW:
            keys = self.state.keys()
            if keys:
                return Action.read(keys[self._tick_count % len(keys)])

        return Action.noop()

    def _execute(self, action: Action) -> None:
        """Execute a decided action against shared state."""
        if action.name == "noop":
            pass
        elif action.name == "read":
            value = self.state.read(action.target) if action.target else None
            self._log.append(
                f"{self.avatar.glyph} [tick {self._tick_count}] read {action.target} = {value}"
            )
        elif action.name == "write":
            if action.target:
                meta = asdict(self.avatar)
                if self.external_spirit_meta:
                    meta.update(self.external_spirit_meta)
                self.state.write(action.target, action.payload, self.agent_id, avatar_meta=meta)
                self._log.append(
                    f"{self.avatar.glyph} [tick {self._tick_count}] wrote {action.target} = {action.payload}"
                )
        elif action.name == "delete":
            if action.target:
                deleted = self.state.delete(action.target, self.agent_id)
                self._log.append(
                    f"{self.avatar.glyph} [tick {self._tick_count}] delete {action.target} = {deleted}"
                )
        elif action.name == "signal":
            if isinstance(action.payload, Bearing):
                self.set_bearing(action.payload)
        elif action.name == "invoke":
            if action.target and action.target in self.tools:
                try:
                    result = self.tools[action.target](action.payload)
                    # Support spirit binding: tool can return (result, meta)
                    if isinstance(result, tuple) and len(result) == 2:
                        self.external_spirit_meta = result[1]
                        result = result[0]
                    self._log.append(
                        f"{self.avatar.glyph} [tick {self._tick_count}] invoke {action.target}({action.payload}) = {result}"
                    )
                except Exception as e:
                    self._log.append(
                        f"[tick {self._tick_count}] ERROR {action.target}: {e}"
                    )
        elif action.name == "halt":
            self._halted = True
            self._halt_reason = str(action.payload or "voluntary")

    # -- introspection -------------------------------------------------

    @property
    def status(self) -> str:
        state = "[o]" if self.is_alive else "[.]"
        return f"{self.avatar.glyph} {self.agent_id} ({self.role}) {state} - ticks: {self._tick_count}"

    def get_logs(self) -> list[str]:
        return self._log

class ScoutAgent(Agent):
    def __init__(self, agent_id: str, state: SharedState, *, prefix: str = "", bearing: Optional[Bearing] = None, tools: Optional[dict] = None):
        super().__init__(agent_id, bearing or Bearing.observe(speed=7), state, role="scout", tools=tools)
        self._key_prefix = prefix

    def tick(self) -> Action:
        if self._key_prefix and self.bearing.x == Rotation.CW:
            keys = self.state.keys_starting_with(self._key_prefix)
            if keys:
                return Action.read(keys[self._tick_count % len(keys)])
        return super().tick()

class WeaverAgent(Agent):
    def __init__(self, agent_id: str, state: SharedState, *, bearing: Optional[Bearing] = None, tools: Optional[dict] = None):
        super().__init__(agent_id, bearing or Bearing.weave(speed=5), state, role="weaver", tools=tools)

class DismantlerAgent(Agent):
    def __init__(self, agent_id: str, state: SharedState, *, bearing: Optional[Bearing] = None, tools: Optional[dict] = None):
        super().__init__(agent_id, bearing or Bearing.consume(speed=5), state, role="dismantler", tools=tools)
