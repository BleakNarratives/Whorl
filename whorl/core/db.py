"""
whorl.core.db
─────────────
SQLite layer. One DB, all modules.
Schema is versioned — safe to run migrations repeatedly.
"""

from __future__ import annotations
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from . import config as _cfg_module

_MIGRATIONS: List[str] = [
    # v1 — core tables
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version  INTEGER PRIMARY KEY,
        applied  TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS signals (
        id           TEXT PRIMARY KEY,
        timestamp    TEXT NOT NULL,
        source       TEXT,
        region       TEXT,
        signal_class TEXT,
        headline     TEXT,
        body         TEXT,
        action       TEXT,
        verified     INTEGER DEFAULT 0,
        metadata     TEXT DEFAULT '{}'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS pitches (
        id        TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        target    TEXT,
        vertical  TEXT,
        situation TEXT,
        risk      TEXT,
        fix       TEXT,
        ask       TEXT,
        hook      TEXT,
        cost      TEXT,
        guarantee TEXT,
        raw       TEXT,
        metadata  TEXT DEFAULT '{}'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS hotseat_sessions (
        id        TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        topic     TEXT,
        audrey    TEXT,
        claib     TEXT,
        vertical  TEXT,
        score     REAL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS qrds (
        id        TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        source_id TEXT,
        blink     TEXT,
        brief     TEXT,
        deep      TEXT,
        full      TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS agents (
        id       TEXT PRIMARY KEY,
        name     TEXT NOT NULL,
        vertical TEXT,
        state    TEXT DEFAULT 'idle',
        bearing  TEXT DEFAULT '{}',
        metadata TEXT DEFAULT '{}'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS nostr_events (
        id        TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        kind      INTEGER,
        pubkey    TEXT,
        content   TEXT,
        tags      TEXT DEFAULT '[]',
        relayed   INTEGER DEFAULT 0
    );
    """,
]

_CURRENT_VERSION = len(_MIGRATIONS)


def _db_path() -> Path:
    return _cfg_module.DB_PATH


@contextmanager
def connect() -> Generator[sqlite3.Connection, None, None]:
    """Context manager — auto-commits on exit, rolls back on error."""
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def migrate() -> None:
    """Run pending migrations. Safe to call on every startup."""
    _cfg_module.WHORL_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        conn.execute(_MIGRATIONS[0])   # schema_version must exist first
        applied = conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        ).fetchone()["v"] or 0

        for i, sql in enumerate(_MIGRATIONS[1:], start=1):
            if i > applied:
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied) VALUES (?, datetime('now'))",
                    (i,)
                )


# ── Generic helpers ────────────────────────────────────────────────────────

def insert(table: str, row: Dict[str, Any]) -> None:
    """Insert a dict as a row. JSON-encodes any dict/list values."""
    encoded = {
        k: json.dumps(v) if isinstance(v, (dict, list)) else v
        for k, v in row.items()
    }
    cols   = ", ".join(encoded.keys())
    placeholders = ", ".join("?" for _ in encoded)
    with connect() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
            list(encoded.values()),
        )


def fetch(table: str, where: str = "", params: tuple = (),
          limit: int = 50) -> List[Dict]:
    clause = f"WHERE {where}" if where else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM {table} {clause} ORDER BY rowid DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def count(table: str, where: str = "", params: tuple = ()) -> int:
    clause = f"WHERE {where}" if where else ""
    with connect() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} {clause}", params
        ).fetchone()[0]
