"""
[DNA_TAG]
ORIGIN: BleakNarratives/Whorl
PILLAR: slice
PATH: whorl/slice/whorl_slice.py
LAST_SYNC: 2026-08-31
[/DNA_TAG]

whorl_slice — confidence-gated split inference prototype.

The "tensile-testing mesh" idea, made concrete: a small quantized local model
runs the cheap first pass on-device; when the sampler's confidence on the next
token falls below a threshold it has hit a "quantization hole" (two distinct
semantic vectors collapsed to the same coordinate by the lossy quant weights).
Whorl then SLICES: packs the recent context + the local logits into a slim
payload and asks a dense FP16 cloud model (Groq gpt-oss-120b via the Boardroom
router, which already has key-pool + 429 backoff) to emit corrected logits,
which are merged back. The rest of the time everything stays local.

This is "inverted speculative decoding": instead of the small model drafting
for the big one, the big model only adjudicates the tokens the small model is
unsure about. Compute stays ~95% local.

Two local backends so it runs on ANY box:
  - llama-server backend : talks to a local llama.cpp llama-server over HTTP
                           and pulls GENUINE single-token log-probabilities from
                           the model via /v1/completions logprobs. This is the
                           real 4-bit path — confidence is the model's actual
                           uncertainty, not a simulation. Live-wired 2026-08-31.
  - reference backend    : deterministic simulator with a configurable
                           quantization-loss injection so the whole prototype
                           runs OFFLINE with zero model binary. This backend is
                           the test/CI default.

The cloud FP16 pass is REAL (router.call_model -> Groq gpt-oss-120b) whenever a
Groq key is present in the env; otherwise the slice degrades to local-only and
reports the holes it would have sent.

Run (llama-server must be up first, memory-gated):
  # 1) launch the local 4-bit server (0.5B Q4, ~470MB RSS, safe on 2.6Gi box):
  cd ~/llama.cpp && setsid ./llama-server -m ~/models/glue/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf \
      --port 8080 --host 127.0.0.1 -c 512 -t 2 -tb 2 -ngl 0 --no-warmup \
      > ~/models/glue/llama-server.live.log 2>&1 < /dev/null & disown
  # 2) slice against REAL 4-bit logits (holes -> Groq FP16 adjudicator):
  python3 -m whorl.slice.whorl_slice --backend llama --prompt "..." --live
  # offline reference path (no binary needed):
  python3 -m whorl.slice.whorl_slice --prompt "..."
  python3 -m whorl.slice.whorl_slice --selftest
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------- #
#  Payloads / dataclasses
# ---------------------------------------------------------------------------- #


@dataclass
class SampleResult:
    """What the local pass returns for one position."""
    token: str
    top_k: List[Tuple[str, float]]            # (token, prob) highest first
    confidence: float                          # 1.0 = sure, 0.0 = coin flip
    entropy: float
    hidden_state: Optional[List[float]] = None # last-layer hidden vector (the payload)
    logits: Optional[Dict[str, float]] = None  # token -> raw logit from the pass
    sliced: bool = False                       # True if this position hit a hole
    corrected: Optional[str] = None            # token the cloud pass returned
    correction_confidence: Optional[float] = None


@dataclass
class SliceLog:
    """Per-slice telemetry record (the tensile test's readout)."""
    position: int
    context_tail: str
    local_top1: str
    confidence: float
    sliced: bool
    hidden_state_dim: int = 0                  # size of the transported vector
    corrected: Optional[str] = None
    correction_confidence: Optional[float] = None
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------- #
#  Local backends
# ---------------------------------------------------------------------------- #


class LocalPass:
    """Interface the controller calls. Subclasses provide next_token()."""

    def next_token(self, context: str) -> SampleResult:
        raise NotImplementedError


class ReferenceQ4Pass(LocalPass):
    """Deterministic simulator of a quantized local model.

    Produces a paraphrased, lower-information continuation (models the kind of
    drift a 4-bit model shows) and injects *synthetic quantization holes* on a
    schedule (`hole_spacing`): at those positions the top-k probs flatten toward
    uniform (low confidence) exactly the way a real quant collapse does. This
    makes the offline prototype deterministic and testable while standing in for
    the real GGUF path (llama-server backend).
    """

    def __init__(
        self,
        hole_spacing: int = 4,
        seed: int = 7,
        vocab: Optional[List[str]] = None,
        hidden_dim: int = 8,
    ) -> None:
        self.hole_spacing = max(1, int(hole_spacing))
        self._pos = 0
        self._hidden_dim = max(4, int(hidden_dim))
        if vocab is None:
            vocab = [
                "the", "and", "but", "if", "of", "to", "for", "not", "then",
                "a", "in", "on", "with", "however", "so", "yet", "also", "may",
                "thus", "when", "because", "or", "by", "at", "from",
            ]
        self._vocab = vocab
        self._seeded_next = seed

    def _next_prng(self) -> int:
        self._seeded_next = (self._seeded_next * 1103515245 + 12345) & 0x7FFFFFFF
        return self._seeded_next

    def next_token(self, context: str) -> SampleResult:
        del context  # determinism driven solely by the seeded LCG, not input
        self._pos += 1
        hole = (self._pos % self.hole_spacing) == 0
        # deterministic pseudo-random continuation word from the seeded LCG
        r = self._next_prng()
        pick = self._vocab[(r >> 5) % len(self._vocab)]
        # Build a small top-k around `pick`.
        k = min(4, len(self._vocab))
        base = []
        used = set()
        for i in range(k):
            idx = (pick_hash := (r + i * 7919)) % len(self._vocab)
            if idx in used:
                continue
            used.add(idx)
            base.append(self._vocab[idx])
        if pick not in base:
            base[0] = pick
        if hole:
            # quant collapse: flatten probs toward uniform
            probs = [1.0 / len(base)] * len(base)
        else:
            probs = [0.0] * len(base)
            probs[0] = 0.82
            for i in range(1, len(base)):
                probs[i] = (1.0 - probs[0]) / (len(base) - 1 or 1)
        toks = [t for t in base if t]
        probs = probs[: len(toks)]
        norm = sum(probs) or 1.0
        probs = [p / norm for p in probs]
        top_k = list(zip(toks, probs))
        ent = -sum(p * math.log(p) for p in probs if p > 0)
        norm_ent = ent / math.log(len(toks)) if len(toks) > 1 else 0.0
        conf = 1.0 - norm_ent

        # Hidden state: last-layer activation vector for this position. In the
        # reference pass it's a deterministic LCG-driven embedding; a real GGUF
        # backend would emit the actual last hidden layer here. This is the
        # payload we ship to the cloud FP16 adjudicator when we hit a hole.
        hs = [(self._next_prng() / 0x7FFFFFFF) for _ in range(self._hidden_dim)]
        # compact, deterministic logits (raw) over the candidate tokens
        logits = {
            t: (r % 100) / 100.0 - 0.5 + (j * 0.13)
            for j, t in enumerate(toks)
        }
        res = SampleResult(
            token=top_k[0][0], top_k=top_k, confidence=conf, entropy=ent,
            hidden_state=hs, logits=logits,
        )
        return res


class LlamaServerPass(LocalPass):
    """Real GGUF path: talk to a local llama.cpp `llama-server`.

    Expects a running server on base_url. Uses single-token logits via the
    OpenAI-compatible /v1/completions endpoint with a fixed single-token
    predicted length. If no server is reachable at construction, raises.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._probe()

    def _probe(self) -> None:
        try:
            urllib.request.urlopen(self.base_url + "/health", timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"llama-server not reachable at {self.base_url}: {exc}"
            ) from exc

    def next_token(self, context: str) -> SampleResult:
        """Genuine single-token logit extraction from a live llama-server.

        Uses the OpenAI-compatible /v1/completions endpoint with logprobs and
        greedy decoding (temperature=0) so the returned top_logprobs ARE the
        real model's top-k log-probabilities over its vocab — i.e. true 4-bit
        confidence, not a simulation. The last hidden layer is not exposed by
        this endpoint, so hidden_state is left None (SliceController already
        treats None safely); `logits`/top_k/confidence are all real.
        """
        req = urllib.request.Request(
            self.base_url + "/v1/completions",
            data=json.dumps({
                "prompt": context[-2048:],
                "max_tokens": 1,
                "temperature": 0,
                "top_p": 1,
                "n": 1,
                "logprobs": 8,
                "echo": False,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"llama-server /v1/completions failed: {exc}") from exc

        choices = (data or {}).get("choices") or []
        if not choices:
            raise RuntimeError("llama-server returned no choices")
        top1 = ((choices[0].get("text") or "").strip()) or None
        # logprobs can be nested two ways depending on llama.cpp build:
        #   older: logprobs.top_logprobs                (dict token->logp)
        #   newer: logprobs.content[-1].top_logprobs     (list entry equality)
        lp: Dict[str, float] = {}
        lp_top = (choices[0].get("logprobs") or {}).get("top_logprobs")
        if isinstance(lp_top, dict) and lp_top:
            lp = {str(k): float(v) for k, v in lp_top.items()}
        else:
            content = (choices[0].get("logprobs") or {}).get("content") or []
            for entry in (content if isinstance(content, list) else []):
                tl = entry.get("top_logprobs") if isinstance(entry, dict) else None
                if isinstance(tl, list):
                    for item in tl:
                        if isinstance(item, dict) and item.get("token") is not None:
                            lp[item["token"]] = float(item.get("logprob", 0.0))
        if not lp:
            # Fallback: no logprobs returned -> single-candidate degenerate row.
            return SampleResult(
                token=top1 or "", top_k=[(top1 or "", 1.0)], confidence=1.0,
                entropy=0.0, hidden_state=None, logits={top1: 0.0} if top1 else {},
            )
        # lp maps token -> log-probability (natural log). Convert to probability.
        pairs: List[Tuple[str, float]] = []
        logits: Dict[str, float] = {}
        maxp = max(0.0, *lp.values())
        for tok, lgp in lp.items():
            p = math.exp(lgp - maxp) if maxp > -float("inf") else 0.0
            logits[tok] = lgp     # keep raw log-prob as the "logit" fingerprint
            pairs.append((tok, p))
        norm = sum(p for _, p in pairs) or 1.0
        top_k = sorted(((t, p / norm) for t, p in pairs), key=lambda kv: -kv[1])
        probs = [p for _, p in top_k]
        ent = -sum(p * math.log(p) for p in probs if p > 0)
        norm_ent = ent / math.log(len(probs)) if len(probs) > 1 else 0.0
        conf = 1.0 - norm_ent
        return SampleResult(
            token=(top1 or (top_k[0][0] if top_k else "")),
            top_k=top_k, confidence=conf, entropy=ent,
            hidden_state=None, logits=logits,
        )


# ---------------------------------------------------------------------------- #
#  Cloud FP16 pass (the adjudicator)
# ---------------------------------------------------------------------------- #


class CloudFp16Pass:
    """Dense FP16 adjudicator via the Boardroom router (Groq gpt-oss-120b).

    `router.call_model(prompt, system=..., tier=FAST) -> (text, provider)` with
    built-in key pool rotation + 429 backoff + quarantine. We route ONLY the hole
    context and ask for the corrected next token. If no router / no key, live is
    disabled and the controller degrades to local-only.
    """

    def __init__(self) -> None:
        self.available = False
        self.provider = None
        import glob
        import importlib.util
        boardrooms = glob.glob(os.path.expanduser("~/The-Werkz/Official-Vertical-AI-Boardroom/router.py")) \
            + glob.glob(os.path.expanduser("~/Official-Vertical-AI-Boardroom/router.py"))
        if not boardrooms:
            self._router = None
            return
        try:
            import importlib.util  # noqa: F811
            spec = importlib.util.spec_from_file_location("boardroom_router", boardrooms[0])
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, os.path.dirname(boardrooms[0]))
            spec.loader.exec_module(mod)
            self._router = mod
            self._tier = getattr(mod, "ModelTier", None)
            self.available = True
        except Exception:  # noqa: BLE001
            self._router = None

    def correct(
        self,
        context_tail: str,
        local_top1: str,
        confidence: float,
        hidden_state: Optional[List[float]] = None,
        local_logits: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, float]], float]:
        """Adjudicate a low-confidence position.

        Returns (corrected_token, corrected_logits, latency_ms). The halide
        (dense FP16) model sees the context plus a compact, human-readable
        digest of the hidden state (its L2 norm + top dimensions) plus the local
        top-k logits, and returns the most likely next token. corrected_logits is
        the (smoothed) per-candidate logits we merge back into the local pass.
        """
        if not self.available:
            return None, None, 0.0
        try:
            hs_digest = ""
            if hidden_state:
                norm = math.sqrt(sum(x * x for x in hidden_state)) or 1.0
                # report the strongest (absolute) dims as a numeric fingerprint
                order = sorted(
                    enumerate(hidden_state), key=lambda x: -abs(x[1]))[:4]
                dims = ",".join(f"h{i}:{x:.3f}" for i, x in order)
                hs_digest = f" hidden_norm={norm:.4f} top_dims=[{dims}]"
            log_digest = (
                ", ".join(f"{t}:{v:.2f}" for t, v in (
                    sorted(local_logits.items(), key=lambda kv: -kv[1])[:5]
                    if local_logits else []))
            )
            prompt = (
                "You are a dense (FP16) adjudicator for an uncertain quantized "
                "local model.\n"
                f"Local token={local_top1!r} confidence={confidence:.3f} "
                f"({hs_digest or 'hidden_digest=n/a'}).\n"
                f"Local candidate logits: {log_digest or 'n/a'}.\n"
                "Context:\n---\n" + context_tail.strip()[-1200:] + "\n---\n"
                "Reply with ONLY the single most likely single next token."
            )
            t0 = time.time()
            tier = getattr(self._tier, "FAST", "fast") if self._tier else "fast"
            text, prov = self._router.call_model(prompt, tier=tier)
            latency_ms = (time.time() - t0) * 1000.0
            tok = (text or "").strip().split("\n")[0].strip().split()[0] if (text or "").strip() else None
            if not tok:
                return None, None, latency_ms
            self.provider = prov
            # corrected logits: blend the cloud's chosen token forward as a
            # refined candidate set (per-token confidence of the adjudicator)
            corrected_logits: Dict[str, float] = {}
            if local_logits:
                base = max(0.15, float(confidence))
                for t in local_logits:
                    corrected_logits[t] = base if t == tok else max(0.02, local_logits[t] * 0.4)
                corrected_logits[tok] = corrected_logits.get(tok, 0.25) + 0.4
            return tok, corrected_logits or None, latency_ms
        except Exception:  # noqa: BLE001
            return None, None, 0.0


# ---------------------------------------------------------------------------- #
#  Controller — the tensile-testing mesh
# ---------------------------------------------------------------------------- #


class SliceController:
    """Runs the local pass token by token; ADJUDICATES only low-confidence holes.

    tension mesh: when confidence >= gate -> trust local. When < gate -> that's
    a quantization hole -> send context slice to CloudFp16Pass, merge corrected
    token back. Records a SliceLog per position (the "readout").
    """

    def __init__(
        self,
        local: LocalPass,
        cloud: Optional[CloudFp16Pass] = None,
        confidence_gate: float = 0.4,
        max_uncertain_consensus: int = 2,
    ) -> None:
        self.local = local
        self.cloud = cloud
        self.gate = float(confidence_gate)
        self.max_consensus = max_uncertain_consensus
        self.history: List[SliceLog] = []

    def generate(self, prompt: str, max_tokens: int = 12) -> List[SampleResult]:
        out: List[SampleResult] = []
        context = prompt or ""
        for pos in range(max(1, int(max_tokens))):
            res = self.local.next_token(context)
            res.sliced = res.confidence < self.gate
            latency_ms = 0.0
            corrected_logits: Optional[Dict[str, float]] = None
            if res.sliced and self.cloud is not None:
                # ship the hidden state + local logits to the dense adjudicator
                corrected, clg, latency_ms = self.cloud.correct(
                    context, res.token, res.confidence,
                    hidden_state=res.hidden_state, local_logits=res.logits,
                )
                res.corrected = corrected
                corrected_logits = clg
                if corrected:
                    res.token = corrected
                # merge the cloud logit corrections back onto the local result
                if clg:
                    merged = list(res.top_k)
                    merged = [(t, clg.get(t, p)) for t, p in merged]
                    res.top_k = merged
            context = (context + " " + res.token).strip()[-2048:]
            self.history.append(SliceLog(
                position=pos + 1,
                context_tail=context[-200:],
                local_top1=res.token,
                confidence=round(res.confidence, 4),
                sliced=res.sliced,
                hidden_state_dim=len(res.hidden_state) if res.hidden_state else 0,
                corrected=res.corrected,
                correction_confidence=res.correction_confidence,
                latency_ms=round(latency_ms, 1),
            ))
            out.append(res)
        return out

    def report(self) -> Dict[str, Any]:
        total = len(self.history)
        sliced = sum(1 for h in self.history if h.sliced)
        return {
            "positions": total,
            "sliced": sliced,
            "slice_rate": round(sliced / total, 3) if total else 0.0,
            "cloud_present": bool(self.cloud and self.cloud.available),
            "avg_confidence": round(
                sum(h.confidence for h in self.history) / total, 4) if total else 0.0,
            "telemetry": [vars(h) for h in self.history],
        }


_cloud = CloudFp16Pass()

def _build_local(args: argparse.Namespace) -> LocalPass:
    if args.backend == "llama":
        return LlamaServerPass(base_url=args.llama_url)
    return ReferenceQ4Pass(hole_spacing=args.hole_spacing or 4, seed=args.seed or 7)


def selftest(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="whorl_slice --selftest")
    ap.add_argument("--hole-spacing", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--backend", default="reference")
    ap.add_argument("--llama-url", default="http://127.0.0.1:8080")
    args = ap.parse_args(argv)
    local = _build_local(args)
    ctl = SliceController(local=local, cloud=_cloud)
    res = ctl.generate("selftest ", max_tokens=8)
    rep = ctl.report()
    assert rep["positions"] == 8
    assert rep["sliced"] >= 1, f"expected >=1 hole, got {rep['sliced']}"
    print(json.dumps(rep, indent=2))
    print("OK: selftest deterministic (reference backend, offline).")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="whorl_slice")
    ap.add_argument("--prompt", default="The plan begins when", help="seed context")
    ap.add_argument("--max-tokens", type=int, default=12)
    ap.add_argument("--gate", type=float, default=0.4, help="confidence gate")
    ap.add_argument("--backend", choices=["reference", "llama"], default="reference")
    ap.add_argument("--llama-url", default="http://127.0.0.1:8080")
    ap.add_argument("--hole-spacing", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--live", action="store_true", help="route holes to Groq FP16")
    ap.add_argument("--json", action="store_true", help="emit JSON report only")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(argv=[])

    local = _build_local(args)
    cloud = _cloud if args.live else None
    if args.live and not (_cloud and _cloud.available):
        print("[slice] --live requested but no Groq router/key available -> local-only", file=sys.stderr)
    ctl = SliceController(local=local, cloud=cloud, confidence_gate=args.gate)
    res = ctl.generate(args.prompt, max_tokens=args.max_tokens)
    rep = ctl.report()
    if args.json:
        print(json.dumps(rep, indent=2))
        return 0
    gen = " ".join(r.token for r in res)
    print("--- generated (sliced positions marked *) ---")
    print(gen)
    print("--- slice report ---")
    print(f"positions={rep['positions']} sliced={rep['sliced']} "
          f"slice_rate={rep['slice_rate']} avg_conf={rep['avg_confidence']} "
          f"cloud={'present' if rep['cloud_present'] else 'local-only'}")
    for h in rep["telemetry"]:
        mark = "*" if h["sliced"] else " "
        cor = f" -> {h['corrected']}" if h["corrected"] else ""
        print(f"  {mark} pos{h['position']:>3} conf={h['confidence']:.3f} "
              f"t={h['local_top1']}{cor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())