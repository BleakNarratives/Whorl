"""
whorl.tools.decompiler — Polyglot decompiler/recompiler.

The decompiler translates source code from one language to another
through a shared intermediate representation (IR).

Implemented adapters:
  - Python  (parse + emit)
  - Bash    (parse + emit)
  - JavaScript (parse + emit)

Planned (not yet implemented — will raise ValueError if used):
  Go, Rust, C, Java, Ruby, Perl, Lua

The IR is intentionally simple: a list of statement dicts with
type, target, and args. The helical aspect comes from how agents
with WEAVE/UNRAVEL bearings interact with the decompiler pipeline.
"""

from dataclasses import dataclass, field
from typing import Any


# ─── Intermediate Representation ──────────────────────────────────────

@dataclass
class IRNode:
    """A single node in the intermediate representation."""
    kind: str               # assign, call, if, for, return, import, ...
    target: str | None = None
    value: Any = None
    args: list[Any] = field(default_factory=list)
    body: list["IRNode"] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "target": self.target,
            "value": self.value,
            "args": self.args,
            "body": [b.to_dict() for b in self.body],
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IRNode":
        return cls(
            kind=d["kind"],
            target=d.get("target"),
            value=d.get("value"),
            args=d.get("args", []),
            body=[cls.from_dict(b) for b in d.get("body", [])],
            meta=d.get("meta", {}),
        )


# ─── Language Adapter Protocol ────────────────────────────────────────

class LanguageAdapter:
    """Protocol for a language-specific parser/emitter."""

    name: str = "unknown"
    extensions: list[str] = []

    def parse(self, source: str) -> list[IRNode]:
        """Parse source code into IR nodes."""
        raise NotImplementedError

    def emit(self, nodes: list[IRNode]) -> str:
        """Emit target language from IR nodes."""
        raise NotImplementedError

class ModelAdapter(LanguageAdapter):
    """Protocol for a model-specific parser/emitter."""
    
    def parse_model(self, model_path: str) -> list[IRNode]:
        """Parse model weights into IR nodes."""
        raise NotImplementedError
    
    def emit_model(self, nodes: list[IRNode], output_path: str, precision_map: dict[str, str]) -> None:
        """Emit model from IR nodes with tiered precision."""
        raise NotImplementedError


# ─── Python Adapter ───────────────────────────────────────────────────

class PythonAdapter(LanguageAdapter):
    name = "python"
    extensions = [".py", ".pyw"]

    def parse(self, source: str) -> list[IRNode]:
        """Simple Python → IR parser (regex-based for now; AST when available)."""
        import re
        nodes = []

        for line in source.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # import x
            if m := re.match(r'^import\s+(\S+)', line):
                nodes.append(IRNode(kind="import", target=m.group(1)))
            # from x import y
            elif m := re.match(r'^from\s+(\S+)\s+import\s+(.+)$', line):
                nodes.append(IRNode(kind="import", target=m.group(1),
                                    args=[a.strip() for a in m.group(2).split(",")]))
            # x = value
            elif m := re.match(r'^(\S+)\s*=\s*(.+)$', line):
                nodes.append(IRNode(kind="assign", target=m.group(1), value=m.group(2)))
            # print(x)
            elif m := re.match(r'^print\((.+)\)$', line):
                nodes.append(IRNode(kind="print", args=[m.group(1)]))
            # function call: name(args)
            elif m := re.match(r'^(\w+)\((.+)\)$', line):
                nodes.append(IRNode(kind="call", target=m.group(1),
                                    args=[a.strip() for a in m.group(2).split(",") if a.strip()]))
            # if x:
            elif m := re.match(r'^if\s+(.+):$', line):
                nodes.append(IRNode(kind="if", target=m.group(1)))
            else:
                nodes.append(IRNode(kind="expr", value=line))

        return nodes

    def emit(self, nodes: list[IRNode]) -> str:
        """IR → Python emission."""
        lines = []
        indent = 0
        for node in nodes:
            prefix = "    " * indent
            if node.kind == "import":
                if node.args:
                    lines.append(f"from {node.target} import {', '.join(node.args)}")
                else:
                    lines.append(f"import {node.target}")
            elif node.kind == "assign":
                lines.append(f"{prefix}{node.target} = {node.value}")
            elif node.kind == "print":
                lines.append(f"{prefix}print({', '.join(node.args)})")
            elif node.kind == "call":
                args = ", ".join(node.args)
                lines.append(f"{prefix}{node.target}({args})")
            elif node.kind == "if":
                lines.append(f"{prefix}if {node.target}:")
            elif node.kind == "expr":
                lines.append(f"{prefix}{node.value}")
            elif node.kind == "return":
                lines.append(f"{prefix}return {node.value or ''}")
            else:
                lines.append(f"{prefix}# [{node.kind}] {node.target or ''} = {node.value or ''}")
        return "\n".join(lines)


# ─── Bash Adapter ─────────────────────────────────────────────────────

