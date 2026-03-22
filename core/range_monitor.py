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
        reentry_tolerance_pips: float = 0.0,
    ) -> None:
        self._executor = executor
        self._state_mgr = state_manager
        self._on_reentry = on_reentry
        self._poll_seconds = poll_seconds
        self._debounce_seconds = debounce_seconds
        self._reentry_tolerance_pips = reentry_tolerance_pips  # G5
        self._last_trigger: dict[str, float] = {}  # "fp:level_id" → epoch
        self._pip_size_cache: dict[str, float] = {}  # symbol → pip_size
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
            reentry_tolerance_pips=self._reentry_tolerance_pips,
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
        """Check all pending re-entry levels against current prices.

        G11: SL breach — if price crossed SL, cancel all pending plans.
        Each plan is checked individually via cross detection.
        """
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

            # G11: Group by fingerprint for SL breach check
            by_fp: dict[str, list[tuple[SignalState, EntryPlan]]] = {}
            for state, plan in entries:
                by_fp.setdefault(state.fingerprint, []).append((state, plan))

            for fp, fp_entries in by_fp.items():
                state = fp_entries[0][0]  # Same signal state for all
                ref_price = tick.ask if state.side == Side.BUY else tick.bid

                # G11: Check SL breach BEFORE checking plans
                if state.sl is not None:
                    sl_breached = (
                        (state.side == Side.SELL and ref_price >= state.sl) or
                        (state.side == Side.BUY and ref_price <= state.sl)
                    )
                    if sl_breached:
                        cancelled = self._state_mgr.cancel_all_pending(fp)
                        log_event(
                            "sl_breach_cancel_all",
                            fingerprint=fp,
                            symbol=symbol,
                            sl=state.sl,
                            price=ref_price,
                            cancelled_plans=cancelled,
                        )
                        continue  # Skip to next signal

                # Check each plan individually
                for st, plan in fp_entries:
                    if self._is_price_crossing(st, plan, ref_price):
                        debounce_key = f"{st.fingerprint}:{plan.level_id}"
                        if self._is_debounced(debounce_key):
                            continue

                        self._last_trigger[debounce_key] = time.time()

                        log_event(
                            "range_monitor_trigger",
                            fingerprint=st.fingerprint,
                            level_id=plan.level_id,
                            level=plan.level,
                            price=ref_price,
                            symbol=symbol,
                        )

                        try:
                            self._on_reentry(st, plan)
                        except Exception as exc:
                            log_event(
                                "range_monitor_callback_error",
                                fingerprint=st.fingerprint,
                                level_id=plan.level_id,
                                error=str(exc),
                            )
                    else:
                        # Update last_price for next cross detection
                        st.last_price = ref_price

    def _is_price_crossing(
        self,
        state: SignalState,
        plan: EntryPlan,
        current_price: float,
    ) -> bool:
        """Detect price CROSSING through a level.

        Cross = price was on one side of level, now on the other.
        Uses state.last_price as previous reference.

        G5: With tolerance, cross detection uses effective_level:
            effective = level + tol (BUY) or level - tol (SELL)
            This fires slightly before exact cross.

        BUY re-entry: trigger when price drops THROUGH level
            (previous > eff_level and current <= eff_level)

        SELL re-entry: trigger when price rises THROUGH level
            (previous < eff_level and current >= eff_level)
        """
        prev = state.last_price
        if prev is None:
            # First check — record price but don't trigger
            state.last_price = current_price
            return False

        level = plan.level

        # G5: Apply tolerance to widen trigger zone
        tol = 0.0
        if self._reentry_tolerance_pips > 0:
            pip_size = self._get_pip_size(state.symbol)
            tol = self._reentry_tolerance_pips * pip_size

        # Update stored price BEFORE returning
        state.last_price = current_price

        if state.side == Side.BUY:
            eff_level = level + tol  # BUY: trigger slightly above level
            return prev > eff_level and current_price <= eff_level
        else:
            eff_level = level - tol  # SELL: trigger slightly below level
            return prev < eff_level and current_price >= eff_level

    def _get_pip_size(self, symbol: str) -> float:
        """Get pip size for symbol, with caching (G5)."""
        if symbol in self._pip_size_cache:
            return self._pip_size_cache[symbol]

        pip_size = 0.1  # default (XAUUSD)
        try:
            import MetaTrader5 as mt5
            info = mt5.symbol_info(symbol)
            if info and info.point > 0:
                pip_size = info.point * 10
        except Exception:
            pass

        self._pip_size_cache[symbol] = pip_size
        return pip_size

    def _is_debounced(self, key: str) -> bool:
        """Check if this level was triggered recently."""
        last = self._last_trigger.get(key, 0.0)
        return (time.time() - last) < self._debounce_seconds

