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
from datetime import datetime
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
    3: """
        -- V3: Active signal tracking for multi-order strategies (P9)
        CREATE TABLE IF NOT EXISTS active_signals (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint       TEXT NOT NULL UNIQUE,
            symbol            TEXT NOT NULL,
            side              TEXT NOT NULL,
            entry_range       TEXT,
            sl                REAL,
            tp                TEXT,
            source_chat_id    TEXT,
            source_message_id TEXT,
            channel_id        TEXT,
            entry_plans       TEXT,
            total_volume      REAL,
            status            TEXT NOT NULL DEFAULT 'pending',
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at        TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_active_signals_status
            ON active_signals(status);
        CREATE INDEX IF NOT EXISTS idx_active_signals_fp
            ON active_signals(fingerprint);

        -- Add source_message_id index on orders for P9 reply handler
        CREATE INDEX IF NOT EXISTS idx_orders_source_msg
            ON orders(source_chat_id, source_message_id);
    """,
    4: """
        -- V4: Signal groups for P10 group management
        CREATE TABLE IF NOT EXISTS signal_groups (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint           TEXT NOT NULL UNIQUE,
            symbol                TEXT NOT NULL,
            side                  TEXT NOT NULL,
            channel_id            TEXT NOT NULL,
            source_message_id     TEXT,
            zone_low              REAL,
            zone_high             REAL,
            signal_sl             REAL,
            signal_tp             TEXT,          -- JSON array
            tickets               TEXT NOT NULL, -- JSON array of ints
            entry_prices          TEXT NOT NULL, -- JSON {ticket: price}
            sl_mode               TEXT NOT NULL DEFAULT 'signal',
            sl_max_pips_from_zone REAL DEFAULT 50.0,
            group_trailing_pips   REAL DEFAULT 0.0,
            group_be_on_partial   INTEGER DEFAULT 0,
            reply_close_strategy  TEXT DEFAULT 'all',
            current_group_sl      REAL,
            status                TEXT NOT NULL DEFAULT 'active',
            created_at            TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_signal_groups_status
            ON signal_groups(status);
        CREATE INDEX IF NOT EXISTS idx_signal_groups_channel
            ON signal_groups(channel_id);
    """,
    5: """
        -- V5: Add symbol column to orders (fixes reply-command lookup)
        ALTER TABLE orders ADD COLUMN symbol TEXT;
    """,
    6: """
        -- V6: Peak profit tracking per group and per trade
        ALTER TABLE signal_groups ADD COLUMN peak_pips REAL;
        ALTER TABLE signal_groups ADD COLUMN peak_price REAL;
        ALTER TABLE signal_groups ADD COLUMN peak_time TEXT;
        ALTER TABLE trades ADD COLUMN peak_pips REAL;
        ALTER TABLE trades ADD COLUMN peak_price REAL;
        ALTER TABLE trades ADD COLUMN peak_time TEXT;
        ALTER TABLE trades ADD COLUMN entry_price REAL;
    """,
    7: """
        -- V7: Market snapshot at order entry (bid/ask/spread + volume)
        ALTER TABLE orders ADD COLUMN volume REAL;
        ALTER TABLE orders ADD COLUMN bid REAL;
        ALTER TABLE orders ADD COLUMN ask REAL;
    """,
}