class BashAdapter(LanguageAdapter):
    name = "bash"
    extensions = [".sh", ".bash"]

    def parse(self, source: str) -> list[IRNode]:
        """Simple Bash → IR parser."""
        import re
        nodes = []

        for line in source.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("#!/"):
                nodes.append(IRNode(kind="shebang", value=line))
            elif m := re.match(r'^(\w+)=(.+)$', line):
                nodes.append(IRNode(kind="assign", target=m.group(1), value=m.group(2)))
            elif m := re.match(r'^echo\s+(.+)$', line):
                nodes.append(IRNode(kind="print", args=[m.group(1)]))
            elif m := re.match(r'^(\w+)\s+(.+)$', line):
                nodes.append(IRNode(kind="call", target=m.group(1), args=[m.group(2)]))
            elif m := re.match(r'^if\s+\[\[?\s*(.+?)\s*\]\]?;\s*then$', line):
                nodes.append(IRNode(kind="if", target=m.group(1)))
            else:
                nodes.append(IRNode(kind="expr", value=line))

        return nodes

    def emit(self, nodes: list[IRNode]) -> str:
        """IR → Bash emission."""
        lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
        for node in nodes:
            if node.kind == "shebang":
                lines[0] = node.value
            elif node.kind == "assign":
                lines.append(f'{node.target}={node.value}')
            elif node.kind == "print":
                lines.append(f'echo {", ".join(node.args)}')
            elif node.kind == "call":
                lines.append(f'{node.target} {" ".join(node.args)}')
            elif node.kind == "if":
                lines.append(f'if [[ {node.target} ]]; then')
            elif node.kind == "import":
                lines.append(f'# source {node.target}  # (bash equivalent of import)')
            elif node.kind == "expr":
                lines.append(f'{node.value}')
            else:
                lines.append(f'# [{node.kind}] {node.target or ""} = {node.value or ""}')
        return "\n".join(lines)


# ─── JavaScript Adapter ────────────────────────────────────────────────

class JavaScriptAdapter(LanguageAdapter):
    name = "javascript"
    extensions = [".js", ".mjs", ".cjs"]

    def parse(self, source: str) -> list[IRNode]:
        """Simple JavaScript → IR parser."""
        import re
        nodes = []

        for line in source.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue

            # const/let/var x = value
            if m := re.match(r'^(?:const|let|var)\s+(\S+)\s*=\s*(.+?);?\s*$', line):
                nodes.append(IRNode(kind="assign", target=m.group(1), value=m.group(2)))
            # x = value (bare assignment)
            elif m := re.match(r'^(\S+)\s*=\s*(.+?);?\s*$', line):
                nodes.append(IRNode(kind="assign", target=m.group(1), value=m.group(2)))
            # console.log(x)
            elif m := re.match(r'^console\.log\((.+)\);?\s*$', line):
                nodes.append(IRNode(kind="print", args=[m.group(1)]))
            # function name(args) {
            elif m := re.match(r'^function\s+(\w+)\(([^)]*)\)\s*\{?\s*$', line):
                nodes.append(IRNode(kind="function", target=m.group(1),
                                    args=[a.strip() for a in m.group(2).split(",") if a.strip()]))
            # import { x } from 'y'
            elif m := re.match(r"^import\s+\{?\s*(.+?)\s*\}?\s*from\s+['\"](.+?)['\"]", line):
                nodes.append(IRNode(kind="import", target=m.group(2),
                                    args=[a.strip() for a in m.group(1).split(",")]))
            # function call: name(args)
            elif m := re.match(r'^(\w+)\((.+)\);?\s*$', line):
                nodes.append(IRNode(kind="call", target=m.group(1),
                                    args=[a.strip() for a in m.group(2).split(",") if a.strip()]))
            # if (condition) {
            elif m := re.match(r'^if\s*\((.+)\)\s*\{?\s*$', line):
                nodes.append(IRNode(kind="if", target=m.group(1)))
            else:
                nodes.append(IRNode(kind="expr", value=line))

        return nodes

    def emit(self, nodes: list[IRNode]) -> str:
        """IR → JavaScript emission."""
        lines = []
        indent = 0
        for node in nodes:
            prefix = "  " * indent
            if node.kind == "import":
                args = ", ".join(node.args) if node.args else ""
                lines.append(f"import {{ {args} }} from '{node.target}';")
            elif node.kind == "assign":
                lines.append(f"{prefix}const {node.target} = {node.value};")
            elif node.kind == "print":
                lines.append(f"{prefix}console.log({", ".join(node.args)});")
            elif node.kind == "call":
                args = ", ".join(node.args)
                lines.append(f"{prefix}{node.target}({args});")
            elif node.kind == "function":
                args = ", ".join(node.args)
                lines.append(f"{prefix}function {node.target}({args}) {{")
            elif node.kind == "if":
                lines.append(f"{prefix}if ({node.target}) {{")
            elif node.kind == "expr":
                lines.append(f"{prefix}{node.value}")
            else:
                lines.append(f"{prefix}// [{node.kind}] {node.target or ''} = {node.value or ''}")
        return "\n".join(lines)


# ─── Decompiler ───────────────────────────────────────────────────────

