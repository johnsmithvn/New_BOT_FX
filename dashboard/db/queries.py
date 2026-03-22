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

    # ── Write Operations (Data Management) ───────────────────────

    def _connect_rw(self) -> sqlite3.Connection:
        """Create a read-write connection (for delete/clear operations)."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _execute_rw(self, sql: str, params: tuple = ()) -> int:
        """Execute a write query and return rowcount."""
        conn = self._connect_rw()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ── Signal Lifecycle Queries ──────────────────────────────────

    def get_signals_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        channel: str | None = None,
        symbol: str | None = None,
        status: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        """Get signals with aggregated order/trade stats, paginated."""
        conditions: list[str] = []
        params: list[Any] = []

        if channel:
            conditions.append("s.source_chat_id = ?")
            params.append(channel)
        if symbol:
            conditions.append("s.symbol = ?")
            params.append(symbol)
        if status:
            conditions.append("s.status = ?")
            params.append(status)
        if from_date:
            conditions.append("date(s.created_at) >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("date(s.created_at) <= ?")
            params.append(to_date)

        where = (" AND " + " AND ".join(conditions)) if conditions else ""

        conn = self._connect()
        try:
            # Total count
            row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM signals s WHERE 1=1{where}",
                tuple(params),
            ).fetchone()
            total = row["cnt"] if row else 0

            # Paginated with aggregated stats
            offset = (page - 1) * per_page
            query_params = tuple(params) + (per_page, offset)
            rows = conn.execute(
                f"""
                SELECT s.*,
                       COALESCE(o_stats.order_count, 0) as order_count,
                       COALESCE(o_stats.success_count, 0) as success_count,
                       COALESCE(t_stats.trade_count, 0) as trade_count,
                       COALESCE(t_stats.total_pnl, 0.0) as total_pnl
                FROM signals s
                LEFT JOIN (
                    SELECT
                        CASE
                            WHEN instr(fingerprint, ':') > 0
                                THEN substr(fingerprint, 1, instr(fingerprint, ':') - 1)
                            ELSE fingerprint
                        END AS base_fp,
                        COUNT(*) as order_count,
                        SUM(success) as success_count
                    FROM orders
                    GROUP BY base_fp
                ) o_stats ON o_stats.base_fp = s.fingerprint
                LEFT JOIN (
                    SELECT
                        CASE
                            WHEN instr(fingerprint, ':') > 0
                                THEN substr(fingerprint, 1, instr(fingerprint, ':') - 1)
                            ELSE fingerprint
                        END AS base_fp,
                        COUNT(*) as trade_count,
                        SUM(pnl) as total_pnl
                    FROM trades
                    GROUP BY base_fp
                ) t_stats ON t_stats.base_fp = s.fingerprint
                WHERE 1=1{where}
                ORDER BY s.id DESC
                LIMIT ? OFFSET ?
                """,
                query_params,
            ).fetchall()

            signals = []
            for r in rows:
                d = dict(r)
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
        except sqlite3.OperationalError:
            return {"signals": [], "total": 0, "page": page, "per_page": per_page}
        finally:
            conn.close()

    def get_signal_lifecycle(self, fingerprint: str) -> dict | None:
        """Get full lifecycle: signal + orders + trades + events + group."""
        conn = self._connect()
        try:
            # Signal
            sig = conn.execute(
                "SELECT * FROM signals WHERE fingerprint = ? ORDER BY id DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
            if not sig:
                return None
            signal = dict(sig)
            try:
                signal["tp"] = json.loads(signal["tp"]) if signal.get("tp") else []
            except (json.JSONDecodeError, TypeError):
                signal["tp"] = []

            # Orders (including sub-fingerprints like fp:L0, fp:L1)
            order_rows = conn.execute(
                """SELECT * FROM orders
                   WHERE fingerprint = ? OR fingerprint LIKE ?
                   ORDER BY id""",
                (fingerprint, f"{fingerprint}:%"),
            ).fetchall()
            orders = [dict(r) for r in order_rows]

            # Trades
            trade_rows = conn.execute(
                """SELECT * FROM trades
                   WHERE fingerprint = ? OR fingerprint LIKE ?
                   ORDER BY close_time""",
                (fingerprint, f"{fingerprint}:%"),
            ).fetchall()
            trades = [dict(r) for r in trade_rows]

            # Events
            event_rows = conn.execute(
                "SELECT * FROM events WHERE fingerprint = ? ORDER BY timestamp",
                (fingerprint,),
            ).fetchall()
            events = []
            for r in event_rows:
                e = dict(r)
                try:
                    e["details"] = json.loads(e["details"]) if e.get("details") else {}
                except (json.JSONDecodeError, TypeError):
                    e["details"] = {}
                events.append(e)

            # Signal group
            group = None
            try:
                g_row = conn.execute(
                    "SELECT * FROM signal_groups WHERE fingerprint = ?",
                    (fingerprint,),
                ).fetchone()
                if g_row:
                    group = dict(g_row)
                    try:
                        group["tickets"] = json.loads(group["tickets"])
                    except (json.JSONDecodeError, TypeError):
                        group["tickets"] = []
                    try:
                        raw = json.loads(group["entry_prices"])
                        group["entry_prices"] = {int(k): v for k, v in raw.items()}
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
        finally:
            conn.close()

    # ── Delete Operations ────────────────────────────────────────

    def delete_signal_cascade(self, fingerprint: str) -> dict[str, int]:
        """Delete signal + ALL related data (orders, trades, events, groups)."""
        conn = self._connect_rw()
        counts: dict[str, int] = {}
        fp_pattern = f"{fingerprint}:%"
        try:
            for table in ["trades", "orders", "events"]:
                c = conn.execute(
                    f"DELETE FROM {table} WHERE fingerprint = ? OR fingerprint LIKE ?",
                    (fingerprint, fp_pattern),
                )
                counts[table] = c.rowcount

            for table in ["signal_groups", "active_signals"]:
                try:
                    c = conn.execute(
                        f"DELETE FROM {table} WHERE fingerprint = ?",
                        (fingerprint,),
                    )
                    counts[table] = c.rowcount
                except sqlite3.OperationalError:
                    counts[table] = 0

            c = conn.execute(
                "DELETE FROM signals WHERE fingerprint = ?",
                (fingerprint,),
            )
            counts["signals"] = c.rowcount

            conn.commit()
            return counts
        finally:
            conn.close()

    def delete_order_by_id(self, order_id: int) -> dict[str, int]:
        """Delete a single order + related trades by ticket."""
        conn = self._connect_rw()
        try:
            row = conn.execute(
                "SELECT ticket FROM orders WHERE id = ?", (order_id,),
            ).fetchone()

            trades_deleted = 0
            if row and row["ticket"]:
                c = conn.execute(
                    "DELETE FROM trades WHERE ticket = ?", (row["ticket"],),
                )
                trades_deleted = c.rowcount

            c = conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            conn.commit()
            return {"orders": c.rowcount, "trades": trades_deleted}
        finally:
            conn.close()

    def delete_trade_by_id(self, trade_id: int) -> int:
        """Delete a single trade by ID."""
        return self._execute_rw(
            "DELETE FROM trades WHERE id = ?", (trade_id,),
        )

    # ── Data Management ──────────────────────────────────────────

    _CLEARABLE = [
        "signals", "orders", "events", "trades",
        "active_signals", "signal_groups", "tracker_state",
    ]

    def clear_table(self, table: str) -> int:
        """Clear all rows from a table."""
        if table not in self._CLEARABLE:
            raise ValueError(f"Cannot clear table: {table}")
        return self._execute_rw(f"DELETE FROM {table}")

    def clear_all_data(self) -> dict[str, int]:
        """Clear all data (except schema_versions)."""
        conn = self._connect_rw()
        counts: dict[str, int] = {}
        try:
            for table in self._CLEARABLE:
                try:
                    c = conn.execute(f"DELETE FROM {table}")
                    counts[table] = c.rowcount
                except sqlite3.OperationalError:
                    counts[table] = 0
            conn.commit()
            return counts
        finally:
            conn.close()

    def get_table_counts(self) -> dict[str, int]:
        """Get row counts for all data tables."""
        counts: dict[str, int] = {}
        conn = self._connect()
        try:
            for table in self._CLEARABLE + ["schema_versions"]:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*) as cnt FROM {table}",
                    ).fetchone()
                    counts[table] = row["cnt"] if row else 0
                except sqlite3.OperationalError:
                    counts[table] = 0
            return counts
        finally:
            conn.close()

    def get_signal_status_counts(self) -> dict:
        """Get signal counts grouped by status (for Overview breakdown)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM signals GROUP BY status"
            ).fetchall()
            total = 0
            by_status: dict[str, int] = {}
            for row in rows:
                by_status[row["status"]] = row["cnt"]
                total += row["cnt"]
            by_status["total"] = total
            return by_status
        finally:
            conn.close()