class Storage:
    """SQLite storage for signal lifecycle persistence."""

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
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
        symbol: str = "",
        volume: float | None = None,
        bid: float | None = None,
        ask: float | None = None,
    ) -> int:
        """Persist an order execution record.

        Args:
            channel_id: Source channel identifier (denormalized).
            source_chat_id: Telegram chat ID for reply threading.
            source_message_id: Telegram message ID for reply threading.
            symbol: Trading symbol (e.g. XAUUSD).
            volume: Lot size executed.
            bid: Market bid price at order time.
            ask: Market ask price at order time.
        """
        cursor = self._execute_with_retry(
            """
            INSERT INTO orders
                (ticket, fingerprint, order_kind, price, sl, tp,
                 retcode, success, channel_id, source_chat_id,
                 source_message_id, symbol, volume, bid, ask)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket, fingerprint, order_kind, price, sl, tp,
             retcode, int(success), channel_id, source_chat_id,
             source_message_id, symbol, volume, bid, ask),
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

        P9 update: Direct query on orders table via source_chat_id +
        source_message_id. No longer joins through signals.fingerprint,
        because re-entry orders use sub-fingerprints (e.g. fp:L0, fp:L1)
        that won't match the signal's base fingerprint.

        Falls back to old JOIN path for orders that pre-date V3 migration
        (orders without source_message_id).
        """
        # Primary path (P9): direct lookup on orders table
        rows = self._conn.execute(
            """SELECT ticket, symbol, fingerprint, channel_id, success
               FROM orders
               WHERE source_chat_id = ? AND source_message_id = ?
                 AND ticket IS NOT NULL
               ORDER BY id""",
            (source_chat_id, source_message_id),
        ).fetchall()

        if not rows:
            # Fallback: old JOIN through signals table (pre-P9 orders)
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
        entry_price: float | None = None,
        peak_pips: float | None = None,
        peak_price: float | None = None,
        peak_time: str | None = None,
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
                     source_chat_id, source_message_id,
                     entry_price, peak_pips, peak_price, peak_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket, deal_ticket, fingerprint, channel_id,
                    close_volume, close_price, close_time, pnl,
                    commission, swap, close_reason,
                    source_chat_id, source_message_id,
                    entry_price, peak_pips, peak_price, peak_time,
                ),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # deal_ticket UNIQUE constraint — already processed
            return None

    def update_group_peak(
        self,
        fingerprint: str,
        peak_pips: float,
        peak_price: float,
        peak_time: str,
    ) -> None:
        """Update peak profit data for a signal group."""
        self._execute_with_retry(
            """
            UPDATE signal_groups
            SET peak_pips = ?, peak_price = ?, peak_time = ?
            WHERE fingerprint = ?
            """,
            (peak_pips, peak_price, peak_time, fingerprint),
        )
        self._conn.commit()

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

    # ── Active Signals (P9) ────────────────────────────────────────

    def store_active_signal(
        self,
        fingerprint: str,
        symbol: str,
        side: str,
        entry_range: list[float] | None,
        sl: float | None,
        tp: list[float],
        source_chat_id: str,
        source_message_id: str,
        channel_id: str,
        entry_plans_json: str,
        total_volume: float,
        expires_at: str,
    ) -> int:
        """Persist an active signal for restart recovery."""
        cursor = self._execute_with_retry(
            """
            INSERT OR REPLACE INTO active_signals
                (fingerprint, symbol, side, entry_range, sl, tp,
                 source_chat_id, source_message_id, channel_id,
                 entry_plans, total_volume, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fingerprint, symbol, side,
                json.dumps(entry_range) if entry_range else None,
                sl,
                json.dumps(tp),
                source_chat_id, source_message_id, channel_id,
                entry_plans_json, total_volume, expires_at,
            ),
        )
        return cursor.lastrowid

    def get_active_signals(self, status: str = "pending") -> list[dict]:
        """Get all active signals with given status.

        Returns raw dicts — caller (SignalStateManager) deserializes.
        Includes both 'pending' and 'partial' by default for rebuild.
        """
        rows = self._conn.execute(
            """SELECT * FROM active_signals
               WHERE status IN ('pending', 'partial')
               ORDER BY created_at""",
        ).fetchall()
        return [dict(row) for row in rows]

    def update_active_signal_status(
        self, fingerprint: str, status: str,
    ) -> None:
        """Update the status of an active signal."""
        self._execute_with_retry(
            "UPDATE active_signals SET status = ? WHERE fingerprint = ?",
            (status, fingerprint),
        )

    def update_active_signal_plans(
        self, fingerprint: str, entry_plans_json: str,
    ) -> None:
        """Update entry plans JSON (after marking levels executed/cancelled)."""
        self._execute_with_retry(
            "UPDATE active_signals SET entry_plans = ? WHERE fingerprint = ?",
            (entry_plans_json, fingerprint),
        )

    def delete_active_signal(self, fingerprint: str) -> None:
        """Remove an active signal (completed or expired)."""
        self._execute_with_retry(
            "DELETE FROM active_signals WHERE fingerprint = ?",
            (fingerprint,),
        )

    # ── P10: Signal Group Persistence ──────────────────────────────

    def store_group(
        self,
        fingerprint: str,
        symbol: str,
        side: str,
        channel_id: str,
        source_message_id: str,
        tickets: list[int],
        entry_prices: dict[int, float],
        zone_low: float | None = None,
        zone_high: float | None = None,
        signal_sl: float | None = None,
        signal_tp: list[float] | None = None,
        sl_mode: str = "signal",
        sl_max_pips_from_zone: float = 50.0,
        group_trailing_pips: float = 0.0,
        group_be_on_partial: bool = False,
        reply_close_strategy: str = "all",
    ) -> None:
        """Persist a signal group to DB for restart recovery."""
        self._execute_with_retry(
            """INSERT OR REPLACE INTO signal_groups (
                fingerprint, symbol, side, channel_id, source_message_id,
                zone_low, zone_high, signal_sl, signal_tp,
                tickets, entry_prices,
                sl_mode, sl_max_pips_from_zone, group_trailing_pips,
                group_be_on_partial, reply_close_strategy,
                status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', datetime('now'))""",
            (
                fingerprint, symbol, side, channel_id, source_message_id,
                zone_low, zone_high, signal_sl,
                json.dumps(signal_tp) if signal_tp else None,
                json.dumps(tickets),
                json.dumps({str(k): v for k, v in entry_prices.items()}),
                sl_mode, sl_max_pips_from_zone, group_trailing_pips,
                1 if group_be_on_partial else 0,
                reply_close_strategy,
            ),
        )

    def get_active_groups(self) -> list[dict]:
        """Get all active signal groups for restart recovery.

        Returns list of dicts with parsed JSON fields.
        """
        try:
            cursor = self._execute_with_retry(
                "SELECT * FROM signal_groups WHERE status = 'active'"
            )
            rows = cursor.fetchall()
        except Exception:
            return []

        groups = []
        for row in rows:
            row_dict = dict(row)
            # Parse JSON fields
            try:
                row_dict["tickets"] = json.loads(row_dict["tickets"])
            except (json.JSONDecodeError, TypeError):
                row_dict["tickets"] = []
            try:
                raw_prices = json.loads(row_dict["entry_prices"])
                row_dict["entry_prices"] = {int(k): v for k, v in raw_prices.items()}
            except (json.JSONDecodeError, TypeError):
                row_dict["entry_prices"] = {}
            try:
                tp = row_dict.get("signal_tp")
                row_dict["signal_tp"] = json.loads(tp) if tp else []
            except (json.JSONDecodeError, TypeError):
                row_dict["signal_tp"] = []
            row_dict["group_be_on_partial"] = bool(row_dict.get("group_be_on_partial", 0))
            groups.append(row_dict)

        return groups

    def update_group_sl(self, fingerprint: str, new_sl: float) -> None:
        """Update the current SL for a signal group."""
        self._execute_with_retry(
            """UPDATE signal_groups
               SET current_group_sl = ?, updated_at = datetime('now')
               WHERE fingerprint = ?""",
            (new_sl, fingerprint),
        )

    def update_group_tickets(
        self, fingerprint: str, tickets: list[int], entry_prices: dict[int, float],
    ) -> None:
        """Update tickets and entry_prices after re-entry adds order."""
        self._execute_with_retry(
            """UPDATE signal_groups
               SET tickets = ?, entry_prices = ?, updated_at = datetime('now')
               WHERE fingerprint = ?""",
            (
                json.dumps(tickets),
                json.dumps({str(k): v for k, v in entry_prices.items()}),
                fingerprint,
            ),
        )

    def complete_group_db(self, fingerprint: str) -> None:
        """Mark a signal group as completed in DB."""
        self._execute_with_retry(
            """UPDATE signal_groups
               SET status = 'completed', updated_at = datetime('now')
               WHERE fingerprint = ?""",
            (fingerprint,),
        )

    def reactivate_group_db(self, fingerprint: str) -> None:
        """Mark a signal group as active in DB (resurrection on re-entry)."""
        self._execute_with_retry(
            """UPDATE signal_groups
               SET status = 'active', updated_at = datetime('now')
               WHERE fingerprint = ?""",
            (fingerprint,),
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
            ("active_signals", "created_at"),
            ("signal_groups", "created_at"),
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

    # ── Signal Lifecycle Queries (Dashboard V2) ─────────────────

    def get_signals_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        channel: str = "",
        symbol: str = "",
        status: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> dict:
        """Get signals with aggregated order/trade stats, paginated.

        Returns {signals: [...], total: int, page: int, per_page: int}.
        """
        where_clauses = []
        params: list = []

        if channel:
            where_clauses.append("s.source_chat_id = ?")
            params.append(channel)
        if symbol:
            where_clauses.append("s.symbol = ?")
            params.append(symbol)
        if status:
            where_clauses.append("s.status = ?")
            params.append(status)
        if date_from:
            where_clauses.append("date(s.created_at) >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("date(s.created_at) <= ?")
            params.append(date_to)

        where_sql = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""

        # Count total
        count_row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM signals s WHERE 1=1{where_sql}",
            params,
        ).fetchone()
        total = count_row["cnt"] if count_row else 0

        # Query signals with aggregated stats
        offset = (page - 1) * per_page
        query_params = params + [per_page, offset]
        rows = self._conn.execute(
            f"""
            SELECT s.*,
                   COALESCE(o_stats.order_count, 0) as order_count,
                   COALESCE(o_stats.success_count, 0) as success_count,
                   COALESCE(t_stats.trade_count, 0) as trade_count,
                   COALESCE(t_stats.total_pnl, 0.0) as total_pnl
            FROM signals s
            LEFT JOIN (
                SELECT fingerprint,
                       COUNT(*) as order_count,
                       SUM(success) as success_count
                FROM orders
                GROUP BY fingerprint
            ) o_stats ON s.fingerprint = o_stats.fingerprint
            LEFT JOIN (
                SELECT fingerprint,
                       COUNT(*) as trade_count,
                       SUM(pnl) as total_pnl
                FROM trades
                GROUP BY fingerprint
            ) t_stats ON s.fingerprint = t_stats.fingerprint
            WHERE 1=1{where_sql}
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?
            """,
            query_params,
        ).fetchall()

        signals = []
        for row in rows:
            d = dict(row)
            # Parse tp JSON
            try:
                d["tp"] = json.loads(d["tp"]) if d.get("tp") else []
            except (json.JSONDecodeError, TypeError):
                d["tp"] = []
            signals.append(d)

        return {
            "signals": signals,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def get_signal_lifecycle(self, fingerprint: str) -> dict | None:
        """Get full lifecycle for a signal: signal + orders + trades + events + group.

        Returns None if signal not found.
        """
        # Signal
        sig_row = self._conn.execute(
            "SELECT * FROM signals WHERE fingerprint = ? ORDER BY id DESC LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if not sig_row:
            return None
        signal = dict(sig_row)
        try:
            signal["tp"] = json.loads(signal["tp"]) if signal.get("tp") else []
        except (json.JSONDecodeError, TypeError):
            signal["tp"] = []

        # Orders
        order_rows = self._conn.execute(
            "SELECT * FROM orders WHERE fingerprint = ? ORDER BY id",
            (fingerprint,),
        ).fetchall()
        # Also check sub-fingerprints (e.g. fp:L0, fp:L1)
        sub_order_rows = self._conn.execute(
            "SELECT * FROM orders WHERE fingerprint LIKE ? AND fingerprint != ? ORDER BY id",
            (f"{fingerprint}:%", fingerprint),
        ).fetchall()
        orders = [dict(r) for r in order_rows] + [dict(r) for r in sub_order_rows]

        # Trades (join by fingerprint and sub-fingerprints)
        trade_rows = self._conn.execute(
            """SELECT * FROM trades
               WHERE fingerprint = ? OR fingerprint LIKE ?
               ORDER BY close_time""",
            (fingerprint, f"{fingerprint}:%"),
        ).fetchall()
        trades = [dict(r) for r in trade_rows]

        # Events
        event_rows = self._conn.execute(
            "SELECT * FROM events WHERE fingerprint = ? ORDER BY timestamp",
            (fingerprint,),
        ).fetchall()
        events = []
        for row in event_rows:
            e = dict(row)
            try:
                e["details"] = json.loads(e["details"]) if e.get("details") else {}
            except (json.JSONDecodeError, TypeError):
                e["details"] = {}
            events.append(e)

        # Signal group (if exists)
        group = None
        try:
            group_row = self._conn.execute(
                "SELECT * FROM signal_groups WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if group_row:
                group = dict(group_row)
                try:
                    group["tickets"] = json.loads(group["tickets"])
                except (json.JSONDecodeError, TypeError):
                    group["tickets"] = []
                try:
                    raw_prices = json.loads(group["entry_prices"])
                    group["entry_prices"] = {int(k): v for k, v in raw_prices.items()}
                except (json.JSONDecodeError, TypeError):
                    group["entry_prices"] = {}
                try:
                    group["signal_tp"] = json.loads(group["signal_tp"]) if group.get("signal_tp") else []
                except (json.JSONDecodeError, TypeError):
                    group["signal_tp"] = []
        except sqlite3.OperationalError:
            pass

        return {
            "signal": signal,
            "orders": orders,
            "trades": trades,
            "events": events,
            "group": group,
        }

    # ── Cascade & Granular Delete (Dashboard V2) ────────────────

    def delete_signal_cascade(self, fingerprint: str) -> dict:
        """Delete a signal and ALL related data (orders, trades, events, groups).

        Returns counts of deleted rows per table.
        """
        fp_pattern = f"{fingerprint}:%"
        counts = {}

        for table in ["trades", "orders", "events"]:
            cursor = self._execute_with_retry(
                f"DELETE FROM {table} WHERE fingerprint = ? OR fingerprint LIKE ?",
                (fingerprint, fp_pattern),
                commit=False,
            )
            counts[table] = cursor.rowcount

        # Signal groups
        try:
            cursor = self._execute_with_retry(
                "DELETE FROM signal_groups WHERE fingerprint = ?",
                (fingerprint,),
                commit=False,
            )
            counts["signal_groups"] = cursor.rowcount
        except sqlite3.OperationalError:
            counts["signal_groups"] = 0

        # Active signals
        try:
            cursor = self._execute_with_retry(
                "DELETE FROM active_signals WHERE fingerprint = ?",
                (fingerprint,),
                commit=False,
            )
            counts["active_signals"] = cursor.rowcount
        except sqlite3.OperationalError:
            counts["active_signals"] = 0

        # Signal itself
        cursor = self._execute_with_retry(
            "DELETE FROM signals WHERE fingerprint = ?",
            (fingerprint,),
            commit=False,
        )
        counts["signals"] = cursor.rowcount

        self._conn.commit()
        return counts

    def delete_order(self, order_id: int) -> dict:
        """Delete a single order by ID. Also deletes related trades by ticket.

        Returns {orders: int, trades: int}.
        """
        # Get ticket before deleting
        row = self._conn.execute(
            "SELECT ticket FROM orders WHERE id = ?", (order_id,),
        ).fetchone()

        trades_deleted = 0
        if row and row["ticket"]:
            cursor = self._execute_with_retry(
                "DELETE FROM trades WHERE ticket = ?",
                (row["ticket"],),
                commit=False,
            )
            trades_deleted = cursor.rowcount

        cursor = self._execute_with_retry(
            "DELETE FROM orders WHERE id = ?",
            (order_id,),
            commit=False,
        )
        self._conn.commit()
        return {"orders": cursor.rowcount, "trades": trades_deleted}

    def delete_trade(self, trade_id: int) -> int:
        """Delete a single trade by ID. Returns rows deleted."""
        cursor = self._execute_with_retry(
            "DELETE FROM trades WHERE id = ?", (trade_id,),
        )
        return cursor.rowcount

    _CLEARABLE_TABLES = {
        "signals": "created_at",
        "orders": "created_at",
        "events": "timestamp",
        "trades": "created_at",
        "active_signals": "created_at",
        "signal_groups": "created_at",
        "tracker_state": None,
    }

    def clear_table(self, table: str) -> int:
        """Clear all rows from a table. Returns count deleted.

        Raises ValueError for invalid table names.
        """
        if table not in self._CLEARABLE_TABLES:
            raise ValueError(f"Cannot clear table: {table}")
        cursor = self._execute_with_retry(f"DELETE FROM {table}")
        return cursor.rowcount

    def clear_all_data(self) -> dict[str, int]:
        """Clear all data tables (except schema_versions).

        Returns {table: deleted_count}.
        """
        counts = {}
        for table in self._CLEARABLE_TABLES:
            try:
                cursor = self._execute_with_retry(
                    f"DELETE FROM {table}", commit=False,
                )
                counts[table] = cursor.rowcount
            except sqlite3.OperationalError:
                counts[table] = 0
        self._conn.commit()
        return counts

    def get_table_counts(self) -> dict[str, int]:
        """Get row counts for all data tables (for Settings display)."""
        counts = {}
        for table in list(self._CLEARABLE_TABLES) + ["schema_versions"]:
            try:
                row = self._conn.execute(
                    f"SELECT COUNT(*) as cnt FROM {table}",
                ).fetchone()
                counts[table] = row["cnt"] if row else 0
            except sqlite3.OperationalError:
                counts[table] = 0
        return counts

