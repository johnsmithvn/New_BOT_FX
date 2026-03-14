"""
core/storage.py

SQLite persistence for:
- Signal fingerprints (dedupe window).
- Order audit trail.
- Runtime event records.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.models import ParsedSignal, SignalStatus


_DEFAULT_DB_PATH = "data/bot.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,
    entry           REAL,
    sl              REAL,
    tp              TEXT,          -- JSON array of floats
    status          TEXT NOT NULL DEFAULT 'received',
    raw_text        TEXT,
    source_chat_id  TEXT,
    source_message_id TEXT,
    received_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_fingerprint ON signals(fingerprint);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket          INTEGER,
    fingerprint     TEXT NOT NULL,
    order_kind      TEXT NOT NULL,
    price           REAL,
    sl              REAL,
    tp              REAL,
    retcode         INTEGER,
    success         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_fingerprint ON orders(fingerprint);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    symbol          TEXT,
    details         TEXT,          -- JSON blob
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_fingerprint ON events(fingerprint);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
"""


class Storage:
    """SQLite storage for signal lifecycle persistence."""

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ── Signals ──────────────────────────────────────────────────

    def store_signal(self, signal: ParsedSignal, status: SignalStatus) -> int:
        """Persist a parsed signal record.

        Returns the row ID of the inserted record.
        """
        cursor = self._conn.execute(
            """
            INSERT INTO signals
                (fingerprint, symbol, side, entry, sl, tp, status,
                 raw_text, source_chat_id, source_message_id, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.fingerprint,
                signal.symbol,
                signal.side.value,
                signal.entry,
                signal.sl,
                json.dumps(signal.tp),
                status.value,
                signal.raw_text,
                signal.source_chat_id,
                signal.source_message_id,
                signal.received_at.isoformat(),
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update_signal_status(
        self, fingerprint: str, status: SignalStatus
    ) -> None:
        """Update signal status by fingerprint."""
        self._conn.execute(
            "UPDATE signals SET status = ? WHERE fingerprint = ?",
            (status.value, fingerprint),
        )
        self._conn.commit()

    def is_duplicate(self, fingerprint: str, ttl_seconds: int = 300) -> bool:
        """Check if a signal with the same fingerprint exists within TTL.

        Args:
            fingerprint: Signal fingerprint to check.
            ttl_seconds: Time window in seconds for duplicate suppression.

        Returns:
            True if duplicate found within window.
        """
        row = self._conn.execute(
            """
            SELECT COUNT(*) as cnt FROM signals
            WHERE fingerprint = ?
              AND datetime(created_at) > datetime('now', ?)
            """,
            (fingerprint, f"-{ttl_seconds} seconds"),
        ).fetchone()
        return row["cnt"] > 0

    # ── Orders ───────────────────────────────────────────────────

    def store_order(
        self,
        ticket: int | None,
        fingerprint: str,
        order_kind: str,
        price: float | None,
        sl: float | None,
        tp: float | None,
        retcode: int,
        success: bool,
    ) -> int:
        """Persist an order execution record."""
        cursor = self._conn.execute(
            """
            INSERT INTO orders
                (ticket, fingerprint, order_kind, price, sl, tp,
                 retcode, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket, fingerprint, order_kind, price, sl, tp,
             retcode, int(success)),
        )
        self._conn.commit()
        return cursor.lastrowid

    # ── Events ───────────────────────────────────────────────────

    def store_event(
        self,
        fingerprint: str,
        event_type: str,
        symbol: str = "",
        details: dict | None = None,
    ) -> int:
        """Persist a runtime event for signal lifecycle tracing."""
        cursor = self._conn.execute(
            """
            INSERT INTO events (fingerprint, event_type, symbol, details)
            VALUES (?, ?, ?, ?)
            """,
            (
                fingerprint,
                event_type,
                symbol,
                json.dumps(details) if details else None,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid
