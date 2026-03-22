"""
dashboard/api/routes.py

FastAPI API endpoints for the analytics dashboard.
All endpoints are read-only and return JSON.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from dashboard.db.queries import DashboardDB

router = APIRouter(prefix="/api")

# Dependency: DB instance is injected via app state
_db: DashboardDB | None = None
_channel_names: dict[str, str] = {}


def set_db(db: DashboardDB) -> None:
    """Set the database instance (called from app startup)."""
    global _db
    _db = db


def load_channel_names(config_path: str | Path) -> None:
    """Load channel ID → name mapping from channels.json."""
    global _channel_names
    path = Path(config_path)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        channels = data.get("channels", {})
        _channel_names = {
            cid: cfg.get("name", cid) for cid, cfg in channels.items()
        }
    except (json.JSONDecodeError, AttributeError):
        _channel_names = {}


def _resolve_name(channel_id: str) -> str:
    """Resolve channel ID to human name."""
    return _channel_names.get(channel_id, channel_id or "Unknown")


def _inject_names(rows: list[dict], key: str = "channel_id") -> list[dict]:
    """Add channel_name field to each row."""
    for row in rows:
        row["channel_name"] = _resolve_name(row.get(key, ""))
    return rows


def get_db() -> DashboardDB:
    """FastAPI dependency for database access."""
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# ── Overview ─────────────────────────────────────────────────────


@router.get("/overview")
def api_overview(db: DashboardDB = Depends(get_db)) -> dict:
    """Get high-level summary statistics."""
    return db.get_overview()


@router.get("/daily-pnl")
def api_daily_pnl(
    days: int = Query(default=30, ge=1, le=365),
    db: DashboardDB = Depends(get_db),
) -> list[dict]:
    """Get daily PnL for the last N days."""
    return db.get_daily_pnl(days)


# ── Channel Performance ─────────────────────────────────────────


@router.get("/channels")
def api_channels(db: DashboardDB = Depends(get_db)) -> list[dict]:
    """Get per-channel performance summary with names."""
    return _inject_names(db.get_channel_stats())


@router.get("/channels/{channel_id}/daily-pnl")
def api_channel_daily_pnl(
    channel_id: str,
    days: int = Query(default=30, ge=1, le=365),
    db: DashboardDB = Depends(get_db),
) -> list[dict]:
    """Get daily PnL for a specific channel."""
    return db.get_channel_daily_pnl(channel_id, days)


# ── Trade History ────────────────────────────────────────────────


@router.get("/trades")
def api_trades(
    channel: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    outcome: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: DashboardDB = Depends(get_db),
) -> dict:
    """Get paginated trade history with filters."""
    result = db.get_trades(
        channel_id=channel,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        outcome=outcome,
        page=page,
        per_page=per_page,
    )
    _inject_names(result["trades"])
    return result


# ── Active Positions ─────────────────────────────────────────────


@router.get("/active")
def api_active(db: DashboardDB = Depends(get_db)) -> list[dict]:
    """Get currently active signal groups."""
    return _inject_names(db.get_active_groups())


# ── Equity Curve (P12) ──────────────────────────────────────────


@router.get("/equity-curve")
def api_equity_curve(
    days: int = Query(default=365, ge=1, le=3650),
    db: DashboardDB = Depends(get_db),
) -> list[dict]:
    """Get cumulative PnL for equity curve chart."""
    return db.get_equity_curve(days)


# ── Symbol Stats (P12) ──────────────────────────────────────────


@router.get("/symbol-stats")
def api_symbol_stats(db: DashboardDB = Depends(get_db)) -> list[dict]:
    """Get per-symbol performance (win rate, PnL, count)."""
    return db.get_symbol_stats()


# ── CSV Export (P12) ─────────────────────────────────────────────


@router.get("/export/csv")
def api_export_csv(
    channel: str | None = Query(default=None),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    db: DashboardDB = Depends(get_db),
) -> StreamingResponse:
    """Export all trades as CSV file."""
    trades = db.get_all_trades_for_export(
        channel_id=channel,
        from_date=from_date,
        to_date=to_date,
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "close_time", "symbol", "side", "entry_price",
            "close_price", "volume", "pnl", "commission",
            "swap", "net_pnl", "channel_id", "channel_name",
            "close_reason", "ticket",
        ],
    )
    writer.writeheader()
    for trade in trades:
        trade["channel_name"] = _resolve_name(trade.get("channel_id", ""))
        writer.writerow(trade)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades_export.csv"},
    )


# ── Metadata ─────────────────────────────────────────────────────


@router.get("/symbols")
def api_symbols(db: DashboardDB = Depends(get_db)) -> list[str]:
    """Get all unique traded symbols."""
    return db.get_symbols()


@router.get("/channel-list")
def api_channel_list(db: DashboardDB = Depends(get_db)) -> list[dict]:
    """Get all unique channel IDs with names."""
    channels = db.get_channels()
    return [{"id": ch, "name": _resolve_name(ch)} for ch in channels]
