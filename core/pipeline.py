"""
core/pipeline.py

Signal pipeline orchestrator for multi-order strategy execution (P9).

RESPONSIBILITIES (strict — SOLE orchestrator):
- Decide whether to use multi-order (range/scale_in) or single mode
- Generate entry plans via EntryStrategy
- Execute each planned entry through existing Bot pipeline
- Manage signal state lifecycle
- Handle re-entry callbacks from RangeMonitor

NOT responsible for:
- Parsing signals (signal_parser does that)
- Validating signals (signal_validator does that)
- Monitoring price (range_monitor does that)
- Managing positions (position_manager does that)

Design note:
    This module does NOT replace main.py's existing pipeline.
    Instead, it wraps the execution phase (steps 7-9) to support
    multiple orders from a single signal. The existing steps 0-6
    (command check, parse, circuit breaker, guards, dedup, validate)
    remain in main.py untouched.

    main.py calls pipeline.execute_signal_plans() after validation
    passes, replacing the old single-order execute path.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from core.entry_strategy import EntryStrategy
from core.models import (
    EntryPlan,
    OrderKind,
    ParsedSignal,
    Side,
    SignalLifecycle,
    SignalState,
    SignalStatus,
    order_fingerprint,
)
from utils.logger import log_event

if TYPE_CHECKING:
    from core.channel_manager import ChannelManager
    from core.circuit_breaker import CircuitBreaker
    from core.daily_risk_guard import DailyRiskGuard
    from core.exposure_guard import ExposureGuard
    from core.order_builder import OrderBuilder
    from core.position_manager import PositionManager
    from core.risk_manager import RiskManager
    from core.signal_state_manager import SignalStateManager
    from core.signal_validator import SignalValidator
    from core.storage import Storage
    from core.trade_executor import TradeExecutor


class SignalPipeline:
    """Orchestrate multi-order execution from a parsed signal.

    This is the SOLE decision-maker for order execution.
    EntryStrategy only generates plans. RangeMonitor only emits events.
    Pipeline decides whether to execute, defer, or reject.
    """

    def __init__(
        self,
        *,
        entry_strategy: EntryStrategy,
        state_manager: SignalStateManager,
        channel_manager: ChannelManager,
        order_builder: OrderBuilder,
        risk_manager: RiskManager,
        executor: TradeExecutor,
        storage: Storage,
        validator: SignalValidator,
        circuit_breaker: CircuitBreaker,
        daily_guard: DailyRiskGuard | None = None,
        exposure_guard: ExposureGuard | None = None,
        position_mgr: PositionManager | None = None,
    ) -> None:
        self._strategy = entry_strategy
        self._state_mgr = state_manager
        self._channel_mgr = channel_manager
        self._order_builder = order_builder
        self._risk_mgr = risk_manager
        self._executor = executor
        self._storage = storage
        self._validator = validator
        self._circuit_breaker = circuit_breaker
        self._daily_guard = daily_guard
        self._exposure_guard = exposure_guard
        self._position_mgr = position_mgr

    def execute_signal_plans(
        self,
        signal: ParsedSignal,
        bid: float,
        ask: float,
        point: float,
        balance: float,
        current_spread: float | None,
        dry_run: bool = False,
    ) -> list[dict[str, Any]]:
        """Execute signal through multi-order pipeline.

        Called by main.py AFTER all validation passes (steps 0-6).
        Replaces the old single-order execute path (steps 7-9).

        Args:
            signal: Validated, parsed signal.
            bid, ask: Current market prices.
            point: Symbol point size.
            balance: Account balance for volume calc.
            current_spread: Current spread in points (or None).
            dry_run: If True, simulate execution.

        Returns:
            List of execution result dicts, one per order attempted.
            Each dict: {level_id, fingerprint, order_kind, success, ticket, ...}
        """
        chat_id = signal.source_chat_id
        fp = signal.fingerprint  # base fingerprint

        # Get channel strategy config
        strategy_config = self._channel_mgr.get_strategy(chat_id)
        mode = strategy_config.get("mode", "single")

        # ── Single mode: delegate to classic single-order path ───
        if mode == "single":
            return self._execute_single(
                signal, bid, ask, point, balance, current_spread, dry_run,
            )

        # ── Multi-order mode (range / scale_in) ─────────────────
        return self._execute_multi(
            signal, strategy_config, bid, ask, point,
            balance, current_spread, dry_run,
        )

    def handle_reentry(
        self,
        signal_state: SignalState,
        plan: EntryPlan,
    ) -> dict[str, Any] | None:
        """Handle a re-entry trigger from RangeMonitor.

        Called when price crosses a pending re-entry level.
        Full risk check gauntlet before execution.

        Returns execution result dict, or None if rejected.
        """
        fp = signal_state.fingerprint

        # ── Risk check gauntlet ──────────────────────────────────
        if not self._circuit_breaker.is_trading_allowed:
            self._state_mgr.mark_level_cancelled(fp, plan.level_id)
            log_event(
                "reentry_rejected", fingerprint=fp,
                level_id=plan.level_id, reason="circuit_breaker",
            )
            return None

        if self._daily_guard:
            allowed, reason = self._daily_guard.is_trading_allowed
            if not allowed:
                self._state_mgr.mark_level_cancelled(fp, plan.level_id)
                log_event(
                    "reentry_rejected", fingerprint=fp,
                    level_id=plan.level_id, reason=reason,
                )
                return None

        if self._exposure_guard:
            allowed, reason = self._exposure_guard.is_allowed(signal_state.symbol)
            if not allowed:
                self._state_mgr.mark_level_cancelled(fp, plan.level_id)
                log_event(
                    "reentry_rejected", fingerprint=fp,
                    level_id=plan.level_id, reason=reason,
                )
                return None

        # ── Get fresh tick ───────────────────────────────────────
        tick = self._executor.get_tick(signal_state.symbol)
        if not tick:
            log_event(
                "reentry_rejected", fingerprint=fp,
                level_id=plan.level_id, reason="no_tick",
            )
            return None

        bid, ask = tick.bid, tick.ask

        # ── Calculate volume for this re-entry level ─────────────
        account = self._executor.account_info()
        balance = account["balance"] if account else 0.0
        volume = self._risk_mgr.calculate_volume(
            balance=balance,
            entry=plan.level,
            sl=signal_state.sl,
        )

        if volume <= 0:
            self._state_mgr.mark_level_cancelled(fp, plan.level_id)
            log_event(
                "reentry_rejected", fingerprint=fp,
                level_id=plan.level_id, reason="zero_volume",
            )
            return None

        # Volume split: recalculate for remaining plans
        strategy_config = self._channel_mgr.get_strategy(signal_state.channel_id)
        split_mode = strategy_config.get("volume_split", "equal")
        total_vol = signal_state.total_volume
        pending_plans = [
            p for p in signal_state.entry_plans if p.status == "pending"
        ]
        if pending_plans and total_vol > 0:
            volumes = self._strategy.split_volume(
                total_vol, pending_plans, signal_state.sl, split_mode,
            )
            # Find this plan's index and use its volume
            for i, p in enumerate(pending_plans):
                if p.level_id == plan.level_id and i < len(volumes):
                    volume = volumes[i]
                    break

        # ── Build + execute order ────────────────────────────────
        order_fp = order_fingerprint(fp, plan.level_id)

        # Build a minimal ParsedSignal-like for order_builder
        reentry_signal = ParsedSignal(
            symbol=signal_state.symbol,
            side=signal_state.side,
            entry=plan.level,
            sl=signal_state.sl,
            tp=signal_state.tp,
            source_chat_id=signal_state.source_chat_id,
            source_message_id=signal_state.source_message_id,
            fingerprint=order_fp,
        )

        # Get symbol info for point
        try:
            import MetaTrader5 as mt5
            symbol_info = mt5.symbol_info(signal_state.symbol)
            point = symbol_info.point if symbol_info else 0.00001
        except Exception:
            point = 0.00001

        decision = self._order_builder.decide_order_type(
            reentry_signal, bid, ask, point,
        )
        request = self._order_builder.build_request(
            reentry_signal, decision, volume, bid, ask,
            spread_points=tick.spread_points if hasattr(tick, 'spread_points') else 0.0,
        )

        exec_result = self._executor.execute(request, fingerprint=order_fp)

        result = {
            "level_id": plan.level_id,
            "fingerprint": order_fp,
            "order_kind": decision.order_kind.value,
            "volume": volume,
            "success": exec_result.success,
            "ticket": exec_result.ticket,
            "retcode": exec_result.retcode,
        }

        if exec_result.success:
            self._circuit_breaker.record_success()
            self._state_mgr.mark_level_executed(fp, plan.level_id)
            self._storage.store_order(
                ticket=exec_result.ticket, fingerprint=order_fp,
                order_kind=decision.order_kind.value,
                price=request.get("price"), sl=reentry_signal.sl,
                tp=decision.tp, retcode=exec_result.retcode, success=True,
                channel_id=signal_state.channel_id,
                source_chat_id=signal_state.source_chat_id,
                source_message_id=signal_state.source_message_id,
            )
            if self._position_mgr and exec_result.ticket:
                self._position_mgr.register_ticket(
                    exec_result.ticket, signal_state.channel_id,
                )
            log_event(
                "reentry_executed", fingerprint=order_fp,
                level_id=plan.level_id, ticket=exec_result.ticket,
                symbol=signal_state.symbol, volume=volume,
            )
        else:
            self._circuit_breaker.record_failure()
            self._state_mgr.mark_level_cancelled(fp, plan.level_id)
            self._storage.store_order(
                ticket=None, fingerprint=order_fp,
                order_kind=decision.order_kind.value,
                price=request.get("price"), sl=reentry_signal.sl,
                tp=decision.tp, retcode=exec_result.retcode, success=False,
                channel_id=signal_state.channel_id,
                source_chat_id=signal_state.source_chat_id,
                source_message_id=signal_state.source_message_id,
            )
            log_event(
                "reentry_failed", fingerprint=order_fp,
                level_id=plan.level_id, retcode=exec_result.retcode,
            )

        return result

    # ── Single mode (backward compatible) ────────────────────────

    def _execute_single(
        self,
        signal: ParsedSignal,
        bid: float,
        ask: float,
        point: float,
        balance: float,
        current_spread: float | None,
        dry_run: bool,
    ) -> list[dict[str, Any]]:
        """Single mode: exactly like the old pipeline. 1 signal → 1 order.

        Returns list with 1 result dict for consistency.
        """
        volume = self._risk_mgr.calculate_volume(
            balance=balance,
            entry=signal.entry,
            sl=signal.sl,
        )

        decision = self._order_builder.decide_order_type(
            signal, bid, ask, point,
        )
        request = self._order_builder.build_request(
            signal, decision, volume, bid, ask,
            spread_points=current_spread if current_spread else 0.0,
        )

        result = {
            "level_id": 0,
            "fingerprint": signal.fingerprint,
            "order_kind": decision.order_kind.value,
            "volume": volume,
            "decision": decision,
            "request": request,
        }

        if dry_run:
            result["success"] = True
            result["ticket"] = None
            result["retcode"] = 0
            result["dry_run"] = True
        else:
            exec_result = self._executor.execute(request, fingerprint=signal.fingerprint)
            result["success"] = exec_result.success
            result["ticket"] = exec_result.ticket
            result["retcode"] = exec_result.retcode

        return [result]

    # ── Multi-order mode (range / scale_in) ──────────────────────

    def _execute_multi(
        self,
        signal: ParsedSignal,
        strategy_config: dict[str, Any],
        bid: float,
        ask: float,
        point: float,
        balance: float,
        current_spread: float | None,
        dry_run: bool,
    ) -> list[dict[str, Any]]:
        """Multi-order mode: generate plans, execute immediate ones,
        register remainder for re-entry monitoring.
        """
        fp = signal.fingerprint
        chat_id = signal.source_chat_id

        # Generate entry plans
        plans = self._strategy.plan_entries(
            signal, strategy_config, bid, ask, point,
        )

        if not plans:
            log_event("pipeline_no_plans", fingerprint=fp, symbol=signal.symbol)
            return []

        # Calculate total volume
        total_volume = self._risk_mgr.calculate_volume(
            balance=balance,
            entry=signal.entry,
            sl=signal.sl,
        )

        # Split volume across plans
        split_mode = strategy_config.get("volume_split", "equal")
        volumes = self._strategy.split_volume(
            total_volume, plans, signal.sl, split_mode,
        )

        # Determine which plans execute NOW vs defer
        results: list[dict[str, Any]] = []
        deferred_plans: list[EntryPlan] = []

        for plan, vol in zip(plans, volumes):
            if plan.order_kind == OrderKind.MARKET or plan.level_id == 0:
                # Execute immediately
                result = self._execute_one_plan(
                    signal, plan, vol, bid, ask, point,
                    current_spread, dry_run,
                )
                results.append(result)
            else:
                # Defer: will be monitored by RangeMonitor
                deferred_plans.append(plan)

        # Register signal state if there are deferred plans
        if deferred_plans:
            ttl_minutes = strategy_config.get("signal_ttl_minutes", 15)
            now = datetime.now(timezone.utc)
            signal_state = SignalState(
                fingerprint=fp,
                symbol=signal.symbol,
                side=signal.side,
                entry_range=signal.entry_range,
                sl=signal.sl,
                tp=signal.tp,
                source_chat_id=chat_id,
                source_message_id=signal.source_message_id,
                channel_id=chat_id,
                entry_plans=plans,  # All plans (including executed ones)
                total_volume=total_volume,
                created_at=now,
                expires_at=now + timedelta(minutes=ttl_minutes),
            )
            # Mark already-executed plans
            for r in results:
                if r.get("success"):
                    for p in signal_state.entry_plans:
                        if p.level_id == r["level_id"]:
                            p.status = "executed"

            self._state_mgr.register(signal_state)
            log_event(
                "pipeline_deferred_plans",
                fingerprint=fp,
                deferred_count=len(deferred_plans),
                ttl_minutes=ttl_minutes,
            )

        return results

    def _execute_one_plan(
        self,
        signal: ParsedSignal,
        plan: EntryPlan,
        volume: float,
        bid: float,
        ask: float,
        point: float,
        current_spread: float | None,
        dry_run: bool,
    ) -> dict[str, Any]:
        """Execute a single entry plan."""
        fp = order_fingerprint(signal.fingerprint, plan.level_id)

        # Build a signal-like object with this plan's entry
        plan_signal = ParsedSignal(
            symbol=signal.symbol,
            side=signal.side,
            entry=plan.level,
            sl=signal.sl,
            tp=signal.tp,
            source_chat_id=signal.source_chat_id,
            source_message_id=signal.source_message_id,
            fingerprint=fp,
        )

        decision = self._order_builder.decide_order_type(
            plan_signal, bid, ask, point,
        )
        request = self._order_builder.build_request(
            plan_signal, decision, volume, bid, ask,
            spread_points=current_spread if current_spread else 0.0,
        )

        result: dict[str, Any] = {
            "level_id": plan.level_id,
            "fingerprint": fp,
            "order_kind": decision.order_kind.value,
            "volume": volume,
            "decision": decision,
            "request": request,
            "label": plan.label,
        }

        if dry_run:
            result["success"] = True
            result["ticket"] = None
            result["retcode"] = 0
            result["dry_run"] = True
            log_event(
                "multi_order_dry_run",
                fingerprint=fp, level_id=plan.level_id,
                order_kind=decision.order_kind.value, volume=volume,
            )
        else:
            exec_result = self._executor.execute(request, fingerprint=fp)
            result["success"] = exec_result.success
            result["ticket"] = exec_result.ticket
            result["retcode"] = exec_result.retcode

            if exec_result.success:
                self._circuit_breaker.record_success()
                self._storage.store_order(
                    ticket=exec_result.ticket, fingerprint=fp,
                    order_kind=decision.order_kind.value,
                    price=request.get("price"), sl=decision.sl, tp=decision.tp,
                    retcode=exec_result.retcode, success=True,
                    channel_id=signal.source_chat_id,
                    source_chat_id=signal.source_chat_id,
                    source_message_id=signal.source_message_id,
                )
                if self._position_mgr and exec_result.ticket:
                    self._position_mgr.register_ticket(
                        exec_result.ticket, signal.source_chat_id,
                    )
                log_event(
                    "multi_order_executed",
                    fingerprint=fp, level_id=plan.level_id,
                    ticket=exec_result.ticket,
                    symbol=signal.symbol, volume=volume,
                )
            else:
                self._circuit_breaker.record_failure()
                self._storage.store_order(
                    ticket=None, fingerprint=fp,
                    order_kind=decision.order_kind.value,
                    price=request.get("price"), sl=decision.sl, tp=decision.tp,
                    retcode=exec_result.retcode, success=False,
                    channel_id=signal.source_chat_id,
                    source_chat_id=signal.source_chat_id,
                    source_message_id=signal.source_message_id,
                )
                log_event(
                    "multi_order_failed",
                    fingerprint=fp, level_id=plan.level_id,
                    retcode=exec_result.retcode,
                )

        return result
