"""
core/mt5_watchdog.py

Periodically verify MT5 connection health.
Trigger reinitialization if connection is lost.
"""

from __future__ import annotations

import asyncio

from core.trade_executor import TradeExecutor
from utils.logger import log_event


class MT5Watchdog:
    """Monitor MT5 connection health.

    Runs a periodic health check using account_info().
    If the check fails, attempts to reinitialize the MT5 connection.
    """

    def __init__(
        self,
        executor: TradeExecutor,
        check_interval_seconds: int = 30,
        max_reinit_retries: int = 5,
        reinit_delay_seconds: float = 5.0,
    ) -> None:
        self._executor = executor
        self._check_interval = check_interval_seconds
        self._max_reinit = max_reinit_retries
        self._reinit_delay = reinit_delay_seconds
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
            if self._consecutive_failures > 0:
                log_event(
                    "mt5_connection_recovered",
                    previous_failures=self._consecutive_failures,
                )
            self._consecutive_failures = 0
            return

        # Health check failed
        self._consecutive_failures += 1
        log_event(
            "mt5_health_check_failed",
            consecutive_failures=self._consecutive_failures,
        )

        if self._consecutive_failures <= self._max_reinit:
            self._attempt_reinit()
        else:
            log_event(
                "mt5_reinit_exhausted",
                max_retries=self._max_reinit,
            )

    def _attempt_reinit(self) -> None:
        """Attempt to reinitialize the MT5 connection."""
        log_event(
            "mt5_reinit_attempt",
            attempt=self._consecutive_failures,
        )

        self._executor.shutdown()

        import time
        time.sleep(self._reinit_delay)

        success = self._executor.init_mt5()
        if success:
            log_event("mt5_reinit_success")
        else:
            log_event("mt5_reinit_failed")
