"""
core/daily_risk_guard.py

Poll-based daily risk guard.

Reads closed deal history from MT5 every N minutes.
Enforces three independent limits:
  - MAX_DAILY_TRADES:       max closed deals per UTC calendar day
  - MAX_DAILY_LOSS:         max total realized loss (USD) per UTC calendar day
  - MAX_CONSECUTIVE_LOSSES: pause after N consecutive losing closed deals

All limits default to 0 = disabled.

Design note:
  P&L and consecutive loss counts are derived from mt5.history_deals_get(),
  NOT from order execution callbacks. This is the only correct approach:
  - Trades may stay open for hours before closing at SL/TP.
  - Execution success != trade closed with profit.
  - Consecutive loss streak is the leading run of (profit < 0) in deal history.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from utils.logger import log_event


def _today_midnight_utc() -> datetime:
    """Return today's midnight UTC as a timezone-aware datetime."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class DailyRiskGuard:
    """Poll-based daily risk limits using MT5 closed deal history.

    Runs a background task that refreshes counters from MT5 every
    ``poll_interval_minutes`` minutes. On the next UTC day boundary,
    counters reset automatically via a separate reset loop.

    Only active in live mode — skipped entirely in dry-run.
    """

    def __init__(
        self,
        max_daily_trades: int = 0,
        max_daily_loss_usd: float = 0.0,
        max_consecutive_losses: int = 0,
        poll_interval_minutes: int = 5,
        on_limit_hit: object = None,  # Callable[[str, str], None] | None
    ) -> None:
        """Args:
            max_daily_trades: Max closed deals per UTC day. 0 = disabled.
            max_daily_loss_usd: Max realized loss (USD) per UTC day. 0.0 = disabled.
            max_consecutive_losses: Max consecutive losing deals. 0 = disabled.
            poll_interval_minutes: How often to refresh counters from MT5.
            on_limit_hit: Optional callback(alert_key, message) when a limit is breached.
        """
        self._max_daily_trades = max_daily_trades
        self._max_daily_loss = max_daily_loss_usd
        self._max_consecutive_losses = max_consecutive_losses
        self._poll_interval = poll_interval_minutes * 60

        self._on_limit_hit = on_limit_hit

        # Polled counters — refreshed from MT5 deal history
        self._daily_trades: int = 0
        self._daily_loss_usd: float = 0.0
        self._consecutive_losses: int = 0

        # Block reason when limits hit — empty = allowed
        self._block_reason: str = ""

        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._reset_task: asyncio.Task | None = None

    # ── Public API ────────────────────────────────────────────────

    @property
    def is_trading_allowed(self) -> tuple[bool, str]:
        """Return (allowed, reason). reason is empty when allowed."""
        if self._block_reason:
            return False, self._block_reason
        return True, ""

    @property
    def daily_stats(self) -> dict:
        """Current day counters for heartbeat / logging."""
        return {
            "daily_trades": self._daily_trades,
            "daily_loss_usd": round(self._daily_loss_usd, 2),
            "consecutive_losses": self._consecutive_losses,
        }

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Start background polling and daily reset loops."""
        self._running = True

        # Initial poll immediately on start
        try:
            self._poll_from_mt5()
        except Exception as exc:
            log_event("daily_risk_guard_poll_error", error=str(exc))

        self._poll_task = asyncio.create_task(self._poll_loop())
        self._reset_task = asyncio.create_task(self._midnight_reset_loop())

        log_event(
            "daily_risk_guard_started",
            max_daily_trades=self._max_daily_trades,
            max_daily_loss_usd=self._max_daily_loss,
            max_consecutive_losses=self._max_consecutive_losses,
            poll_interval_minutes=self._poll_interval // 60,
        )

    async def stop(self) -> None:
        """Stop background loops."""
        self._running = False
        for task in (self._poll_task, self._reset_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        log_event("daily_risk_guard_stopped")

    # ── Background Loops ──────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Refresh counters from MT5 every N minutes."""
        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)
                self._poll_from_mt5()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("daily_risk_guard_poll_error", error=str(exc))

    async def _midnight_reset_loop(self) -> None:
        """Reset daily counters at each UTC midnight."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                # Seconds until next midnight UTC
                seconds_until_midnight = (
                    86400
                    - now.hour * 3600
                    - now.minute * 60
                    - now.second
                )
                await asyncio.sleep(seconds_until_midnight + 1)  # +1s buffer

                if not self._running:
                    break

                self._daily_trades = 0
                self._daily_loss_usd = 0.0
                self._consecutive_losses = 0
                self._block_reason = ""

                log_event("daily_risk_guard_reset", reason="midnight_utc")

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("daily_risk_guard_reset_error", error=str(exc))
                await asyncio.sleep(60)

    # ── MT5 Poll Logic ────────────────────────────────────────────

    def _poll_from_mt5(self) -> None:
        """Read closed deal history from MT5 and update counters.

        Uses mt5.history_deals_get(date_from) to get all deals since
        today's UTC midnight. Computes:
          - daily_trades: count of deal-out entries (closed positions)
          - daily_loss_usd: total realized loss today (sum of negative profits)
          - consecutive_losses: leading streak of losing deals (sorted desc by time)
        """
        try:
            import MetaTrader5 as mt5
        except ImportError:
            log_event("daily_risk_guard_mt5_import_error")
            return

        midnight = _today_midnight_utc()
        deals = mt5.history_deals_get(midnight)

        if deals is None:
            # No deals or MT5 unavailable — normal, no need to log
            self._daily_trades = 0
            self._daily_loss_usd = 0.0
            self._consecutive_losses = 0
            return

        # DEAL_ENTRY_OUT = 1: position close (the deal that books P&L)
        DEAL_ENTRY_OUT = 1
        closing_deals = [d for d in deals if d.entry == DEAL_ENTRY_OUT]

        # Daily trade count
        self._daily_trades = len(closing_deals)

        # Daily realized loss (only sum negative profits = losses)
        self._daily_loss_usd = -sum(
            d.profit for d in closing_deals if d.profit < 0
        )

        # Consecutive losses: sort by time descending, count leading loss streak
        sorted_deals = sorted(closing_deals, key=lambda d: d.time, reverse=True)
        streak = 0
        for deal in sorted_deals:
            if deal.profit < 0:
                streak += 1
            else:
                break  # First profitable deal stops the streak
        self._consecutive_losses = streak

        log_event(
            "daily_risk_guard_polled",
            daily_trades=self._daily_trades,
            daily_loss_usd=round(self._daily_loss_usd, 2),
            consecutive_losses=self._consecutive_losses,
        )

        # Evaluate limits and update block reason
        self._evaluate_limits()

    def _evaluate_limits(self) -> None:
        """Check counters against configured limits. Update block_reason."""
        # Max daily trades
        if self._max_daily_trades > 0 and self._daily_trades >= self._max_daily_trades:
            reason = (
                f"daily trade limit reached ({self._daily_trades}/{self._max_daily_trades})"
            )
            self._set_block(reason, "daily_trades_limit")
            return

        # Max daily loss
        if self._max_daily_loss > 0 and self._daily_loss_usd >= self._max_daily_loss:
            reason = (
                f"daily loss limit reached (${self._daily_loss_usd:.2f}/${self._max_daily_loss:.2f})"
            )
            self._set_block(reason, "daily_loss_limit")
            return

        # Max consecutive losses
        if (
            self._max_consecutive_losses > 0
            and self._consecutive_losses >= self._max_consecutive_losses
        ):
            reason = (
                f"consecutive loss limit reached "
                f"({self._consecutive_losses}/{self._max_consecutive_losses})"
            )
            self._set_block(reason, "consecutive_loss_limit")
            return

        # All clear — unblock if previously blocked
        if self._block_reason:
            log_event("daily_risk_guard_unblocked")
            self._block_reason = ""

    def _set_block(self, reason: str, alert_key: str) -> None:
        """Set block reason and fire alert callback (rate-limited by caller)."""
        is_new_block = not self._block_reason
        self._block_reason = reason

        log_event("daily_risk_guard_blocked", reason=reason)

        # Only fire alert on new block, not every poll cycle
        if is_new_block and self._on_limit_hit:
            try:
                self._on_limit_hit(
                    alert_key,
                    f"⛔ **DAILY RISK LIMIT**\n{reason}\nTrading paused until next UTC day.",
                )
            except Exception as exc:
                log_event("daily_risk_guard_alert_error", error=str(exc))
