#!/usr/bin/env python3
"""
Whorl v0.1 — Reference Interpreter
Helical execution model. The instruction pointer rotates, not advances.
Thought is orbital. Tokens are serialized. This is the gap.

Section 5 reference:  AMPLITUDE: 0.0491
arXiv target: cs.PL / physics.comp-ph

Usage:
    python whorl.py              # runs Section 5 reference program
    python whorl.py program.whr  # runs a .whr source file
"""

import re
import math
import sys
import numpy as np
from typing import Any, Dict, List, Tuple, Optional

# ─── LEXER ────────────────────────────────────────────────────────────────────

TOKEN_RE = re.compile(
    r'\s*(?:'
    r'(#[^\n]*)'                         # comment
    r'|([A-Z_][A-Z0-9_]*)'              # keyword or UPPER_IDENT
    r'|([a-z_][a-zA-Z0-9_]*)'           # lowercase_ident
    r'|([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)'  # numeric literal
    r'|([{}:,])'                          # structural punctuation
    r'|(\->)'                             # arrow
    r'|(=)'                               # equals
    r')',
    re.MULTILINE
)

def tokenize(source: str) -> List[Tuple[str, Any]]:
    """Convert source text to token stream. Strips comments."""
    tokens = []
    for m in TOKEN_RE.finditer(source):
        if   m.group(1): continue                              # comment → skip
        elif m.group(2): tokens.append(('KW',  m.group(2)))   # UPPER keyword
        elif m.group(3): tokens.append(('NAME',  m.group(3)))   # lower ident
        elif m.group(4): tokens.append(('NUM', float(m.group(4))))
        elif m.group(5): tokens.append(('SYM', m.group(5)))
        elif m.group(6): tokens.append(('SYM', m.group(6)))
        elif m.group(7): tokens.append(('SYM', m.group(7)))
    return tokens

# ─── INTERPRETER ──────────────────────────────────────────────────────────────

class WhorlInterpreter:
    """
    Executes Whorl v0.1 programs using NumPy FFT backend.
    """

    def __init__(self):
        self.N = 0
        self.phi_h = 0.0
        self.psi = None
        self.vars = {}

    def run(self, source: str):
        tokens = tokenize(source)
        pos = 0

        def peek():
            return tokens[pos] if pos < len(tokens) else ('EOF', None)

        def consume(t=None, v=None):
            nonlocal pos
            tok = peek()
            if t and tok[0] != t: raise SyntaxError(f"Expected {t}, got {tok[0]}")
            if v and tok[1] != v: raise SyntaxError(f"Expected {v}, got {tok[1]}")
            pos += 1
            return tok

        # Parse Header
        consume('KW', 'WHORL')
        consume('KW', 'VERSION')
        consume('NUM')
        consume('KW', 'FIELD')
        consume('KW', 'N')
        consume('SYM', '=')
        self.N = int(consume('NUM')[1])
        consume('KW', 'PHI_H')
        consume('SYM', '=')
        self.phi_h = float(consume('NUM')[1])
        
        self.psi = np.zeros(self.N, dtype=np.complex64)

        # Parse Body
        while pos < len(tokens):
            tok = consume()
            if tok[0] == 'KW':
                if tok[1] == 'LET':
                    name = consume('NAME')[1]
                    consume('SYM', '=')
                    self.vars[name] = self.eval_expr(consume)
                elif tok[1] == 'SPAWN':
                    name = consume('NAME')[1]
                    consume('KW', 'AT')
                    node = int(self.eval_expr(consume))
                    consume('KW', 'AMPLITUDE')
                    consume('SYM', '=')
                    amp = self.eval_expr(consume)
                    consume('KW', 'PHASE')
                    consume('SYM', '=')
                    phase = self.eval_expr(consume)
                    self.psi[node] = amp * np.exp(1j * phase)
                elif tok[1] == 'LEARN':
                    name = consume('NAME')[1]
                    consume('KW', 'STEPS')
                    consume('SYM', '=')
                    steps = int(consume('NUM')[1])
                    consume('KW', 'USING')
                    disp_type = consume('KW')[1]
                    self.learn(steps, disp_type)
                elif tok[1] == 'OBSERVE':
                    name = consume('NAME')[1]
                    consume('KW', 'AT')
                    node = int(self.eval_expr(consume))
                    consume('SYM', '->')
                    outputs = []
                    while True:
                        outputs.append(consume('KW')[1])
                        if peek() == ('SYM', ','):
                            consume()
                        else:
                            break
                    for out in outputs:
                        if out == 'AMPLITUDE':
                            val = np.abs(self.psi[node])
                            print(f"AMPLITUDE: {val:.4f}")
                        elif out == 'PHASE':
                            val = np.angle(self.psi[node])
                            print(f"PHASE: {val:.4f}")

    def eval_expr(self, consume):
        # Extremely simple expression evaluator for literals/vars
        tok = consume()
        if tok[0] == 'NUM': return tok[1]
        if tok[0] == 'NAME': return self.vars.get(tok[1], 0.0)
        return 0.0

    def learn(self, steps, disp_type):
        k = np.fft.fftfreq(self.N) * 2 * np.pi
        dt = 1.0
        c = self.vars.get('c', 1.0)
        alpha = 0.5 # Default alpha for quadratic

        for _ in range(steps):
            psi_k = np.fft.fft(self.psi)
            if disp_type == 'LINEAR':
                omega = c * np.abs(k)
            elif disp_type == 'QUADRATIC':
                omega = alpha * k**2
            else:
                omega = np.zeros_like(k)
            
            psi_k *= np.exp(-1j * omega * dt)
            self.psi = np.fft.ifft(psi_k)

# ─── SECTION 5 REFERENCE PROGRAM ─────────────────────────────────────────────

SECTION_5 = """
WHORL VERSION 0.1
FIELD N = 256 PHI_H = 0.7854

LET c = 1.0

SPAWN agent_wave AT 32
    AMPLITUDE = 1.0
    PHASE = 0.0

LEARN agent_wave
    STEPS = 10
    USING LINEAR

OBSERVE agent_wave AT 64 -> AMPLITUDE, PHASE
"""

def main():
    interpreter = WhorlInterpreter()
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            interpreter.run(f.read())
    else:
        print("Whorl v0.1 — Section 5 reference run")
        print("=" * 38)
        interpreter.run(SECTION_5)

if __name__ == '__main__':
    main()
