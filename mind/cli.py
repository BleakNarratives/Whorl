"""
whorl.mind.cli
──────────────
Command-line interface for the Mind model scaffolding.

Usage:
  python -m whorl.mind.cli list              # Show all models
  python -m whorl.mind.cli ask CODE "prompt"  # Route to code model
  python -m whorl.mind.cli chat code          # Interactive chat
  python -m whorl.mind.cli which              # Currently loaded model
  python -m whorl.mind.cli resolve wild       # Resolve alias → tag
  python -m whorl.mind.cli health             # Backend health check
"""

from __future__ import annotations
import sys
import argparse
from dataclasses import asdict
from typing import Optional

from .models import ModelRole, BackendKind, ModelSpec
from .registry import ModelRegistry


def _color(code: str, text: str) -> str:
    """Simple ANSI color wrapper."""
    colors = {
        "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
        "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
        "blue": "\033[34m", "cyan": "\033[36m", "magenta": "\033[35m",
    }
    if not sys.stdout.isatty():
        return text
    c = colors.get(code, "")
    r = colors["reset"]
    return f"{c}{text}{r}"


def cmd_list(registry: ModelRegistry) -> None:
    """Pretty-print all discovered models."""
    if registry.model_count == 0:
        print(_color("dim", "No models discovered. Is ollama running?"))
        return

    snap = registry.snapshot()
    print()
    print(_color("cyan", f"  ╭── mind registry ── {snap.total_models} models ─────────────╮"))
    print(_color("cyan", f"  │  backends: {', '.join(snap.backends)}"))

    # Group by role
    by_role = registry.list_roles()
    role_order = [
        ModelRole.CODE, ModelRole.REASONING, ModelRole.CREATIVE,
        ModelRole.GENERAL, ModelRole.TOOL_USE, ModelRole.VISION,
    ]
    for role in role_order:
        if role not in by_role:
            continue
        models = by_role[role]
        role_label = _color("yellow", f"[{role.value}]")
        for m in models:
            alias_str = ", ".join(m.aliases) if m.aliases else "—"
            print(
                f"  │  {role_label:<20s} "
                f"{_color('green', m.name):<38s} "
                f"{m.size_gb:.1f}GB  "
                f"{_color('dim', alias_str)}"
            )

    print(_color("cyan", "  ╰──────────────────────────────────────────────────╯"))
    print()


def cmd_resolve(registry: ModelRegistry, identifier: str) -> None:
    """Resolve an alias to a full model spec."""
    spec = registry.resolve(identifier)
    if spec is None:
        print(_color("red", f"  ✖  '{identifier}' not found"))
        return
    print(_color("green", f"  ✓  {spec.name}"))
    print(f"      backend:  {spec.backend.value}")
    print(f"      size:     {spec.size_gb:.1f} GB")
    print(f"      roles:    {[r.value for r in spec.roles]}")
    print(f"      context:  {spec.context}")
    print(f"      aliases:  {spec.aliases}")


def cmd_ask(
    registry: ModelRegistry,
    prompt: str,
    *,
    model: Optional[str] = None,
    role: Optional[str] = None,
    system: Optional[str] = None,
) -> None:
    """One-shot: ask a model a question."""
    model_role = None
    if role:
        try:
            model_role = ModelRole(role)
        except ValueError:
            print(_color("red", f"  ✖  Unknown role: {role}"))
            print(f"      Valid: {[r.value for r in ModelRole]}")
            return

    spec = None
    if model:
        spec = registry.resolve(model)
    elif model_role:
        spec = registry.resolve_role(model_role)

    if spec is None:
        print(_color("red", "  ✖  No matching model found"))
        return

    print(_color("magenta", f"  ╭── {spec.name} ──"))
    response = registry.ask(
        prompt, model=model, role=model_role, system=system,
    )
    print(f"  │  {response.text}")
    print(_color("magenta", f"  ╰── {response.elapsed_ms:.0f}ms"))
    print()


def cmd_chat(registry: ModelRegistry, identifier: str) -> None:
    """Interactive chat with a specific model."""
    spec = registry.resolve(identifier)
    if spec is None:
        print(_color("red", f"  ✖  '{identifier}' not found"))
        return

    # Use resolved tag for all subsequent calls — avoid re-resolution
    model_tag = spec.tag

    print(_color("magenta", f"\n  ╭── {spec.name} [{spec.backend.value}] ──"))
    print(_color("dim", "  │  type /exit to quit, /model to switch"))
    print(_color("magenta", "  ╰──\n"))

    while True:
        try:
            prompt = input(_color("green", f"  {identifier} › "))
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if prompt.strip() in ("/exit", "/quit", "/q"):
            break
        if prompt.strip() == "/model":
            cmd_list(registry)
            continue

        if not prompt.strip():
            continue

        response = registry.ask(prompt, model=model_tag)
        print(f"\n  {response.text}\n")
        print(_color("dim", f"  ── {response.elapsed_ms:.0f}ms ──\n"))


