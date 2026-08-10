"""
whorl.runtimes — Language-specific runtime adapters.

Rather than forcing agents into one language, Whorl provides
adapters that let agents execute code in their native language
while still participating in the shared state swarm.

Each adapter:
  1. Registers a runtime (Python subprocess, bash subshell, etc.)
  2. Provides tools native to that language
  3. Translates state access to language-idiomatic forms
"""


class RuntimeAdapter:
    """Base class for language runtime adapters."""

    language: str = "unknown"

    def execute(self, code: str) -> str:
        """Execute code in this runtime and return output."""
        raise NotImplementedError

    def state_read(self, key: str) -> str:
        """Read from shared state (language-idiomatic)."""
        raise NotImplementedError

    def state_write(self, key: str, value: str) -> str:
        """Write to shared state (language-idiomatic)."""
        raise NotImplementedError


class BashRuntime(RuntimeAdapter):
    """Execute Bash code in a subshell."""

    language = "bash"

    def execute(self, code: str) -> str:
        import subprocess
        result = subprocess.run(
            ["bash", "-c", code],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout or result.stderr

    def state_read(self, key: str) -> str:
        """Generate bash code to read state via whorl CLI."""
        return f'python3 -c "from whorl.core.state import SharedState; s=SharedState(); print(s.read(\'{key}\'))"'

    def state_write(self, key: str, value: str) -> str:
        """Generate bash code to write state via whorl CLI."""
        return f'python3 -c "from whorl.core.state import SharedState; s=SharedState(); s.write(\'{key}\', \'{value}\', \'bash-agent\')"'


class PythonRuntime(RuntimeAdapter):
    """Execute Python code in a subprocess."""

    language = "python"

    def execute(self, code: str) -> str:
        import subprocess
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout or result.stderr

    def state_read(self, key: str) -> str:
        return f'__import__("whorl.core.state").SharedState().read("{key}")'

    def state_write(self, key: str, value: str) -> str:
        return f'__import__("whorl.core.state").SharedState().write("{key}", {value}, "python-agent")'


class NodeRuntime(RuntimeAdapter):
    """Execute JavaScript code via Node.js."""

    language = "javascript"

    def execute(self, code: str) -> str:
        import subprocess
        try:
            result = subprocess.run(
                ["node", "-e", code],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout or result.stderr
        except FileNotFoundError:
            return "(Node.js not installed — install with: sudo apt install nodejs)"

    def state_read(self, key: str) -> str:
        """Generate JS code to read state via Python bridge."""
        return (
            f'const {{ execSync }} = require("child_process"); '
            f'execSync("python3 -c \\"from whorl.core.state import SharedState; '
            f'print(SharedState().read(\'{key}\'))\\"").toString().trim()'
        )

    def state_write(self, key: str, value: str) -> str:
        """Generate JS code to write state via Python bridge."""
        return (
            f'const {{ execSync }} = require("child_process"); '
            f'execSync("python3 -c \\"from whorl.core.state import SharedState; '
            f'SharedState().write(\'{key}\', \'{value}\', \'node-agent\')\\"")'
        )


class GoRuntime(RuntimeAdapter):
    """Execute Go code snippets via `go run`."""

    language = "go"

    def execute(self, code: str) -> str:
        import subprocess, tempfile, os
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".go", delete=False, dir="/tmp"
            ) as f:
                f.write(code)
                tmp = f.name
            result = subprocess.run(
                ["go", "run", tmp],
                capture_output=True, text=True, timeout=30
            )
            os.unlink(tmp)
            return result.stdout or result.stderr
        except FileNotFoundError:
            return "(Go not installed — install with: sudo apt install golang)"

    def state_read(self, key: str) -> str:
        return (
            f'package main; import ("fmt";"os/exec"); func main() {{ '
            f'out,_:=exec.Command("python3","-c",'
            f'"from whorl.core.state import SharedState;print(SharedState().read(\'{key}\'))").Output(); '
            f'fmt.Print(string(out)) }}'
        )

    def state_write(self, key: str, value: str) -> str:
        return (
            f'package main; import "os/exec"; func main() {{ '
            f'exec.Command("python3","-c",'
            f'"from whorl.core.state import SharedState;SharedState().write(\'{key}\',\'{value}\',\'go-agent\')").Run() }}'
        )


# Registry of all available runtimes
RUNTIMES = {
    "python": PythonRuntime,
    "bash": BashRuntime,
    "javascript": NodeRuntime,
    "node": NodeRuntime,
    "js": NodeRuntime,
    "go": GoRuntime,
}


def get_runtime(language: str) -> RuntimeAdapter | None:
    """Get a runtime adapter by language name."""
    cls = RUNTIMES.get(language.lower())
    return cls() if cls else None


def available_runtimes() -> list[str]:
    """List all available language runtimes."""
    return sorted(RUNTIMES.keys())
