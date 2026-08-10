"""
whorl.tools.adapters.gguf_adapter — Adapter for GGUF models.
"""

import os
from whorl.tools.decompiler import ModelAdapter, IRNode
# Reusing logic from gguf_peek.py for parsing
from gguf_peek import peek, read_u32, read_u64, read_string, read_value, GGUF_MAGIC

class GGUFAdapter(ModelAdapter):
    name = "gguf"
    extensions = [".gguf"]

    def __init__(self):
        self.source_path = None

    def parse_model(self, model_path: str) -> list[IRNode]:
        """Parses a GGUF file into IR nodes."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        self.source_path = model_path
        meta, tensors = peek(model_path, max_kv_print=0, max_tensor_print=0) # suppress output
        
        nodes = []
        for name, dims, ttype, offset in tensors:
            nodes.append(IRNode(
                kind="tensor",
                target=name,
                value=dims,
                meta={
                    "type": ttype,
                    "offset": offset,
                }
            ))
        return nodes

    def emit_model(self, nodes: list[IRNode], output_path: str, precision_map: dict[str, str]) -> None:
        """Writes tensors back out in GGUF binary tensor format, applying tiered precision."""
        import numpy as np

        if not self.source_path:
            raise ValueError("No source model path set. Call parse_model first.")

        with open(self.source_path, "rb") as f:
            raw = f.read()

        with open(output_path, "wb") as out:
            for node in nodes:
                if node.kind != "tensor":
                    continue
                name = node.target
                offset = node.meta["offset"]
                ttype = node.meta["type"]

                dims = node.value
                count = 1
                for d in dims:
                    count *= d

                type_sizes = {0: 4, 1: 2, 8: 1, 9: 1}
                elem_size = type_sizes.get(ttype, 4)
                nbytes = count * elem_size

                tensor_bytes = raw[offset:offset + nbytes]

                target_precision = precision_map.get(name)
                if target_precision == "int8" and ttype in (0, 1):
                    arr = np.frombuffer(tensor_bytes, dtype=np.float32 if ttype == 0 else np.float16).astype(np.float32)
                    scale = np.abs(arr).max() / 127.0 if arr.size else 1.0
                    q = np.clip(np.round(arr / scale), -128, 127).astype(np.int8)
                    tensor_bytes = q.tobytes()
                elif target_precision == "float16" and ttype == 0:
                    arr = np.frombuffer(tensor_bytes, dtype=np.float32).astype(np.float16)
                    tensor_bytes = arr.tobytes()

                out.write(tensor_bytes)

        print(f"Wrote {output_path} ({os.path.getsize(output_path)} bytes)")
