"""
whorl.tailor
────────────
THE TAILOR — QRD engine + MindaIntent parser + the Cognitive Shadow.

Bridges the sl1u3 doctrine into the outer package on the firm rails:

  * the legacy `whorl/whorl/tailor` module supplied the design — the QRD
    tiers (BLINK / BRIEF / DEEP / FULL), the MindaIntent schema, and the
    Tailor's voice. Its prompts (QRD_SYSTEM, INTENT_SYSTEM) are imported
    and reused verbatim — the bridge is a bridge, not a rewrite.
  * the call path runs through model_spirit (bounded, unified routing)
    with deterministic offline fallbacks — the Tailor never hangs.
  * the Cognitive Shadow is the sl1u3 layer made mechanical: it reads the
    operator's ACTUAL telemetry — the Orbit Vane's bearing (whorl drift),
    the gate's pulse index, and open roadmap threads — and fits the QRD
    against it. "It doesn't prop up your cognitive dissonance. It keeps
    your edges razor-sharp." No flattery on the model path, no flattery
    off it.

CLI:
    whorl tailor qrd 'text'               # four-tier distillation
    whorl tailor intent 'chaotic dump'    # MindaIntent structured parsing
    whorl tailor shadow 'text'            # QRD fitted to your real orbit + pulse
"""

from __future__ import annotations
import re
import time
from typing import Any, Optional

from whorl.memory.cycle import _Timeout
from whorl.whorl.tailor import QRD_SYSTEM, INTENT_SYSTEM, _extract_json

# ─── deterministic fallback tables ───────────────────────────────────────

_DOMAINS = {
    "plumber": ["pipe", "plumb", "drain", "faucet", "leak", "water", "toilet"],
    "auto_dealer": ["car", "dealer", "vehicle", "trade", "truck", "test drive"],
    "convenience": ["store", "shop", "convenience", "gas", "register", "shelf"],
}
_URGENT = ["urgent", "asap", "now", "today", "rent", "eviction", "deadline",
           "overdue", "tonight", "broke"]
_POSITIVE = ["love", "great", "win", "excited", "amazing", "perfect", "best"]
_NEGATIVE = ["hate", "worry", "fear", "fail", "broke", "lose", "trouble",
             "stuck", "dread"]
_RISK = ["risk", "unknown", "danger", "cost", "delay", "fail", "but",
         "however", "cannot", "unlikely"]


def _sentences(text: str, max_n: int = 6) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= 12][:max_n]


def _call_model(prompt: str, temperature: float = 0.3) -> Optional[str]:
    """One wall-clocked model call through model_spirit. None on failure —
    the Tailor falls back, never hangs."""
    try:
        from whorl.tools.model_spirit import invoke_model
        out, _meta = _Timeout(6.0).run(
            invoke_model, prompt, max_tokens=500, temperature=temperature)
        if not out or out.startswith(("Model Error", "Remote Error",
                                      "Groq Error", "Parse Error")):
            return None
        return out.strip()
    except Exception:
        return None


