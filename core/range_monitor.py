"""
core/range_monitor.py

Background price monitor for re-entry triggers (P9).

RESPONSIBILITIES (strict):
- Poll price at interval
- Detect price CROSSING a pending level (not just "is near")
- Emit event via callback when cross detected
- Debounce: ignore same level for N seconds after trigger

NOT responsible for:
- Executing orders (Pipeline does that via callback)
- Managing signal state (SignalStateManager does that)
- Making strategy decisions (EntryStrategy does that)
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Callable

from core.models import EntryPlan, Side, SignalState
from utils.logger import log_event

if TYPE_CHECKING:
    from core.signal_state_manager import SignalStateManager
    from core.trade_executor import TradeExecutor


# Callback type: receives (SignalState, EntryPlan)
ReentryCallback = Callable[[SignalState, EntryPlan], None]


class RangeMonitor:
    """Background price monitor — emits re-entry events.

    Price-cross detection:
        BUY re-entry: trigger when price drops THROUGH level
                      (prev > level, current ≤ level)
        SELL re-entry: trigger when price rises THROUGH level
                       (prev < level, current ≥ level)

    Debounce:
        After triggering a level, ignore the same level for
        debounce_seconds. Prevents spam when price oscillates
        around a level.

    Thread safety:
        Runs as an asyncio background task. Uses synchronous
        callback (Pipeline.handle_reentry) which is expected
        to be fast and non-blocking for the critical path.
    """

    def __init__(
        self,
        executor: TradeExecutor,
        state_manager: SignalStateManager,
        on_reentry: ReentryCallback,
        poll_seconds: int = 5,
        debounce_seconds: int = 30,
    ) -> None:
        self._executor = executor
        self._state_mgr = state_manager
        self._on_reentry = on_reentry
        self._poll_seconds = poll_seconds
        self._debounce_seconds = debounce_seconds
        self._last_trigger: dict[str, float] = {}  # "fp:level_id" → epoch
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_signals(self) -> int:
        return self._state_mgr.active_count

    async def start(self) -> None:
        """Start the background monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        log_event(
            "range_monitor_started",
            poll_seconds=self._poll_seconds,
            debounce_seconds=self._debounce_seconds,
        )

    async def stop(self) -> None:
        """Stop the background monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log_event("range_monitor_stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop. Runs until stopped."""
        while self._running:
            try:
                await asyncio.sleep(self._poll_seconds)
                if not self._running:
                    break

                # Check re-entries
                self._check_reentries()

                # Expire old signals
                expired = self._state_mgr.expire_old()
                if expired > 0:
                    log_event("range_monitor_expired", count=expired)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event(
                    "range_monitor_error",
                    error=str(exc),
                )
                # Don't crash the monitor on transient errors
                await asyncio.sleep(1)

    def _check_reentries(self) -> None:
        """Check all pending re-entry levels against current prices."""
        pending = self._state_mgr.get_pending_reentries()
        if not pending:
            return

        # Group by symbol to minimize tick requests
        by_symbol: dict[str, list[tuple[SignalState, EntryPlan]]] = {}
        for state, plan in pending:
            by_symbol.setdefault(state.symbol, []).append((state, plan))

        for symbol, entries in by_symbol.items():
            tick = self._executor.get_tick(symbol)
            if not tick:
                continue

            for state, plan in entries:
                ref_price = tick.ask if state.side == Side.BUY else tick.bid

                if self._is_price_crossing(state, plan, ref_price):
                    debounce_key = f"{state.fingerprint}:{plan.level_id}"

                    if self._is_debounced(debounce_key):
                        continue

                    # Record trigger time for debounce
                    self._last_trigger[debounce_key] = time.time()

                    log_event(
                        "range_monitor_trigger",
                        fingerprint=state.fingerprint,
                        level_id=plan.level_id,
                        level=plan.level,
                        price=ref_price,
                        symbol=symbol,
                    )

                    # Emit → Pipeline.handle_reentry()
                    try:
                        self._on_reentry(state, plan)
                    except Exception as exc:
                        log_event(
                            "range_monitor_callback_error",
                            fingerprint=state.fingerprint,
                            level_id=plan.level_id,
                            error=str(exc),
                        )
                else:
                    # Update last_price for next cross detection
                    state.last_price = ref_price

    def _is_price_crossing(
        self,
        state: SignalState,
        plan: EntryPlan,
        current_price: float,
    ) -> bool:
        """Detect price CROSSING through a level.

        Cross = price was on one side of level, now on the other.
        Uses state.last_price as previous reference.

        BUY re-entry: trigger when price drops THROUGH level
            (previous > level and current ≤ level)
            → Price entered buy zone / got cheaper

        SELL re-entry: trigger when price rises THROUGH level
            (previous < level and current ≥ level)
            → Price entered sell zone / got more expensive
        """
        prev = state.last_price
        if prev is None:
            # First check — record price but don't trigger
            state.last_price = current_price
            return False

        level = plan.level

        # Update stored price BEFORE returning
        state.last_price = current_price

        if state.side == Side.BUY:
            return prev > level and current_price <= level
        else:
            return prev < level and current_price >= level

    def _is_debounced(self, key: str) -> bool:
        """Check if this level was triggered recently."""
        last = self._last_trigger.get(key, 0.0)
        return (time.time() - last) < self._debounce_seconds

