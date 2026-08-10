"""
whorl.tools.adapters.safetensors_adapter — Adapter for Safetensors models.
"""

import os
from safetensors.torch import load_file, save_file
import torch
from whorl.tools.decompiler import ModelAdapter, IRNode

class SafetensorsAdapter(ModelAdapter):
    name = "safetensors"
    extensions = [".safetensors"]

    def __init__(self):
        self.source_path = None

    def parse_model(self, model_path: str) -> list[IRNode]:
        """Parses a safetensors file into IR nodes."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        self.source_path = model_path
        tensors = load_file(model_path)
        nodes = []
        
        for name, tensor in tensors.items():
            nodes.append(IRNode(
                kind="tensor",
                target=name,
                value=tensor.shape,
                meta={
                    "dtype": str(tensor.dtype),
                }
            ))
        return nodes

    def emit_model(self, nodes: list[IRNode], output_path: str, precision_map: dict[str, str]) -> None:
        """Emits model with tiered precision quantization."""
        if not self.source_path:
            raise ValueError("No source model path set. Call parse_model first.")
            
        source_tensors = load_file(self.source_path)
        new_state_dict = {}
        
        for node in nodes:
            if node.kind == "tensor":
                name = node.target
                tensor = source_tensors[name]
                
                # Apply tiered quantization
                if name in precision_map:
                    target_precision = precision_map[name]
                    
                    if target_precision == "int8":
                        # Simple INT8 quantization: scale and round
                        scale = tensor.abs().max() / 127.0
                        tensor = torch.clamp(torch.round(tensor / scale), -128, 127).to(torch.int8)
                    elif target_precision == "float16":
                        tensor = tensor.to(torch.float16)
                    # else keep as is (likely float32)
                
                new_state_dict[name] = tensor
                
        save_file(new_state_dict, output_path)
