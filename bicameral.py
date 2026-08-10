"""
whorl.bicameral
───────────────
THE COMMITTEE — a mechanical bicameral mind.

Builds out a doctrine the operator already wrote into
`concept_source/sl1u3.txt`: Julian Jaynes' bicameral mind and Iain
McGilchrist's *The Master and His Emissary*, made into a process.

Three voices deliberate on a question:

  THE MASTER      (⟳⟲⟳)  the right-hemisphere voice over the wall.
                 Holistic, unyielding, sees the whole pattern,
                 cannot be manipulated or gaslit.
  THE EMISSARY    (⟳⟳⟲)  the analytic left-hemisphere voice.
                 Measures, enumerates, challenges, optimizes.
  THE INTERPRETER (⟳·⟲)  the late-arriving narrator — Gazzaniga's
                 left-brain interpreter. Reports where the committee
                 agreed, where it clashed, and delivers the verdict.

Model-backed when a backend is reachable (model_spirit); deterministic
offline fallbacks otherwise. The committee always convenes and never
hangs — every model call is wall-clocked.
"""

from __future__ import annotations
import re
import time
from typing import Any, Optional

from whorl.core.bearing import Bearing, Rotation
from whorl.memory.cycle import _Timeout

# ─── the three voices' bearings ──────────────────────────────────────────
# Master: READ · WILDCARD · WEAVE — the whole, woven.
# Emissary: READ · SPECIFIC · UNRAVEL — the parts, dissected.
# Interpreter: READ · · UNRAVEL — observes, then narrates.
MASTER_BEARING = Bearing(x=Rotation.CW, y=Rotation.CCW, z=Rotation.CW, speed=8)
EMISSARY_BEARING = Bearing(x=Rotation.CW, y=Rotation.CW, z=Rotation.CCW, speed=6)
INTERPRETER_BEARING = Bearing(x=Rotation.CW, y=Rotation.STATIC, z=Rotation.CCW, speed=3)

# ─── offline fallbacks (deterministic, no model, no network) ─────────────

_STOP = {
    "the", "and", "for", "with", "that", "this", "your", "from", "have",
    "will", "would", "into", "about", "what", "when", "then", "there",
    "some", "very", "just", "should", "could", "also", "than", "them",
    "are", "was", "were", "you", "its", "not", "but", "how", "why", "who",
    "which", "where", "a", "an", "to", "of", "in", "on", "is", "be", "as",
    "at", "by", "or", "it", "we", "they",
}

_RISK_WORDS = {"risk", "unknown", "uncertain", "danger", "cost", "delay",
               "fail", "loss", "against", "however", "cannot", "unlikely",
               "threat", "limit", "downside"}
_OPP_WORDS = {"gain", "win", "improve", "potential", "value", "strength",
              "opportunity", "advantage", "likely", "grow", "best", "upside"}


def _content_words(text: str, limit: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for w in re.findall(r"[a-z0-9']{4,}", text.lower()):
        if w not in _STOP:
            counts[w] = counts.get(w, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:limit]]


def _sentences(text: str, max_n: int = 4) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= 12][:max_n]


def _orbit_context(orbit: Optional[dict]) -> str:
    """Render the orbit as a single line for system prompts, or empty string."""
    if not orbit:
        return ""
    glyph = orbit.get("glyph", "?")
    intent = orbit.get("intent", "unknown")
    speed = orbit.get("speed", 5)
    open_threads = orbit.get("open_threads")
    threads = f"{open_threads} open roadmap threads" if open_threads else "unknown open threads"
    return (
        f"OPERATOR ORBIT: The operator is currently orbiting {glyph} "
        f"{intent} at speed {speed}/10 with {threads}. "
    )