class Tailor:
    """
    The Tailor. Four-tier QRD distillation, MindaIntent parsing, and the
    Cognitive Shadow fit.

    Usage:
        t = Tailor(state=SharedState())
        rec = t.qrd("...")            # blink/brief/deep/full
        intent = t.parse_intent("...")
        shadow = t.shadow_fit("...")  # qrd + fit telemetry
    """

    def __init__(self, prefer_offline: bool = False, state=None):
        self.prefer_offline = prefer_offline
        self.state = state
        self.backend = "offline"

    # ── QRD (the legacy engine, on outer rails) ───────────────────────

    def qrd(self, text: str, source_id: str = "",
            context: Optional[dict] = None) -> dict[str, Any]:
        text = text.strip()
        if not text:
            raise ValueError("empty input — the Tailor needs something to fit")

        telemetry = ""
        if context:
            gate_line = ""
            if context.get("gate_density") is not None:
                g_accept = "passed" if context.get("gate_accepted") else "BLOCKED"
                g_dens = context["gate_density"]
                g_slack = context.get("gate_slack", "?")
                g_drop = context.get("gate_dropped", [])
                gate_line = (
                    f"  gate: {g_accept} — density {g_dens} (slack {g_slack}×)"
                )
                if g_drop:
                    gate_line += f" — dropped: {', '.join(g_drop[:5])}"
                gate_line += "\n"
            committee_block = ""
            if context.get("committee_verdict"):
                c_glyph = context.get("committee_glyph", "⟳·⟲")
                c_align = context.get("committee_alignment", "?")
                c_verdict = context["committee_verdict"]
                c_q = context.get("committee_question", "")
                committee_block = (
                    f"  committee ({c_align}): {c_glyph} "
                    f"'{c_q[:80]}' → {c_verdict[:150]}…\n"
                )
            telemetry = (
                "OPERATOR TELEMETRY (read from their own artifacts — do not "
                "flatter, keep their edges sharp):\n"
                f"  orbit: {context.get('orbit_glyph', '?')} "
                f"{context.get('orbit_intent', '?')} at speed "
                f"{context.get('orbit_speed', '?')}/10\n"
                f"  pulse: {context.get('pulse', '?')} (0 calm — 1 frantic)\n"
                f"  open threads: {context.get('open_threads', '?')}\n"
                f"{gate_line}"
                f"{committee_block}\n"
            )

        blink = brief = deep = None
        if not self.prefer_offline:
            raw = _call_model(
                f"{QRD_SYSTEM}\n\n{telemetry}<INPUT>\n{text}\n</INPUT>")
            if raw:
                try:
                    data = _extract_json(raw)
                    if isinstance(data, dict) and data.get("blink"):
                        # Per-tier fallback: the model may return partial
                        # JSON — missing tiers get the deterministic fill.
                        fb_blink, fb_brief, fb_deep = self._qrd_fallback(text)
                        blink = data.get("blink") or fb_blink
                        brief = data.get("brief") or fb_brief
                        deep = data.get("deep") or fb_deep
                except Exception:
                    pass

        if blink is None:
            self.backend = "offline"
            blink, brief, deep = self._qrd_fallback(text)

        record = {
            "id": f"{int(time.time() * 1000) % 10**10:x}",
            "at": time.time(),
            "source_id": source_id or "manual",
            "kind": "qrd",
            "backend": self.backend,
            "blink": blink,
            "brief": brief,
            "deep": deep,
            "full": text,
        }
        if context:
            record["kind"] = "shadow"
            record["fit"] = context
        self._save(record)
        return record

    def _qrd_fallback(self, text: str) -> tuple[str, str, str]:
        sents = _sentences(text, 6)
        blink = sents[0] if sents else (
            text[:90].rstrip() + ("…" if len(text) > 90 else ""))
        brief = " ".join(sents[:3]) if sents else text[:200]
        if len(brief) > 400:
            brief = brief[:397].rstrip() + "…"
        risks = [s for s in sents if any(w in s.lower() for w in _RISK)]
        deep = (
            "Situation: " + (sents[0] if sents else text[:120]) + "\n"
            "Options: " + ("; ".join(sents[1:3]) if len(sents) > 1
                           else "single path — commit or decline") + "\n"
            "Recommendation: " + blink + "\n"
            + (("Risks: " + "; ".join(risks[:2]) + "\n") if risks
               else "Risks: none flagged deterministically\n")
            + "First Action: " + (sents[0] if sents else text[:120])
        )
        return blink, brief, deep

    # ── MindaIntent (the legacy parser, on outer rails) ───────────────

    def parse_intent(self, thought: str) -> dict[str, Any]:
        thought = thought.strip()
        if not thought:
            raise ValueError("empty thought — MindaIntent needs the dump")

        if not self.prefer_offline:
            raw = _call_model(
                f"{INTENT_SYSTEM}\n\n<THOUGHT>\n{thought}\n</THOUGHT>")
            if raw:
                try:
                    data = _extract_json(raw)
                    if isinstance(data, dict) and data.get("core_intent"):
                        self.backend = "model"
                        data["at"] = time.time()
                        data["backend"] = "model"
                        data["kind"] = "intent"
                        self._save(data)
                        return data
                except Exception:
                    pass

        self.backend = "offline"
        record = self._intent_fallback(thought)
        record["kind"] = "intent"
        record["backend"] = "offline"
        self._save(record)
        return record

    def _intent_fallback(self, thought: str) -> dict[str, Any]:
        low = thought.lower()
        sents = _sentences(thought, 4)

        domain, best = "general", 0
        for name, words in _DOMAINS.items():
            hits = sum(1 for w in words if w in low)
            if hits > best:
                best, domain = hits, name

        urgency = min(1.0, sum(1 for w in _URGENT if w in low) * 0.25)
        valence = (min(1.0, sum(1 for w in _POSITIVE if w in low) * 0.2)
                   - min(1.0, sum(1 for w in _NEGATIVE if w in low) * 0.2))
        valence = round(max(-1.0, min(1.0, valence)), 2)
        core = sents[0] if sents else thought[:140]

        return {
            "domain_hint": domain,
            "urgency": round(urgency, 2),
            "emotional_valence": valence,
            "constraints": [],
            "core_intent": core,
            "execution_paths": [{
                "name": "first pass",
                "description": core[:120],
                "estimated_hours": 1,
                "requires_api": False,
            }],
            "resources_needed": [],
            "confidence": 0.5,
        }

    # ── the Cognitive Shadow (the sl1u3 layer) ────────────────────────

    def _shadow_context(self, text: Optional[str] = None,
                        committee: Optional[dict] = None) -> dict[str, Any]:
        """The operator's ACTUAL telemetry: orbit from the Orbit Vane,
        pulse from the gate's chaos index, open threads from the roadmap,
        and — when text is given — a gate evaluation of the input itself
        so the shadow sees whether the question matches the orbit.

        When a committee deliberation record is passed, the shadow also
        knows what the bicameral mind just concluded — so the Tailor
        sharpens the execution plan against the verdict."""
        ctx: dict[str, Any] = {"orbit_glyph": None, "orbit_intent": None,
                               "orbit_speed": None, "pulse": None,
                               "open_threads": None,
                               "gate_density": None, "gate_slack": None,
                               "gate_dropped": None,
                               "committee_verdict": None,
                               "committee_glyph": None,
                               "committee_alignment": None}
        try:
            from whorl.drift import orbit_report
            rep = orbit_report(1, state=self.state)
            ctx["orbit_glyph"] = rep["glyph"]
            ctx["orbit_intent"] = rep["intent"]
            ctx["orbit_speed"] = rep["speed"]
            ctx["open_threads"] = rep.get("roadmap_open_items")
        except Exception:
            pass
        try:
            from whorl.memory.gate import chaos_index
            ctx["pulse"] = chaos_index()
        except Exception:
            pass
        if text:
            try:
                from whorl.memory.gate import evaluate as gate_eval
                g = gate_eval(text)
                ctx["gate_accepted"] = g["accepted"]
                ctx["gate_density"] = g["density"]
                ctx["gate_slack"] = g["slack"]
                ctx["gate_dropped"] = g.get("dropped_words", [])
                ctx["gate_reason"] = g.get("reason", "")
            except Exception:
                pass
        if committee:
            interp = committee.get("interpreter", {})
            ctx["committee_verdict"] = interp.get("content", "")[:300]
            ctx["committee_glyph"] = interp.get("glyph", "⟳·⟲")
            ctx["committee_question"] = committee.get("question", "")[:200]
            ctx["committee_alignment"] = (
                "divergent" if committee.get("disagreement") else "aligned"
            )
            ctx["committee_backend"] = committee.get("backend", "?")
        return ctx

    def shadow_fit(self, text: str, source_id: str = "",
                   committee: Optional[dict] = None) -> dict[str, Any]:
        """A QRD fitted against the operator's real orbit + pulse. The
        anti-flatterer: the fit note names their actual state so the
        sharpening is grounded, not decorative. The input itself is gated
        so the shadow knows if the question is as sharp as the orbit.

        When a committee deliberation record is passed, the shadow also
        knows what the bicameral mind just concluded — the Tailor sharpens
        the execution plan against the verdict."""
        return self.qrd(text, source_id=source_id,
                        context=self._shadow_context(text=text,
                                                     committee=committee))

    # ── persistence (SharedState — the vane sees these) ───────────────

    def _save(self, record: dict[str, Any]) -> None:
        if self.state is None:
            return
        # .get() not []: a record missing 'kind' must persist under a safe
        # namespace instead of crashing the whole Tailor.
        self.state.write(
            f"tailor:{record.get('kind', 'misc')}:{time.time() * 1000:.0f}",
            record, "whorl.tailor")


