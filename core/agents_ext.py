"""
whorl.core.agents_ext — Specialised Whorl agent types.

CompilerAgent: Uses the decompiler to transpile state entries.
WatchdogAgent: Monitors other agents' health via bearing observation.
HelixAgent : Auto-weaves/unravels state entries with helical crypto.
"""

import time
from typing import Optional

from .bearing import Bearing, Rotation
from .state import SharedState
from .agent import Agent, Action


class CompilerAgent(Agent):
    """
    An agent that transpiles state entries between languages.

    Uses the polyglot decompiler to read state entries written in one
    language, transpile them, and write the result back. This is the
    agent that makes Whorl a true polyglot swarm — code flows between
    languages through shared state.
    """

    def __init__(
        self,
        agent_id: str,
        state: SharedState,
        *,
        from_lang: str = "python",
        to_lang: str = "bash",
    ):
        super().__init__(
            agent_id=agent_id,
            bearing=Bearing.weave(speed=6),
            role=f"compiler:{from_lang}→{to_lang}",
            state=state,
        )
        self.from_lang = from_lang
        self.to_lang = to_lang

    def _decide(self) -> Action:
        # Compilers look for source:* entries and produce target:* entries
        source_keys = self.state.keys_starting_with(f"source:{self.from_lang}:")
        if source_keys:
            key = source_keys[self._tick_count % len(source_keys)]
            return Action.read(key)

        # If nothing to compile, write status
        return Action.write(
            f"compiler:{self.agent_id}:status",
            {
                "from": self.from_lang,
                "to": self.to_lang,
                "ticks": self._tick_count,
                "compiled": 0,
            },
        )

    def _execute(self, action: Action) -> None:
        """Override to add compilation logic on reads."""
        if action.name == "read" and action.target:
            value = self.state.read(action.target)
            self._log.append(
                f"[tick {self._tick_count}] read {action.target} = {str(value)[:60]}"
            )

            # If it looks like code, transpile it
            if isinstance(value, str) and len(value) > 0:
                try:
                    from ..tools.decompiler import get_decompiler
                    dc = get_decompiler()
                    result = dc.transpile(
                        value,
                        from_lang=self.from_lang,
                        to_lang=self.to_lang,
                    )
                    output_key = action.target.replace(
                        f"source:{self.from_lang}:",
                        f"target:{self.to_lang}:",
                    )
                    self.state.write(output_key, result, self.agent_id)
                    self._log.append(
                        f"[tick {self._tick_count}] COMPILED {action.target} → {output_key}"
                    )
                    # Signal we did work
                    self.set_bearing(Bearing.weave(speed=self.speed))
                except Exception as e:
                    self._log.append(
                        f"[tick {self._tick_count}] COMPILE ERROR: {e}"
                    )
        else:
            super()._execute(action)


class WatchdogAgent(Agent):
    """
    An agent that monitors the health of other agents.

    Periodically checks the state for agent status entries and
    raises alerts if agents appear stalled, halted, or absent.

    Uses OBSERVE bearing to scan agent status, and CONSUME bearing
    to clean up stale status entries.
    """

    def __init__(self, agent_id: str, state: SharedState, *, alert_after_ticks: int = 10):
        super().__init__(
            agent_id=agent_id,
            bearing=Bearing.observe_broad(speed=4),
            role="watchdog",
            state=state,
        )
        self.alert_after_ticks = alert_after_ticks
        self._alerts: list[dict] = []

    def _decide(self) -> Action:
        # Watchdogs alternate between observing and cleaning
        if self._tick_count % 3 == 0:
            # Scan for agent status entries every 3 ticks
            status_keys = self.state.keys_starting_with("agent:status:")
            if status_keys:
                key = status_keys[self._tick_count % len(status_keys)]
                return Action.read(key)
            return Action.write(
                f"watchdog:{self.agent_id}:status",
                {"watching": True, "alerts": len(self._alerts), "tick": self._tick_count},
            )
        elif self._tick_count % 3 == 1:
            # Check system health
            all_keys = self.state.keys()
            if all_keys:
                return Action.read(all_keys[self._tick_count % len(all_keys)])
        else:
            # Clean stale entries
            records = self.state.by_agent(self.agent_id)
            if records:
                return Action.delete(records[0].key)

        return Action.noop()

    def _execute(self, action: Action) -> None:
        if action.name == "read" and action.target:
            value = self.state.read(action.target)
            rec = self.state.read_record(action.target)

            # Check for stalled agents
            if rec and rec.created_at:
                age = time.time() - rec.created_at
                if age > self.alert_after_ticks:
                    alert = {
                        "key": action.target,
                        "age": round(age, 2),
                        "tick": self._tick_count,
                        "created_by": rec.created_by,
                    }
                    self._alerts.append(alert)
                    self.state.write(
                        f"watchdog:alert:{self._tick_count}",
                        alert,
                        self.agent_id,
                    )
                    self._log.append(
                        f"[tick {self._tick_count}] ALERT: {action.target} "
                        f"stale ({age:.1f}s old)"
                    )

            self._log.append(
                f"[tick {self._tick_count}] read {action.target} = {str(value)[:40]}"
            )
        else:
            super()._execute(action)

    @property
    def alerts(self) -> list[dict]:
        return list(self._alerts)

    def status(self) -> dict:
        base = super().status()
        base["alerts"] = len(self._alerts)
        base["alert_after_ticks"] = self.alert_after_ticks
        return base


class HelixAgent(Agent):
    """
    An agent that auto-weaves and unravels state through the helical crypto layer.

    Every write is automatically woven into a Knot. Every read is
    auto-unraveled. Without the agent's key, its state entries are
    cryptographically worthless — fulfilling the "stolen data is
    worthless" property.

    Other agents can read the knot metadata (who wove it, bearing,
    depth) via inspect without the key, but not the content.
    """

    def __init__(
        self,
        agent_id: str,
        state: SharedState,
        *,
        weave_key: str,
        role: str = "helix-agent",
        speed: int = 5,
    ):
        super().__init__(
            agent_id=agent_id,
            bearing=Bearing(Rotation.STATIC, Rotation.STATIC, Rotation.CW, speed=speed),
            role=role,
            state=state,
        )
        self.weave_key = weave_key
        # Lazy-import to avoid circular deps at module load
        self._helix = None

    @property
    def helix(self):
        if self._helix is None:
            from ..core.helix import Helix
            self._helix = Helix()
        return self._helix

    def _decide(self) -> Action:
        # Helix agents alternate: weave new encrypted data, then read/unravel
        if self._tick_count % 2 == 0:
            # WEAVE mode — always write a new woven entry
            # (each entry has a unique tick-stamped key, so no overwrite)
            payload = {
                "agent": self.agent_id,
                "tick": self._tick_count,
                "bearing": self.bearing.to_dict(),
            }
            return Action.write(
                f"helix:{self.agent_id}:woven-{self._tick_count}",
                payload,
            )
        else:
            # UNRAVEL mode — read and decrypt existing knots
            helix_keys = self.state.keys_starting_with("helix:")
            if helix_keys:
                key = helix_keys[self._tick_count % len(helix_keys)]
                return Action.read(key)
            # Scan broadly for any knot-like entries
            all_keys = self.state.keys()
            if all_keys:
                return Action.read(all_keys[self._tick_count % len(all_keys)])
            return Action.noop()

    def _execute(self, action: Action) -> None:
        """Override to auto-weave on write and auto-unravel on read."""
        if action.name == "write" and action.target and action.payload is not None:
            # WEAVE: encrypt the payload before writing
            try:
                plaintext = action.payload
                # Use JSON-serialisable payloads
                knot = self.helix.weave(
                    plaintext,
                    key=self.weave_key,
                    weaver_id=self.agent_id,
                    bearing=self.bearing,
                )
                # Write the knot dict (not the raw knot object)
                self.state.write(action.target, knot.to_dict(), self.agent_id)
                self._log.append(
                    f"[tick {self._tick_count}] WOVE {action.target} "
                    f"(depth={knot.depth}, hash={knot.key_hash})"
                )
                self.set_bearing(Bearing.weave(speed=self.speed))
            except Exception as e:
                # Fall back to plain write on error
                self.state.write(action.target, action.payload, self.agent_id)
                self._log.append(
                    f"[tick {self._tick_count}] WEAVE FAILED ({e}), "
                    f"wrote plain {action.target}"
                )

        elif action.name == "read" and action.target:
            raw = self.state.read(action.target)
            # If it looks like a knot, unravel it
            if isinstance(raw, dict) and "payload" in raw and "weaver_id" in raw:
                try:
                    from ..core.helix import Knot
                    knot = Knot.from_dict(raw)
                    # Check if we can verify the key first
                    if self.helix.verify_key(knot, self.weave_key):
                        plaintext = self.helix.unravel(knot, key=self.weave_key)
                        self._log.append(
                            f"[tick {self._tick_count}] UNRAVELED {action.target} "
                            f"→ {str(plaintext)[:60]}"
                        )
                    else:
                        # Not our knot — inspect metadata only
                        info = self.helix.inspect(knot)
                        self._log.append(
                            f"[tick {self._tick_count}] INSPECT {action.target} "
                            f"(woven by {info['weaver_id']}, depth={info['depth']})"
                        )
                except Exception as e:
                    self._log.append(
                        f"[tick {self._tick_count}] UNRAVEL FAILED {action.target}: {e}"
                    )
            else:
                # Plain value — log normally
                self._log.append(
                    f"[tick {self._tick_count}] read {action.target} = {str(raw)[:40]}"
                )
        else:
            super()._execute(action)
