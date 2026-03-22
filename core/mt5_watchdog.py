"""
core/mt5_watchdog.py

Periodically verify MT5 connection health.
Trigger reinitialization if connection is lost.
Weekend/market-close aware — suppress false alarms.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from core.trade_executor import TradeExecutor
from utils.logger import log_event


class MT5Watchdog:
    """Monitor MT5 connection health.

    Features:
    - Periodic health check using account_info().
    - Exponential backoff on reinit failures.
    - Weekend detection: suppress false alarms when market closed.
    - Alert callback for critical failures.
    """

    def __init__(
        self,
        executor: TradeExecutor,
        check_interval_seconds: int = 30,
        max_reinit_retries: int = 5,
        reinit_delay_seconds: float = 5.0,
        on_reinit_exhausted=None,
        on_connection_lost=None,
        on_health_update=None,
    ) -> None:
        self._executor = executor
        self._check_interval = check_interval_seconds
        self._max_reinit = max_reinit_retries
        self._base_reinit_delay = reinit_delay_seconds
        self._on_reinit_exhausted = on_reinit_exhausted
        self._on_connection_lost = on_connection_lost
        self._on_health_update = on_health_update
        self._running = False
        self._task: asyncio.Task | None = None
        self._consecutive_failures = 0

    async def start(self) -> None:
        """Start the watchdog monitoring loop."""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        log_event(
            "mt5_watchdog_started",
            check_interval=self._check_interval,
        )

    async def stop(self) -> None:
        """Stop the watchdog monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log_event("mt5_watchdog_stopped")

    @staticmethod
    def _is_market_closed() -> bool:
        """Detect if market is likely closed (weekend).

        Returns True on Saturday (5) and Sunday (6) UTC.
        Note: Forex typically closes Friday 22:00 UTC, reopens Sunday 22:00 UTC.
        This is a conservative check to suppress false alarms.
        """
        now = datetime.now(timezone.utc)
        return now.weekday() in (5, 6)  # Saturday, Sunday

    async def _monitor_loop(self) -> None:
        """Periodically check MT5 health."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                self._health_check()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("mt5_watchdog_error", error=str(exc))

    def _health_check(self) -> None:
        """Run a lightweight health check on MT5."""
        info = self._executor.account_info()

        if info is not None:
            # Connection is healthy
            if self._on_health_update:
                try:
                    self._on_health_update(True)
                except Exception:
                    pass
            if self._consecutive_failures > 0:
                log_event(
                    "mt5_connection_recovered",
                    previous_failures=self._consecutive_failures,
                )
            self._consecutive_failures = 0
            return

        # Health check failed
        if self._on_health_update:
            try:
                self._on_health_update(False)
            except Exception:
                pass
        self._consecutive_failures += 1

        # Suppress false alarms during weekend
        if self._is_market_closed():
            if self._consecutive_failures == 1:
                log_event(
                    "mt5_health_check_weekend",
                    note="Market likely closed, suppressing reinit",
                )
            return

        log_event(
            "mt5_health_check_failed",
            consecutive_failures=self._consecutive_failures,
        )

        # Notify on first failure
        if self._consecutive_failures == 1 and self._on_connection_lost:
            try:
                self._on_connection_lost()
            except Exception:
                pass

        if self._consecutive_failures <= self._max_reinit:
            self._attempt_reinit()
        else:
            log_event(
                "mt5_reinit_exhausted",
                max_retries=self._max_reinit,
            )
            # Alert callback
            if self._on_reinit_exhausted:
                try:
                    self._on_reinit_exhausted()
                except Exception:
                    pass

    def _attempt_reinit(self) -> None:
        """Attempt to reinitialize the MT5 connection with exponential backoff."""
        log_event(
            "mt5_reinit_attempt",
            attempt=self._consecutive_failures,
        )

        self._executor.shutdown()

        # Exponential backoff
        import time
        delay = self._base_reinit_delay * (2 ** (self._consecutive_failures - 1))
        delay = min(delay, 120)  # Cap at 2 minutes
        time.sleep(delay)

        success = self._executor.init_mt5()
        if success:
            log_event("mt5_reinit_success")
        else:
            log_event("mt5_reinit_failed")
