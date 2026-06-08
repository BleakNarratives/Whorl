"""
whorl.scouts
────────────
Intel feed ingestion. Consumes structured SCOUT FIELD RECON REPORT
text blocks or RSS/JSON feeds and writes Signal objects to the DB.

Extend by adding parsers to PARSERS dict below.
"""

from __future__ import annotations
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from whorl.core import config, db
from whorl.core.models import Signal, SignalClass


# ── Parsers ────────────────────────────────────────────────────────────────

def _parse_recon_block(text: str) -> Optional[Signal]:
    """
    Parse the SCOUT FIELD RECON REPORT text format.
    Returns None if the block doesn't match.
    """
    if "SCOUT FIELD RECON REPORT" not in text:
        return None

    def _field(label: str) -> str:
        m = re.search(rf"{label}:\s*(.+)", text)
        return m.group(1).strip() if m else ""

    headline = _field("Target Event")
    source   = _field("Source Feed")
    action   = _field("Action")
    region   = _field("Region") or "GLOBAL"

    # Rough signal classification from headline keywords
    kw = headline.lower()
    if any(w in kw for w in ["strike", "port", "shipping", "supply"]):
        cls = SignalClass.SUPPLY_CHAIN
    elif any(w in kw for w in ["foreclosure", "property", "listing", "real estate"]):
        cls = SignalClass.REAL_ESTATE
    elif any(w in kw for w in ["boycott", "semiconductor", "chip"]):
        cls = SignalClass.GEOPOLITICAL
    else:
        cls = SignalClass.ECONOMIC

    return Signal(
        id           = str(uuid.uuid4()),
        timestamp    = datetime.now(timezone.utc).isoformat(),
        source       = source,
        region       = region,
        signal_class = cls,
        headline     = headline,
        body         = text.strip(),
        action       = action,
    )


def _parse_distressed_block(text: str) -> Optional[Signal]:
    """
    Parse the distressed property leads format.
    e.g. [2026-06-02T16:38:01...] REGION: ... INTEL: ... FIELD ORDER: ...
    """
    blocks = re.findall(
        r"\[(.+?)\]\s+REGION:\s*(.+?)\n\s*INTEL:\s*(.+?)\n\s*FIELD ORDER:\s*(.+?)(?=\[|\Z)",
        text, re.DOTALL
    )
    signals = []
    for ts, region, intel, order in blocks:
        signals.append(Signal(
            id           = str(uuid.uuid4()),
            timestamp    = ts.strip(),
            source       = "distressed_property_feed",
            region       = region.strip(),
            signal_class = SignalClass.REAL_ESTATE,
            headline     = intel.strip(),
            body         = intel.strip(),
            action       = order.strip(),
        ))
    return signals[0] if signals else None  # return first; caller can iterate


# ── Public API ─────────────────────────────────────────────────────────────

PARSERS = [
    _parse_recon_block,
    _parse_distressed_block,
]


def ingest_text(raw: str) -> List[Signal]:
    """Try each parser against raw text. Persist matches to DB."""
    found = []
    for parser in PARSERS:
        sig = parser(raw)
        if sig:
            _persist(sig)
            found.append(sig)
    return found


def _persist(sig: Signal) -> None:
    db.insert("signals", {
        "id":           sig.id,
        "timestamp":    sig.timestamp,
        "source":       sig.source,
        "region":       sig.region,
        "signal_class": sig.signal_class.value,
        "headline":     sig.headline,
        "body":         sig.body,
        "action":       sig.action,
        "verified":     int(sig.verified),
        "metadata":     sig.metadata,
    })


def list_signals(limit: int = 20) -> List[dict]:
    return db.fetch("signals", limit=limit)


def run_sweep() -> None:
    """
    Entry point for `whorl scout run`.
    Extend to pull from configured RSS/HTTP feeds.
    """
    cfg = config.cfg()
    feeds = cfg.scout_feeds

    if not feeds:
        print("[scouts] No feeds configured. Add feeds to ~/.whorl/config.toml")
        return

    # Placeholder: iterate feeds, fetch, parse
    for feed_url in feeds:
        print(f"[scouts] Sweeping {feed_url} ...")
        # TODO: fetch feed, parse entries, call ingest_text()

    recent = list_signals(limit=5)
    print(f"[scouts] {len(recent)} recent signals in DB.")
