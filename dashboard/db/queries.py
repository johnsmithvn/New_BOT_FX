"""
dashboard/db/queries.py

Read-only SQL aggregation queries for the analytics dashboard.
Connects to the bot's SQLite database in read-only mode.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class DashboardDB:
    """Read-only database access for dashboard analytics.

    Opens SQLite in WAL mode with read-only URI to prevent
    any accidental writes from the dashboard process.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        if not self._db_path.exists():
            raise FileNotFoundError(f"Database not found: {self._db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Create a read-only connection."""
        uri = f"file:{self._db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a read-only query and return list of dicts."""
        conn = self._connect()
        try:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                return []
            raise
        finally:
            conn.close()

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Execute a query and return single result."""
        conn = self._connect()
        try:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()

    # ── Overview ─────────────────────────────────────────────────

    def get_overview(self) -> dict[str, Any]:
        """Get high-level summary statistics."""
        stats = self._query_one("""
            SELECT
                COUNT(*)                                    AS total_trades,
                COALESCE(SUM(pnl), 0)                      AS total_pnl,
                COALESCE(SUM(commission), 0)                AS total_commission,
                COALESCE(SUM(swap), 0)                      AS total_swap,
                COALESCE(SUM(pnl) + SUM(commission) + SUM(swap), 0) AS net_pnl,
                COALESCE(AVG(pnl), 0)                      AS avg_pnl,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)   AS wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END)  AS losses,
                MAX(close_time)                             AS last_trade_time
            FROM trades
        """) or {}

        total = stats.get("total_trades", 0)
        wins = stats.get("wins", 0)
        stats["win_rate"] = round((wins / total * 100), 1) if total > 0 else 0.0

        # Active groups
        active = self._query_one("""
            SELECT COUNT(*) AS active_groups
            FROM signal_groups
            WHERE status = 'active'
        """)
        stats["active_groups"] = active["active_groups"] if active else 0

        # Total signals
        signals = self._query_one("""
            SELECT COUNT(*) AS total_signals FROM signals
        """)
        stats["total_signals"] = signals["total_signals"] if signals else 0

        return stats

    # ── Daily PnL ────────────────────────────────────────────────

    def get_daily_pnl(self, days: int = 30) -> list[dict]:
        """Get daily PnL for the last N days."""
        return self._query("""
            SELECT
                DATE(close_time) AS date,
                SUM(pnl)         AS pnl,
                SUM(pnl + COALESCE(commission, 0) + COALESCE(swap, 0)) AS net_pnl,
                COUNT(*)         AS trades
            FROM trades
            WHERE DATE(close_time) >= DATE('now', ? || ' days')
            GROUP BY DATE(close_time)
            ORDER BY DATE(close_time)
        """, (f"-{days}",))

    # ── Channel Performance ──────────────────────────────────────

    def get_channel_stats(self) -> list[dict]:
        """Get per-channel performance summary."""
        return self._query("""
            SELECT
                channel_id,
                COUNT(*)                                    AS total_trades,
                SUM(pnl)                                    AS total_pnl,
                SUM(pnl + COALESCE(commission, 0) + COALESCE(swap, 0)) AS net_pnl,
                AVG(pnl)                                    AS avg_pnl,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)   AS wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END)  AS losses,
                MAX(close_time)                             AS last_trade,
                MIN(close_time)                             AS first_trade
            FROM trades
            GROUP BY channel_id
            ORDER BY SUM(pnl) DESC
        """)

    def get_channel_daily_pnl(
        self, channel_id: str, days: int = 30
    ) -> list[dict]:
        """Get daily PnL for a specific channel."""
        return self._query("""
            SELECT
                DATE(close_time) AS date,
                SUM(pnl)         AS pnl,
                COUNT(*)         AS trades
            FROM trades
            WHERE channel_id = ?
              AND DATE(close_time) >= DATE('now', ? || ' days')
            GROUP BY DATE(close_time)
            ORDER BY DATE(close_time)
        """, (channel_id, f"-{days}"))

    # ── Trade History ────────────────────────────────────────────

    def get_trades(
        self,
        channel_id: str | None = None,
        symbol: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        outcome: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """Get paginated trade history with filters.

        Returns:
            {"trades": [...], "total": N, "page": N, "per_page": N}
        """
        conditions = []
        params: list = []

        if channel_id:
            conditions.append("t.channel_id = ?")
            params.append(channel_id)
        if symbol:
            conditions.append("s.symbol LIKE ?")
            params.append(f"%{symbol}%")
        if from_date:
            conditions.append("DATE(t.close_time) >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("DATE(t.close_time) <= ?")
            params.append(to_date)
        if outcome == "win":
            conditions.append("t.pnl > 0")
        elif outcome == "loss":
            conditions.append("t.pnl <= 0")

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * per_page

        # Total count
        count_sql = f"""
            SELECT COUNT(*) AS total
            FROM trades t
            LEFT JOIN signals s ON t.fingerprint = s.fingerprint
            {where}
        """
        total_row = self._query_one(count_sql, tuple(params))
        total = total_row["total"] if total_row else 0

        # Summary
        summary_sql = f"""
            SELECT
                COALESCE(SUM(t.pnl), 0) AS total_pnl,
                COALESCE(AVG(t.pnl), 0) AS avg_pnl
            FROM trades t
            LEFT JOIN signals s ON t.fingerprint = s.fingerprint
            {where}
        """
        summary = self._query_one(summary_sql, tuple(params)) or {}

        # Paginated data
        data_sql = f"""
            SELECT
                t.ticket,
                t.fingerprint,
                t.channel_id,
                t.close_time,
                t.close_price,
                t.close_volume,
                t.pnl,
                t.commission,
                t.swap,
                t.close_reason,
                s.symbol,
                s.side,
                s.entry AS entry_price
            FROM trades t
            LEFT JOIN signals s ON t.fingerprint = s.fingerprint
            {where}
            ORDER BY t.close_time DESC
            LIMIT ? OFFSET ?
        """
        params.extend([per_page, offset])
        trades = self._query(data_sql, tuple(params))

        return {
            "trades": trades,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pnl": round(summary.get("total_pnl", 0), 2),
            "avg_pnl": round(summary.get("avg_pnl", 0), 2),
        }

    # ── Active Positions ─────────────────────────────────────────

    def get_active_groups(self) -> list[dict]:
        """Get currently active signal groups."""
        rows = self._query("""
            SELECT
                fingerprint,
                symbol,
                side,
                channel_id,
                tickets,
                entry_prices,
                current_group_sl,
                sl_mode,
                created_at
            FROM signal_groups
            WHERE status = 'active'
            ORDER BY created_at DESC
        """)

        # Parse JSON fields
        for row in rows:
            try:
                row["tickets"] = json.loads(row.get("tickets", "[]"))
            except (json.JSONDecodeError, TypeError):
                row["tickets"] = []
            try:
                row["entry_prices"] = json.loads(row.get("entry_prices", "{}"))
            except (json.JSONDecodeError, TypeError):
                row["entry_prices"] = {}

        return rows

    # ── Symbols ──────────────────────────────────────────────────

    def get_symbols(self) -> list[str]:
        """Get all unique traded symbols."""
        rows = self._query("""
            SELECT DISTINCT symbol FROM signals
            WHERE symbol IS NOT NULL AND symbol != ''
            ORDER BY symbol
        """)
        return [r["symbol"] for r in rows]

    def get_channels(self) -> list[str]:
        """Get all unique channel IDs from trades."""
        rows = self._query("""
            SELECT DISTINCT channel_id FROM trades
            WHERE channel_id IS NOT NULL AND channel_id != ''
            ORDER BY channel_id
        """)
        return [r["channel_id"] for r in rows]

    # ── Equity Curve (P12) ───────────────────────────────────────

    def get_equity_curve(self, days: int = 365) -> list[dict]:
        """Get cumulative PnL over time for equity curve chart."""
        return self._query("""
            SELECT
                DATE(close_time) AS date,
                SUM(pnl + COALESCE(commission, 0) + COALESCE(swap, 0)) AS daily_net,
                SUM(SUM(pnl + COALESCE(commission, 0) + COALESCE(swap, 0)))
                    OVER (ORDER BY DATE(close_time)) AS cumulative_pnl,
                COUNT(*) AS trades
            FROM trades
            WHERE DATE(close_time) >= DATE('now', ? || ' days')
            GROUP BY DATE(close_time)
            ORDER BY DATE(close_time)
        """, (f"-{days}",))

    # ── Symbol Stats (P12) ───────────────────────────────────────

    def get_symbol_stats(self) -> list[dict]:
        """Get per-symbol performance: win rate, PnL, trade count."""
        return self._query("""
            SELECT
                s.symbol,
                COUNT(*)                                    AS total_trades,
                SUM(t.pnl)                                  AS total_pnl,
                AVG(t.pnl)                                  AS avg_pnl,
                SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN t.pnl <= 0 THEN 1 ELSE 0 END) AS losses,
                ROUND(
                    CAST(SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS REAL)
                    / COUNT(*) * 100, 1
                )                                           AS win_rate
            FROM trades t
            LEFT JOIN signals s ON t.fingerprint = s.fingerprint
            WHERE s.symbol IS NOT NULL AND s.symbol != ''
            GROUP BY s.symbol
            ORDER BY SUM(t.pnl) DESC
        """)

    # ── All Trades (CSV) ─────────────────────────────────────────

    def get_all_trades_for_export(
        self,
        channel_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        """Get ALL trades (no pagination) for CSV export."""
        conditions = []
        params: list = []

        if channel_id:
            conditions.append("t.channel_id = ?")
            params.append(channel_id)
        if from_date:
            conditions.append("DATE(t.close_time) >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("DATE(t.close_time) <= ?")
            params.append(to_date)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        return self._query(f"""
            SELECT
                t.close_time,
                s.symbol,
                s.side,
                s.entry AS entry_price,
                t.close_price,
                t.close_volume AS volume,
                t.pnl,
                t.commission,
                t.swap,
                t.pnl + COALESCE(t.commission, 0) + COALESCE(t.swap, 0) AS net_pnl,
                t.channel_id,
                t.close_reason,
                t.ticket
            FROM trades t
            LEFT JOIN signals s ON t.fingerprint = s.fingerprint
            {where}
            ORDER BY t.close_time DESC
        """, tuple(params))