class Decompiler:
    """
    Polyglot decompiler/recompiler.

    Routes source code through the IR to any target language.

    Usage:
        dc = Decompiler()
        dc.register(PythonAdapter())
        dc.register(BashAdapter())

        bash_code = dc.transpile("print('hello')", from_lang="python", to_lang="bash")
        # → 'echo hello'
    """

    def __init__(self):
        self._adapters: dict[str, LanguageAdapter] = {}

    def register(self, adapter: LanguageAdapter) -> None:
        self._adapters[adapter.name] = adapter
        for ext in adapter.extensions:
            self._adapters[ext] = adapter

    def get(self, name: str) -> LanguageAdapter | None:
        return self._adapters.get(name)

    def languages(self) -> list[str]:
        return sorted(set(a.name for a in self._adapters.values()))

    def _resolve(self, language: str) -> LanguageAdapter | None:
        """Resolve a language token to an adapter.

        Accepts the canonical name ("javascript"), an extension with or
        without the dot ("js" / ".js"), or any registered alias.
        """
        token = language.strip().lstrip(".").lower()
        adapter = self._adapters.get(token)
        if adapter is not None:
            return adapter
        dotted = f".{token}"
        return self._adapters.get(dotted)

    def parse(self, source: str, language: str) -> list[IRNode]:
        """Parse source → IR."""
        adapter = self._resolve(language)
        if adapter is None:
            raise ValueError(f"Unknown language: {language}")
        return adapter.parse(source)

    def emit(self, nodes: list[IRNode], language: str) -> str:
        """IR → target language."""
        adapter = self._resolve(language)
        if adapter is None:
            raise ValueError(f"Unknown language: {language}")
        return adapter.emit(nodes)

    def transpile(self, source: str, *, from_lang: str, to_lang: str) -> str:
        """Transpile source from one language to another."""
        nodes = self.parse(source, from_lang)
        return self.emit(nodes, to_lang)


# ─── Singleton ────────────────────────────────────────────────────────

_decompiler: Decompiler | None = None


def get_decompiler() -> Decompiler:
    global _decompiler
    if _decompiler is None:
        _decompiler = Decompiler()
        _decompiler.register(PythonAdapter())
        _decompiler.register(BashAdapter())
        _decompiler.register(JavaScriptAdapter())
    return _decompiler

# ─── Tier Profiler ──────────────────────────────────────────────────

class TierProfiler:
    """Automated generation of precision maps for tiered quantization.
    
    NOTE: This is scaffolding. It defines the *intent* for tiered quantization.
    Actual quality improvement requires requantization from unquantized 
    (FP16/FP32) source checkpoints, not re-casting already quantized (GGUF) weights.
    """
    
    @staticmethod
    def generate_map(nodes: list[IRNode]) -> dict[str, str]:
        """Maps tensor names to precision based on architecture."""
        precision_map = {}
        for node in nodes:
            if node.kind == "tensor":
                name = node.target
                
                # Tiered Strategy:
                # 1. Attention layers (k, q, v, output) -> Higher Precision (float16)
                # 2. FFN layers -> Lower Precision (simulated target for quantization)
                
                if "attn" in name:
                    precision_map[name] = "float16"
                elif "ffn" in name:
                    # Tier 2: Aggressive quantization (int8)
                    precision_map[name] = "int8"
                else:
                    precision_map[name] = "float32" # Keep norm/embeds high
        return precision_map
import struct
import json

# ─── Emitter Engine ──────────────────────────────────────────────────

class SGUFEmitter:
    """Serializes IRNodes into the S-GGUF optimized format."""

    MAGIC = 0x46554753  # "SGUS"
    VERSION = 1

    @staticmethod
    def emit(adapter: ModelAdapter, nodes: list[IRNode], output_path: str, precision_map: dict[str, str]) -> None:
        """Serializes tensors with tiered precision into the S-GGUF format."""
        print(f"Emitting S-GGUF to {output_path}...")

        # 1. Prepare Manifest
        manifest = {
            "version": SGUFEmitter.VERSION,
            "tensors": [node.to_dict() for node in nodes if node.kind == "tensor"],
            "precision_map": precision_map
        }
        manifest_bytes = json.dumps(manifest).encode('utf-8')

        # 2. Open binary file
        with open(output_path, "wb") as f:
            # Header
            f.write(struct.pack("<I", SGUFEmitter.MAGIC))
            f.write(struct.pack("<I", SGUFEmitter.VERSION))

            # Placeholder for Manifest Offset (we'll fill it later)
            f.write(struct.pack("<Q", 0)) 

            # Tensors (delegating to adapter)
            # For now, we simulate this as the adapter's emit_model responsibility
            # while the emitter handles the container.
            adapter.emit_model(nodes, output_path + ".tensors", precision_map)

            # Write Manifest
            manifest_offset = f.tell()
            f.write(manifest_bytes)

            # Fix header offset
            f.seek(8)
            f.write(struct.pack("<Q", manifest_offset))

        print(f"Successfully emitted {output_path}")