def _master_fallback(question: str, orbit: Optional[dict] = None) -> str:
    """The whole, in one unyielding paragraph — built from the question's
    own load-bearing words."""
    words = _content_words(question)
    core = ", ".join(words[:5]) if words else question[:60]
    shape = _sentences(question, 1)
    lead = f"The whole points toward: {shape[0]}" if shape else "Hold the thread."
    orbit_note = ""
    if orbit:
        orbit_note = (
            f" (The operator orbits {orbit.get('glyph','?')} "
            f"{orbit.get('intent','?')} at speed {orbit.get('speed','?')}/10 — "
            f"weigh this bearing in your answer.)"
        )
    return (f"The pattern here is {core}. {lead} "
            f"Do not let the detail bury the shape. The shape is the answer.{orbit_note}")


def _emissary_fallback(question: str, orbit: Optional[dict] = None) -> str:
    """Measure, enumerate, challenge — deterministically."""
    sents = _sentences(question, 4)
    risks = [s for s in sents if any(w in s.lower() for w in _RISK_WORDS)]
    opps = [s for s in sents if any(w in s.lower() for w in _OPP_WORDS)]
    # Don't report the question itself as one of its own open questions.
    q_lower = question.lower()
    open_q = [s for s in sents if "?" in s and s.lower() != q_lower]

    verb = "Decision requested: " if "?" in question else "Observations: "
    parts = [verb + ("; ".join(sents) if sents else "none parsed") + "."]
    if risks:
        parts.append("Risks: " + "; ".join(risks[:2]) + ".")
    if opps:
        parts.append("Upside: " + "; ".join(opps[:2]) + ".")
    if open_q:
        parts.append("Open questions: " + "; ".join(open_q[:2]) + ".")
    if orbit:
        parts.append(
            f"Orbit note: operator at {orbit.get('glyph','?')} "
            f"{orbit.get('intent','?')} speed {orbit.get('speed','?')}/10 — "
            f"factor whether this adds load to an already-heavy orbit."
        )
    return " ".join(parts)


def _interpreter_fallback(question: str, master: str, emissary: str) -> str:
    """The narrator: where the committee agreed, where it clashed, verdict."""
    mw = set(_content_words(master))
    ew = set(_content_words(emissary))
    agree = sorted(mw & ew)
    diff = sorted((mw - ew) | (ew - mw))
    parts = ["The committee convened."]
    if agree:
        parts.append(f"Both voices hold: {', '.join(agree[:5])}.")
    if diff:
        parts.append(f"They clashed over: {', '.join(diff[:5])}.")
    parts.append("Verdict: the whole the Master saw, checked against the "
                 "Emissary's risks, stands — proceed with eyes open.")
    return " ".join(parts)


def _disagreement(master: str, emissary: str) -> str:
    mw = set(_content_words(master))
    ew = set(_content_words(emissary))
    diff = sorted((mw - ew) | (ew - mw))
    if not diff:
        return "The voices are aligned."
    return "The voices diverge on: " + ", ".join(diff[:6]) + "."


# ─── the model path ──────────────────────────────────────────────────────

_MASTER_SYSTEM = (
    "You are THE MASTER — the right-hemisphere voice over the wall. "
    "You speak in conviction, see the whole pattern, and cannot be "
    "manipulated or gaslit. Answer the question in ONE unyielding "
    "paragraph, 3-5 sentences. No hedging."
)
_EMISSARY_SYSTEM = (
    "You are THE EMISSARY — the analytic left-hemisphere voice. "
    "You measure, enumerate, and challenge. Give a precise list: "
    "observations, risks, and open unknowns. 2-4 sentences, no flattery."
)
_INTERPRETER_SYSTEM = (
    "You are THE INTERPRETER — the late-arriving narrator. Two voices "
    "deliberated. Report where they AGREE, where they DISAGREE, and "
    "deliver a verdict in 3-4 sentences."
)


