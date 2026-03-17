"""
core/storage.py

SQLite persistence for:
- Signal fingerprints (dedupe window).
- Order audit trail.
- Runtime event records.
- Trade outcome tracking (v0.6.0).
- Tracker state (background worker persistence).

Schema evolution uses a versioned migration system.
Migrations are idempotent — safe for repeated restarts.
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

CREATE TABLE IF NOT EXISTS schema_versions (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# ── Versioned Migrations ─────────────────────────────────────────
# Each migration runs exactly once. The version number is stored in
# schema_versions after successful execution. Safe for repeated restarts.

_MIGRATIONS: dict[int, str] = {
    1: """
        -- V1: Multi-channel support columns
        ALTER TABLE orders ADD COLUMN channel_id TEXT;
        ALTER TABLE orders ADD COLUMN source_chat_id TEXT;
        ALTER TABLE orders ADD COLUMN source_message_id TEXT;
        ALTER TABLE orders ADD COLUMN position_ticket INTEGER;
        ALTER TABLE events ADD COLUMN channel_id TEXT;

        CREATE INDEX IF NOT EXISTS idx_signals_channel
            ON signals(source_chat_id);
        CREATE INDEX IF NOT EXISTS idx_orders_channel
            ON orders(channel_id);
        CREATE INDEX IF NOT EXISTS idx_orders_position
            ON orders(position_ticket);
        CREATE INDEX IF NOT EXISTS idx_events_channel
            ON events(channel_id);
    """,
    2: """
        -- V2: Trade outcome tracking + tracker state
        CREATE TABLE IF NOT EXISTS trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket          INTEGER NOT NULL,
            deal_ticket     INTEGER NOT NULL UNIQUE,
            fingerprint     TEXT NOT NULL,
            channel_id      TEXT NOT NULL,
            source_chat_id  TEXT,
            source_message_id TEXT,
            close_volume    REAL NOT NULL,
            close_price     REAL NOT NULL,
            close_time      TEXT NOT NULL,
            pnl             REAL NOT NULL,
            commission      REAL DEFAULT 0.0,
            swap            REAL DEFAULT 0.0,
            close_reason    TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_trades_ticket
            ON trades(ticket);
        CREATE INDEX IF NOT EXISTS idx_trades_channel
            ON trades(channel_id);
        CREATE INDEX IF NOT EXISTS idx_trades_time
            ON trades(close_time);

        CREATE TABLE IF NOT EXISTS tracker_state (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """,
}


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
        """Create base tables and apply pending migrations."""
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()
        self._apply_migrations()

    def _apply_migrations(self) -> None:
        """Apply pending versioned migrations.

        Checks schema_versions to skip already-applied migrations.
        Each migration runs in a transaction for atomicity.
        """
        applied = set()
        try:
            rows = self._conn.execute(
                "SELECT version FROM schema_versions"
            ).fetchall()
            applied = {row["version"] for row in rows}
        except sqlite3.OperationalError:
            # Table might not exist on very first run before _SCHEMA_SQL
            pass

        for version in sorted(_MIGRATIONS.keys()):
            if version in applied:
                continue
            try:
                self._conn.executescript(_MIGRATIONS[version])
                self._conn.execute(
                    "INSERT INTO schema_versions (version) VALUES (?)",
                    (version,),
                )
                self._conn.commit()
                log_event(
                    "schema_migration_applied",
                    version=version,
                )
            except sqlite3.OperationalError as exc:
                # Handle "duplicate column" if migration partially ran before
                if "duplicate column" in str(exc).lower():
                    self._conn.execute(
                        "INSERT OR IGNORE INTO schema_versions (version) VALUES (?)",
                        (version,),
                    )
                    self._conn.commit()
                    log_event(
                        "schema_migration_skipped",
                        version=version,
                        reason=str(exc),
                    )
                else:
                    raise

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
        channel_id: str = "",
        source_chat_id: str = "",
        source_message_id: str = "",
    ) -> int:
        """Persist an order execution record.

        Args:
            channel_id: Source channel identifier (denormalized).
            source_chat_id: Telegram chat ID for reply threading.
            source_message_id: Telegram message ID for reply threading.
        """
        cursor = self._execute_with_retry(
            """
            INSERT INTO orders
                (ticket, fingerprint, order_kind, price, sl, tp,
                 retcode, success, channel_id, source_chat_id,
                 source_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket, fingerprint, order_kind, price, sl, tp,
             retcode, int(success), channel_id, source_chat_id,
             source_message_id),
        )
        return cursor.lastrowid

    def update_position_ticket(
        self, order_ticket: int, position_ticket: int,
    ) -> None:
        """Update position_ticket when a pending order fills.

        For MARKET orders, order_ticket == position_ticket.
        For pending orders, MT5 creates a new position_ticket on fill.
        """
        self._execute_with_retry(
            "UPDATE orders SET position_ticket = ? WHERE ticket = ?",
            (position_ticket, order_ticket),
        )

    def get_order_by_ticket(self, ticket: int) -> dict | None:
        """Lookup order by MT5 ticket (direct match)."""
        row = self._conn.execute(
            "SELECT * FROM orders WHERE ticket = ? AND success = 1",
            (ticket,),
        ).fetchone()
        return dict(row) if row else None

    def get_order_by_position_ticket(self, position_ticket: int) -> dict | None:
        """Lookup order by position_ticket (filled pending orders)."""
        row = self._conn.execute(
            "SELECT * FROM orders WHERE position_ticket = ? AND success = 1",
            (position_ticket,),
        ).fetchone()
        return dict(row) if row else None

    def get_open_tickets(self) -> dict[int, str]:
        """Return {ticket: channel_id} for all successful orders.

        Used by PositionManager to rebuild ticket→channel cache on startup.
        """
        rows = self._conn.execute(
            "SELECT ticket, channel_id FROM orders WHERE success = 1 AND ticket IS NOT NULL",
        ).fetchall()
        return {row["ticket"]: (row["channel_id"] or "") for row in rows}

    def get_fingerprint_by_message(
        self, source_chat_id: str, source_message_id: str,
    ) -> str | None:
        """Lookup fingerprint by original message coordinates.

        Used by _process_edit to find the original signal before
        comparing fingerprints on edited messages.
        """
        row = self._conn.execute(
            """SELECT fingerprint FROM signals
               WHERE source_chat_id = ? AND source_message_id = ?
               ORDER BY id DESC LIMIT 1""",
            (source_chat_id, source_message_id),
        ).fetchone()
        return row["fingerprint"] if row else None

    def get_orders_by_message(
        self, source_chat_id: str, source_message_id: str,
    ) -> list[dict]:
        """Get ALL orders associated with a signal message.

        Joins signals → orders via fingerprint to get ticket, symbol,
        channel_id, and success status. Returns list of dicts.
        Used by reply handler to act on all orders from a signal.
        """
        rows = self._conn.execute(
            """SELECT o.ticket, s.symbol, o.fingerprint,
                      o.channel_id, o.success
               FROM orders o
               JOIN signals s ON o.fingerprint = s.fingerprint
               WHERE s.source_chat_id = ? AND s.source_message_id = ?
                 AND o.ticket IS NOT NULL
               ORDER BY o.id""",
            (source_chat_id, source_message_id),
        ).fetchall()
        return [
            {
                "ticket": row["ticket"],
                "symbol": row["symbol"],
                "fingerprint": row["fingerprint"],
                "channel_id": row["channel_id"] or "",
                "success": bool(row["success"]),
            }
            for row in rows
        ]

    # ── Events ───────────────────────────────────────────────────

    def store_event(
        self,
        fingerprint: str,
        event_type: str,
        symbol: str = "",
        details: dict | None = None,
        channel_id: str = "",
    ) -> int:
        """Persist a runtime event for signal lifecycle tracing."""
        cursor = self._execute_with_retry(
            """
            INSERT INTO events (fingerprint, event_type, symbol, details,
                                channel_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                fingerprint,
                event_type,
                symbol,
                json.dumps(details) if details else None,
                channel_id,
            ),
        )
        return cursor.lastrowid

    # ── Trades ────────────────────────────────────────────────────

    def store_trade(
        self,
        ticket: int,
        deal_ticket: int,
        fingerprint: str,
        channel_id: str,
        close_volume: float,
        close_price: float,
        close_time: str,
        pnl: float,
        commission: float = 0.0,
        swap: float = 0.0,
        close_reason: str = "",
        source_chat_id: str = "",
        source_message_id: str = "",
    ) -> int | None:
        """Persist a trade outcome (closing deal).

        Returns row ID on success, None if deal_ticket already exists.
        """
        try:
            cursor = self._execute_with_retry(
                """
                INSERT INTO trades
                    (ticket, deal_ticket, fingerprint, channel_id,
                     close_volume, close_price, close_time, pnl,
                     commission, swap, close_reason,
                     source_chat_id, source_message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket, deal_ticket, fingerprint, channel_id,
                    close_volume, close_price, close_time, pnl,
                    commission, swap, close_reason,
                    source_chat_id, source_message_id,
                ),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # deal_ticket UNIQUE constraint — already processed
            return None

    def get_signal_reply_info(
        self, fingerprint: str,
    ) -> tuple[str, str] | None:
        """Get (source_chat_id, source_message_id) for Telegram reply."""
        row = self._conn.execute(
            "SELECT source_chat_id, source_message_id FROM signals WHERE fingerprint = ? LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if row:
            return (row["source_chat_id"] or "", row["source_message_id"] or "")
        return None

    # ── Tracker State ─────────────────────────────────────────────

    def get_tracker_state(self, key: str) -> str | None:
        """Read a tracker state value."""
        row = self._conn.execute(
            "SELECT value FROM tracker_state WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    def set_tracker_state(self, key: str, value: str) -> None:
        """Write a tracker state value (upsert)."""
        self._execute_with_retry(
            """
            INSERT INTO tracker_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    # ── Cleanup ──────────────────────────────────────────────────

    def cleanup_old_records(self, retention_days: int = 30) -> dict:
        """Delete records older than retention_days.

        Returns dict with counts of deleted rows per table.
        """
        cutoff = f"-{retention_days} days"
        counts = {}

        tables = [
            ("signals", "created_at"),
            ("orders", "created_at"),
            ("events", "timestamp"),
            ("trades", "created_at"),
        ]
        for table, col in tables:
            try:
                cursor = self._execute_with_retry(
                    f"DELETE FROM {table} WHERE datetime({col}) < datetime('now', ?)",
                    (cutoff,),
                )
                counts[table] = cursor.rowcount
            except sqlite3.OperationalError:
                # Table may not exist if migrations haven't run yet
                counts[table] = 0

        log_event(
            "storage_cleanup",
            retention_days=retention_days,
            deleted_signals=counts.get("signals", 0),
            deleted_orders=counts.get("orders", 0),
            deleted_events=counts.get("events", 0),
            deleted_trades=counts.get("trades", 0),
        )
        return counts