def format_qrd(record: dict[str, Any], kind: str = "qrd") -> str:
    """Plain ASCII panels — the Tailor dresses sharp, not heavy."""
    lines = [f"── THE TAILOR · {kind.upper()} " + "─" * max(0, 26 - len(kind))]
    lines.append(f"  BLINK (30 sec)  {record.get('blink', '')}")
    lines.append(f"  BRIEF (2 min)   {record.get('brief', '')}")
    deep = record.get("deep", "")
    lines.append(f"  DEEP (10 min)   {deep}")
    full = record.get("full", "")
    lines.append(f"  FULL            {full[:80]}{'…' if len(full) > 80 else ''}")

    fit = record.get("fit")
    if fit:
        parts = []
        if fit.get("orbit_glyph"):
            parts.append(f"orbit {fit['orbit_glyph']} {fit.get('orbit_intent')} "
                         f"@{fit.get('orbit_speed')}")
        if fit.get("pulse") is not None:
            parts.append(f"pulse {fit['pulse']:.2f}")
        if fit.get("open_threads"):
            parts.append(f"{fit['open_threads']} open threads")
        if fit.get("gate_density") is not None:
            g_accept = "✓" if fit.get("gate_accepted") else "✗"
            parts.append(f"gate {g_accept} dens {fit['gate_density']} slack {fit.get('gate_slack','?')}×")
        if fit.get("committee_verdict"):
            c_glyph = fit.get("committee_glyph", "⟳·⟲")
            c_align = fit.get("committee_alignment", "?")
            c_verdict = fit["committee_verdict"]
            # Grab the last sentence — the verdict, not the opening formula.
            sents = re.split(r"(?<=[.!?])\s+", c_verdict.strip())
            snippet = sents[-1] if sents else c_verdict[:50]
            if len(snippet) > 60:
                snippet = snippet[:57] + "…"
            parts.append(f"committee {c_glyph} {c_align} \"{snippet}\"")
        if parts:
            lines.append(f"  fit             " + " · ".join(parts))

    lines.append(f"  backend         {record.get('backend', '?')}")
    return "\n".join(lines)


def format_intent(record: dict[str, Any]) -> str:
    lines = ["── THE TAILOR · MINDAINTENT " + "─" * max(0, 22)]
    lines.append(f"  domain          {record.get('domain_hint', '?')} · "
                 f"urgency {record.get('urgency', '?')} · "
                 f"valence {record.get('emotional_valence', '?')} · "
                 f"confidence {record.get('confidence', '?')}")
    lines.append(f"  core intent     {record.get('core_intent', '')}")
    for p in record.get("execution_paths", []):
        desc = p.get("description", "")
        lines.append(f"  path            {p.get('name', '?')} — "
                     f"{desc[:80]}{'…' if len(desc) > 80 else ''}")
    lines.append(f"  backend         {record.get('backend', '?')}")
    return "\n".join(lines)