def cmd_which(registry: ModelRegistry) -> None:
    """Show currently loaded model via ollama backend."""
    ollama = registry.get_backend(BackendKind.OLLAMA)
    if ollama is None or not ollama.health():
        print(_color("dim", "  Ollama backend not available"))
        return

    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=5,
        )
        output = result.stdout.strip()
        if not output or "NAME" not in output:
            print(_color("dim", "  No model loaded — RAM is free"))
        else:
            print(output)
    except FileNotFoundError:
        print(_color("dim", "  ollama CLI not found"))
    except Exception:
        print(_color("dim", "  Could not check ollama status"))


def cmd_health(registry: ModelRegistry) -> None:
    """Check all backend health."""
    from .backends import OllamaBackend, HuggingFaceBackend

    print()
    backends = [
        ("ollama", OllamaBackend()),
        ("huggingface", HuggingFaceBackend()),
    ]
    for name, backend in backends:
        status = _color("green", "✓ healthy") if backend.health() else _color("red", "✗ offline")
        models = backend.list_models()
        model_count = _color("dim", f"({len(models)} models)")
        print(f"  {status}  {name:<20s} {model_count}")
    print()


def cmd_pull(registry: ModelRegistry, model_tag: str) -> None:
    """Pull a model through its backend."""
    # Determine which backend to use — try ollama first
    ollama = registry.get_backend(BackendKind.OLLAMA)
    if ollama is not None and ollama.health():
        # Create a minimal spec for the pull
        temp_spec = ModelSpec(
            name=model_tag, backend=BackendKind.OLLAMA, tag=model_tag,
            size_gb=0.0, roles=[ModelRole.GENERAL],
        )
        print(_color("yellow", f"  Pulling {model_tag} via ollama..."))
        if ollama.pull(temp_spec):
            print(_color("green", f"  ✓ {model_tag} pulled successfully"))
            registry.discover()  # refresh
        else:
            print(_color("red", f"  ✖ Pull failed for {model_tag}"))
        return

    print(_color("red", f"  ✖ No healthy backend available to pull {model_tag}"))
    print(_color("dim", "  Is ollama running? Try: ollama serve &"))


def cmd_stop(registry: ModelRegistry) -> None:
    """Stop/unload models to free RAM via ollama backend."""
    ollama = registry.get_backend(BackendKind.OLLAMA)
    if ollama is None or not ollama.health():
        print(_color("red", "  Ollama backend not available"))
        return

    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 1:
            print(_color("dim", "  Nothing to stop"))
            return
        for line in lines[1:]:
            model_name = line.split()[0] if line.strip() else ""
            if model_name:
                subprocess.run(["ollama", "stop", model_name], capture_output=True)
                print(_color("green", f"  ✓ unloaded {model_name}"))
        print(_color("green", "  RAM freed"))
    except FileNotFoundError:
        print(_color("red", "  ollama CLI not found"))
    except Exception as e:
        print(_color("red", f"  Error: {e}"))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="mind",
        description="Whorl Mind — modular model scaffolding",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # list
    sub.add_parser("list", aliases=["ls"], help="List all models")

    # resolve
    p_resolve = sub.add_parser("resolve", help="Resolve an alias to a model spec")
    p_resolve.add_argument("identifier", help="Alias, name, or tag")

    # ask (one-shot)
    p_ask = sub.add_parser("ask", help="One-shot question to a model")
    p_ask.add_argument("prompt", help="The prompt to send")
    p_ask.add_argument("--model", "-m", help="Specific model (alias or tag)")
    p_ask.add_argument("--role", "-r", help="Role filter (code, reasoning, creative)")
    p_ask.add_argument("--system", "-s", help="System prompt override")

    # chat
    p_chat = sub.add_parser("chat", help="Interactive chat with a model")
    p_chat.add_argument("model", help="Model alias or tag")

    # which
    sub.add_parser("which", help="Show currently loaded model")

    # health
    sub.add_parser("health", help="Check backend health")

    # stop
    sub.add_parser("stop", help="Unload models from RAM")

    # pull
    p_pull = sub.add_parser("pull", help="Pull/install a model")
    p_pull.add_argument("model", help="Model tag to pull (e.g. granite3.2:2b)")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    registry = ModelRegistry()

    if args.command in ("list", "ls"):
        cmd_list(registry)
    elif args.command == "resolve":
        cmd_resolve(registry, args.identifier)
    elif args.command == "ask":
        cmd_ask(registry, args.prompt, model=args.model, role=args.role, system=args.system)
    elif args.command == "chat":
        cmd_chat(registry, args.model)
    elif args.command == "which":
        cmd_which(registry)
    elif args.command == "health":
        cmd_health(registry)
    elif args.command == "stop":
        cmd_stop(registry)
    elif args.command == "pull":
        cmd_pull(registry, args.model)


if __name__ == "__main__":
    main()
