"""
core/order_lifecycle_manager.py

Manage lifecycle of pending orders.
Track expiration time and auto-cancel orders exceeding TTL.
Prevent stale signals from executing hours later.
"""

from __future__ import annotations

import asyncio
import time

from core.trade_executor import TradeExecutor
from utils.logger import log_event


class OrderLifecycleManager:
    """Monitor and expire pending orders.

    Periodically checks pending orders in MT5 and cancels
    any that have exceeded the configured TTL.
    """

    def __init__(
        self,
        executor: TradeExecutor,
        ttl_minutes: int = 15,
        check_interval_seconds: int = 30,
    ) -> None:
        self._executor = executor
        self._ttl_seconds = ttl_minutes * 60
        self._check_interval = check_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the lifecycle monitoring loop."""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        log_event(
            "lifecycle_manager_started",
            ttl_minutes=self._ttl_seconds // 60,
            check_interval=self._check_interval,
        )

    async def stop(self) -> None:
        """Stop the lifecycle monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log_event("lifecycle_manager_stopped")

    async def _monitor_loop(self) -> None:
        """Periodically check and expire stale pending orders."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                self._check_and_expire()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event(
                    "lifecycle_monitor_error",
                    error=str(exc),
                )

    def _check_and_expire(self) -> None:
        """Check all pending orders and cancel expired ones."""
        orders = self._executor.get_pending_orders()
        if not orders:
            return

        now = int(time.time())

        for order in orders:
            setup_time = order.get("time_setup", 0)
            age_seconds = now - setup_time

            if age_seconds > self._ttl_seconds:
                ticket = order["ticket"]
                symbol = order.get("symbol", "")
                comment = order.get("comment", "")

                # Extract fingerprint from comment if present
                fingerprint = ""
                if comment and comment.startswith("signal:"):
                    fingerprint = comment.replace("signal:", "")

                log_event(
                    "pending_order_expired",
                    fingerprint=fingerprint,
                    symbol=symbol,
                    ticket=ticket,
                    age_seconds=age_seconds,
                    ttl_seconds=self._ttl_seconds,
                )

                self._executor.cancel_order(
                    ticket=ticket,
                    fingerprint=fingerprint,
                )
