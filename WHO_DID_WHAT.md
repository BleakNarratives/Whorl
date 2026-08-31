# WHO DID WHAT — Whorl

## Buffy (Codebuff) — 2026-08-31

### whorl_slice — confidence-gated split inference (v1 + v2)
- **v1 (commit `5ea544a`):** new `whorl/slice/` package. `SliceController` runs a
  local quant pass token-by-token; when confidence falls below the gate it has hit
  a "quantization hole" (where 4-bit loss collapsed distinct vectors), so Whorl
  slices and sends that context to a dense FP16 cloud adjudicator (Groq
  gpt-oss-120b via the Boardroom router — key-pool + 429 backoff inherited) and
  merges the corrected token back. `ReferenceQ4Pass` (deterministic synthetic
  hole injection) default; `LlamaServerPass` GGUF backend wiring-ready. Cloud pass
  loads the Boardroom router via importlib; passes `ModelTier.FAST` enum (the
  string `"fast"` hits a `KeyError`). Fixes: reference-pass determinism (was
  clobbering its seeded LCG with a salted `hash()`).
- **v2 (commit `307cd1b`):** upgraded transport from token-text to genuine
  hidden-state → corrected-logit. `SampleResult` now carries a real `hidden_state`
  vector + raw candidate logits. `CloudFp16Pass.correct()` consumes them, ships
  the FP16 model a digest (L2 norm + top dims + candidate logits), and returns
  `(corrected_token, corrected_logits, latency)`; controller merges corrected
  logits back onto the sliced position. New `tests/test_slice_hidden.py` (4/4).
- Full Whorl suite now **41 pass / 2 skip** (cv2-independent).
- Verified live: hole routed to Groq, corrected token + logits merged back.
- **Honest gap:** local `hidden_state` is a SIMULATED embedding, not a real GGUF
  last-hidden-layer. True quant→FP16 requires building llama.cpp and wiring
  `LlamaServerPass` against `~/models/glue/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf`.

### Earlier (2026-08-28 through 08-30, prior sessions)
- Signal Loom telemetry adapters + offline demo (`whorl/signal_loom_adapters.py`,
  `whorl/signal_loom_demo.py`), Whorl Agent Bus Phase 1 + hardening, Fire Drill
  score feedback routing, full regression suite + cv2 isolation.