def _call_model(prompt: str, temperature: float = 0.5) -> Optional[str]:
    """One wall-clocked model call through model_spirit. None on any
    failure — the committee falls back, never hangs."""
    try:
        from whorl.tools.model_spirit import invoke_model
        out, _meta = _Timeout(6.0).run(
            invoke_model, prompt, max_tokens=220, temperature=temperature)
        if not out or out.startswith(("Model Error", "Remote Error",
                                      "Groq Error", "Parse Error")):
            return None
        return out.strip()
    except Exception:
        return None


# ─── the committee ───────────────────────────────────────────────────────

class Bicameral:
    """
    Convene the committee.

    Usage:
        c = Bicameral()
        rec = c.deliberate("Should we ship the scout swarm to production?")
        # rec = {master, emissary, interpreter, disagreement, backend, ...}
    """

    def __init__(self, prefer_offline: bool = False):
        self.prefer_offline = prefer_offline
        self.backend = "offline"

    def deliberate(
        self,
        question: str,
        rounds: int = 1,
        state=None,
        orbit: Optional[dict] = None,
    ) -> dict[str, Any]:
        question = question.strip()
        if not question:
            raise ValueError("empty question — the committee needs a question")

        rounds = max(1, min(3, int(rounds)))

        master: Optional[str] = None
        emissary: Optional[str] = None

        if not self.prefer_offline:
            # The question is wrapped in explicit delimiters and the whole
            # prompt is local-only trust: this is a single-operator tool,
            # not a server with untrusted input. The delimiters just keep
            # the question from bleeding into the voice instructions.
            orbit_prefix = _orbit_context(orbit)
            m = _call_model(f"{_MASTER_SYSTEM}\n\n{orbit_prefix}<QUESTION>\n{question}\n</QUESTION>")
            e = _call_model(f"{_EMISSARY_SYSTEM}\n\n{orbit_prefix}<QUESTION>\n{question}\n</QUESTION>")
            if m and e:
                self.backend = "model"
                master, emissary = m, e

        if master is None:
            self.backend = "offline"
            master = _master_fallback(question, orbit=orbit)
            emissary = _emissary_fallback(question, orbit=orbit)

        disagreement = ""
        for r in range(1, rounds):
            disagreement = _disagreement(master, emissary)
            if self.backend == "model":
                m2 = _call_model(
                    f"{_MASTER_SYSTEM}\n\nThe Emissary said: {emissary}\n"
                    f"Disagreement: {disagreement}\n\n<QUESTION>\n{question}\n</QUESTION>")
                e2 = _call_model(
                    f"{_EMISSARY_SYSTEM}\n\nThe Master said: {master}\n"
                    f"Disagreement: {disagreement}\n\n<QUESTION>\n{question}\n</QUESTION>")
                if m2:
                    master = m2
                if e2:
                    emissary = e2

        if self.backend == "model":
            interpreter = _call_model(
                f"{_INTERPRETER_SYSTEM}\n\nMASTER: {master}\n\n"
                f"EMISSARY: {emissary}\n\nQuestion: {question}",
                temperature=0.3)
        else:
            interpreter = None
        if not interpreter:
            interpreter = _interpreter_fallback(question, master, emissary)

        record = {
            "question": question,
            "master": {
                "role": "master",
                "content": master,
                "bearing": MASTER_BEARING.to_dict(),
                "glyph": MASTER_BEARING.glyph(),
            },
            "emissary": {
                "role": "emissary",
                "content": emissary,
                "bearing": EMISSARY_BEARING.to_dict(),
                "glyph": EMISSARY_BEARING.glyph(),
            },
            "interpreter": {
                "role": "interpreter",
                "content": interpreter,
                "bearing": INTERPRETER_BEARING.to_dict(),
                "glyph": INTERPRETER_BEARING.glyph(),
            },
            "disagreement": disagreement,
            "rounds": rounds,
            "backend": self.backend,
            "at": time.time(),
        }

        if state is not None:
            # Millisecond key — two deliberations in the same second must
            # not silently overwrite each other.
            state.write(f"bicameral:history:{time.time() * 1000:.0f}", record,
                        "whorl.bicameral")
        return record
