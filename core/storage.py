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
import time
from datetime import datetime, timezone
from pathlib import Path

from core.models import ParsedSignal, SignalStatus
from utils.logger import log_event


_DEFAULT_DB_PATH = "data/bot.db"
_MAX_RETRIES = 3
_RETRY_DELAY = 0.5

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
        # Enable WAL mode for better concurrent access
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def _execute_with_retry(self, sql: str, params=(), commit: bool = True):
        """Execute SQL with retry on database locked errors."""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                cursor = self._conn.execute(sql, params)
                if commit:
                    self._conn.commit()
                return cursor
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc) and attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * attempt)
                    continue
                raise

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ── Signals ──────────────────────────────────────────────────

    def store_signal(self, signal: ParsedSignal, status: SignalStatus) -> int:
        """Persist a parsed signal record.

        Returns the row ID of the inserted record.
        """
        cursor = self._execute_with_retry(
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
        return cursor.lastrowid

    def update_signal_status(
        self, fingerprint: str, status: SignalStatus
    ) -> None:
        """Update signal status by fingerprint."""
        self._execute_with_retry(
            "UPDATE signals SET status = ? WHERE fingerprint = ?",
            (status.value, fingerprint),
        )

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
        cursor = self._execute_with_retry(
            """
            INSERT INTO orders
                (ticket, fingerprint, order_kind, price, sl, tp,
                 retcode, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket, fingerprint, order_kind, price, sl, tp,
             retcode, int(success)),
        )
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
        cursor = self._execute_with_retry(
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
        return cursor.lastrowid

    # ── Cleanup ──────────────────────────────────────────────────

    def cleanup_old_records(self, retention_days: int = 30) -> dict:
        """Delete records older than retention_days.

        Returns dict with counts of deleted rows per table.
        """
        cutoff = f"-{retention_days} days"
        counts = {}

        for table, col in [("signals", "created_at"), ("orders", "created_at"), ("events", "timestamp")]:
            cursor = self._execute_with_retry(
                f"DELETE FROM {table} WHERE datetime({col}) < datetime('now', ?)",
                (cutoff,),
            )
            counts[table] = cursor.rowcount

        log_event(
            "storage_cleanup",
            retention_days=retention_days,
            deleted_signals=counts.get("signals", 0),
            deleted_orders=counts.get("orders", 0),
            deleted_events=counts.get("events", 0),
        )
        return counts
