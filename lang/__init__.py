"""
whorl.lang.parser — Whorl language (*.whr) parser.

A .whr file expresses an agent swarm configuration and runtime
instructions in a simple declarative format.

.whr syntax:
    # Comments start with #
    @agent <name> <role>            — declare an agent
      bearing: <x> <y> <z>         — initial bearing (cw/ccw/0)
      speed: <1-10>                 — execution speed
      tools: <t1, t2, ...>         — toolset
    @state <key> = <value>          — initial state entry
    @run <ticks>                    — how many ticks to run
    @weave                           — begin a weave block (data fibers)
    @unravel                         — begin an unravel block

Example test.whr:
    @agent scout-1 market-scout
      bearing: cw 0 0
      speed: 8

    @agent weaver-1 builder
      bearing: 0 cw cw
      speed: 5

    @state market:btc = 42300
    @run 100
"""

from dataclasses import dataclass, field
from ..core.bearing import Bearing, Rotation


# ─── Parse result types ───────────────────────────────────────────────

@dataclass
class AgentDef:
    """Parsed agent definition from a .whr file."""
    agent_id: str
    role: str
    bearing: Bearing = field(default_factory=Bearing.stasis)
    tools: list[str] = field(default_factory=list)


@dataclass
class WhorlProgram:
    """A parsed Whorl program."""
    agents: list[AgentDef] = field(default_factory=list)
    state: dict[str, object] = field(default_factory=dict)
    run_ticks: int | None = None
    tick_delay: float = 0.05
    verbose: bool = True
    weave_blocks: list[str] = field(default_factory=list)
    unravel_blocks: list[str] = field(default_factory=list)


# ─── Parser ────────────────────────────────────────────────────────────

def _parse_rotation(token: str) -> Rotation:
    """Parse a rotation token: cw, ccw, or 0."""
    t = token.strip().lower()
    if t in ("cw", "1", "+1"):
        return Rotation.CW
    elif t in ("ccw", "-1"):
        return Rotation.CCW
    return Rotation.STATIC


def parse_whorl(source: str) -> WhorlProgram:
    """Parse a .whr source string into a WhorlProgram."""
    program = WhorlProgram()
    lines = source.strip().split("\n")

    current_agent: AgentDef | None = None
    current_block: list[str] | None = None
    block_kind: str | None = None

    def flush_agent():
        nonlocal current_agent
        if current_agent:
            program.agents.append(current_agent)
            current_agent = None

    def flush_block():
        nonlocal current_block, block_kind
        if current_block and block_kind:
            content = "\n".join(current_block)
            if block_kind == "weave":
                program.weave_blocks.append(content)
            elif block_kind == "unravel":
                program.unravel_blocks.append(content)
            current_block = None
            block_kind = None

    for line in lines:
        stripped = line.strip()

        # Skip comments and blanks
        if not stripped or stripped.startswith("#"):
            continue

        # End current blocks when encountering non-indented content
        if not line.startswith((" ", "\t")) and current_block is not None:
            flush_block()

        # @agent directive
        if stripped.startswith("@agent"):
            flush_agent()
            parts = stripped.split()
            if len(parts) >= 3:
                current_agent = AgentDef(agent_id=parts[1], role=parts[2])
            elif len(parts) == 2:
                current_agent = AgentDef(agent_id=parts[1], role="agent")

        # @state directive
        elif stripped.startswith("@state"):
            parts = stripped[7:].strip().split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                # Try to parse as number
                try:
                    if "." in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    value = value.strip('"').strip("'")
                program.state[key] = value

        # @run directive
        elif stripped.startswith("@run"):
            parts = stripped.split()
            if len(parts) >= 2:
                try:
                    program.run_ticks = int(parts[1])
                except ValueError:
                    pass

        # @delay directive
        elif stripped.startswith("@delay"):
            parts = stripped.split()
            if len(parts) >= 2:
                try:
                    program.tick_delay = float(parts[1])
                except ValueError:
                    pass

        # @verbose directive
        elif stripped.startswith("@verbose"):
            parts = stripped.split()
            if len(parts) >= 2:
                program.verbose = parts[1].lower() in ("on", "true", "1")

        # @weave / @unravel blocks
        elif stripped.startswith("@weave"):
            flush_block()
            block_kind = "weave"
            current_block = []
        elif stripped.startswith("@unravel"):
            flush_block()
            block_kind = "unravel"
            current_block = []

        # Agent attribute lines (indented)
        elif current_agent is not None and line.startswith((" ", "\t")):
            attr = stripped
            if ":" in attr:
                key, val = attr.split(":", 1)
                key = key.strip().lower()
                val = val.strip()

                if key == "bearing":
                    parts = val.split()
                    if len(parts) >= 3:
                        current_agent.bearing = Bearing(
                            x=_parse_rotation(parts[0]),
                            y=_parse_rotation(parts[1]),
                            z=_parse_rotation(parts[2]),
                        )
                elif key == "speed":
                    try:
                        current_agent.bearing = current_agent.bearing.with_speed(int(val))
                    except ValueError:
                        pass
                elif key == "tools":
                    current_agent.tools = [t.strip() for t in val.split(",") if t.strip()]

        # Content lines for weave/unravel blocks
        elif current_block is not None:
            current_block.append(stripped)

    # Flush remaining
    flush_agent()
    flush_block()

    return program


def load_whorl(filepath: str) -> WhorlProgram:
    """Load and parse a .whr file."""
    with open(filepath, "r") as f:
        return parse_whorl(f.read())
