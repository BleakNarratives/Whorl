"""
Whorl Tools — Tool, Toolkit, and Toolchain abstractions.

A Tool is an atomic capability (one thing an agent can do).
A Toolkit is a collection of related tools.
A Toolchain is a pipeline of tools that transform data across languages.
"""

from ..core.bearing import Bearing


class Tool:
    """An atomic capability an agent can invoke."""

    def __init__(self, name: str, fn, description: str = ""):
        self.name = name
        self._fn = fn
        self.description = description

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)

    def __repr__(self):
        return f"<Tool {self.name}>"


class Toolkit:
    """A named collection of related Tools."""

    def __init__(self, name: str, tools: list[Tool], description: str = ""):
        self.name = name
        self.tools: dict[str, Tool] = {t.name: t for t in tools}
        self.description = description

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def invoke(self, name: str, *args, **kwargs):
        tool = self.tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in toolkit '{self.name}'")
        return tool(*args, **kwargs)

    def as_dict(self) -> dict:
        """Return tools as a plain dict for Agent tools param."""
        return {name: tool._fn for name, tool in self.tools.items()}

    def list(self) -> list[str]:
        return sorted(self.tools.keys())

    def __repr__(self):
        return f"<Toolkit {self.name} ({len(self.tools)} tools)>"


class Toolchain:
    """
    A pipeline of tools that transform data step-by-step.

    Toolchains are the Whorl way to compose operations across languages.
    A polyglot toolchain might: parse Python → IR → emit Bash, for example.
    """

    def __init__(self, name: str, steps: list[Tool], description: str = ""):
        self.name = name
        self.steps = steps
        self.description = description

    def run(self, input_data=None):
        """Run the toolchain, feeding output of each step to the next."""
        data = input_data
        for step in self.steps:
            if data is not None:
                data = step(data)
            else:
                data = step()
        return data

    def __repr__(self):
        return f"<Toolchain {self.name} ({len(self.steps)} steps)>"


# ─── Built-in tools ───────────────────────────────────────────────────

def _tool_read_file(path: str) -> str:
    """Read a file from disk."""
    with open(path, "r") as f:
        return f.read()


def _tool_write_file(path: str, content: str) -> int:
    """Write content to a file. Returns byte count."""
    with open(path, "w") as f:
        return f.write(content)


def _tool_run_shell(cmd: str) -> str:
    """Run a shell command and return stdout."""
    import subprocess
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout or result.stderr


def _tool_search(pattern: str, path: str = ".") -> str:
    """Search for a pattern in files (ripgrep wrapper)."""
    import subprocess
    try:
        result = subprocess.run(
            ["rg", "--no-heading", "-n", pattern, path],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout or "(no matches)"
    except FileNotFoundError:
        return "(ripgrep not installed — install with: sudo apt install ripgrep)"


def _tool_curl(url: str) -> str:
    """Fetch a URL via curl."""
    import subprocess
    result = subprocess.run(
        ["curl", "-sL", "--max-time", "10", url],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr


def builtin_toolkit() -> Toolkit:
    """Return the standard built-in Whorl toolkit."""
    return Toolkit(
        name="whorl:builtins",
        tools=[
            Tool("read_file", _tool_read_file, "Read a file from disk"),
            Tool("write_file", _tool_write_file, "Write content to a file"),
            Tool("shell", _tool_run_shell, "Run a shell command"),
            Tool("search", _tool_search, "Search for a pattern in files"),
            Tool("curl", _tool_curl, "Fetch a URL"),
        ],
        description="Standard Whorl built-in tools",
    )
