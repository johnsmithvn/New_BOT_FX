"""
main.py

Startup orchestration for telegram-mt5-bot.
Full pipeline: Telegram → Parser → Validator → Risk → Order Builder → Executor → Storage.

P3 features:
- Smart dry-run mode (dynamic bid/ask from signal entry)
- Pipeline summary logging
- Signal lifecycle events in DB
- Circuit breaker with Telegram alerting
- Background storage cleanup
- Global exception handling
- Session metrics (parsed/rejected/executed/failed + avg/max latency)
- Heartbeat log (rich status every N minutes)
"""

from __future__ import annotations

import asyncio
import signal
import sys
import time
from dataclasses import dataclass, field

from config.settings import load_settings
from core.models import ParsedSignal, ParseFailure, Side, SignalStatus, OrderKind
from core.signal_parser.parser import SignalParser
from core.signal_validator import SignalValidator
from core.risk_manager import RiskManager
from core.order_builder import OrderBuilder
from core.trade_executor import TradeExecutor
from core.storage import Storage
from core.telegram_listener import TelegramListener
from core.order_lifecycle_manager import OrderLifecycleManager
from core.mt5_watchdog import MT5Watchdog
from core.message_update_handler import MessageUpdateHandler, UpdateAction
from core.circuit_breaker import CircuitBreaker, BreakerState
from core.telegram_alerter import TelegramAlerter
from core.daily_risk_guard import DailyRiskGuard
from core.exposure_guard import ExposureGuard
from core.position_manager import PositionManager
from core.command_parser import CommandParser
from core.command_executor import CommandExecutor
from utils.logger import setup_logger, log_event
from utils.symbol_mapper import SymbolMapper


@dataclass
class _SessionMetrics:
    """In-memory counters for the current bot session.

    Tracks signal outcomes and execution latency.
    Latency is measured only for successfully executed signals
    (signal_received → order done).
    """
    parsed:           int = field(default=0)
    rejected:         int = field(default=0)
    executed:         int = field(default=0)
    failed:           int = field(default=0)
    # Latency tracking (executed signals only)
    _exec_count:      int = field(default=0, repr=False)
    _total_lat_ms:    int = field(default=0, repr=False)
    _max_lat_ms:      int = field(default=0, repr=False)

    def record_latency(self, latency_ms: int) -> None:
        """Record latency for a successfully executed signal."""
        self._exec_count += 1
        self._total_lat_ms += latency_ms
        if latency_ms > self._max_lat_ms:
            self._max_lat_ms = latency_ms

    @property
    def avg_execution_latency_ms(self) -> int:
        if self._exec_count == 0:
            return 0
        return self._total_lat_ms // self._exec_count

    @property
    def max_execution_latency_ms(self) -> int:
        return self._max_lat_ms


class Bot:
    """Main bot orchestration.

    Wires all components and manages the signal processing pipeline.
    """

    def __init__(self) -> None:
        self.settings = load_settings()
        self.storage: Storage | None = None
        self.parser: SignalParser | None = None
        self.validator: SignalValidator | None = None
        self.risk_manager: RiskManager | None = None
        self.order_builder: OrderBuilder | None = None
        self.executor: TradeExecutor | None = None
        self.listener: TelegramListener | None = None
        self.lifecycle_mgr: OrderLifecycleManager | None = None
        self.watchdog: MT5Watchdog | None = None
        self.update_handler: MessageUpdateHandler | None = None
        self.circuit_breaker: CircuitBreaker | None = None
        self.alerter: TelegramAlerter | None = None
        self.daily_guard: DailyRiskGuard | None = None
        self.exposure_guard: ExposureGuard | None = None
        self.position_mgr: PositionManager | None = None
        self.command_parser: CommandParser | None = None
        self.command_executor: CommandExecutor | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._metrics = _SessionMetrics()
        self._start_time: float = 0.0

    def _init_components(self) -> None:
        """Initialize all components."""
        s = self.settings

        # Logger
        setup_logger(
            level=s.log.level,
            file_path=s.log.file,
            rotation=s.log.rotation,
        )
        log_event("system_startup")

        # Storage
        self.storage = Storage()

        # Parser
        mapper = SymbolMapper()
        self.parser = SignalParser(
            symbol_mapper=mapper,
            max_message_length=s.parser.max_message_length,
        )

        # Validator — all thresholds in PIPS
        self.validator = SignalValidator(
            max_entry_distance_pips=s.safety.max_entry_distance_pips,
            signal_age_ttl_seconds=s.safety.signal_age_ttl_seconds,
            max_spread_pips=s.safety.max_spread_pips,
            max_open_trades=s.safety.max_open_trades,
            max_entry_drift_pips=s.safety.max_entry_drift_pips,
        )

        # Risk Manager
        self.risk_manager = RiskManager(
            mode=s.risk.mode,
            fixed_lot_size=s.risk.fixed_lot_size,
            risk_percent=s.risk.risk_percent,
            lot_min=s.risk.lot_min,
            lot_max=s.risk.lot_max,
            lot_step=s.risk.lot_step,
        )

        # Order Builder — values from config, no hardcoded magic numbers
        self.order_builder = OrderBuilder(
            market_tolerance_points=s.execution.market_tolerance_points,
            deviation=s.execution.deviation_points,
            magic=s.execution.bot_magic_number,
            dynamic_deviation_multiplier=s.execution.dynamic_deviation_multiplier,
        )

        # Trade Executor — retries from config
        self.executor = TradeExecutor(
            mt5_path=s.mt5.path,
            login=s.mt5.login,
            password=s.mt5.password,
            server=s.mt5.server,
            max_retries=s.execution.max_retries,
            retry_delay_seconds=s.execution.retry_delay_seconds,
        )

        # Circuit Breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=s.runtime.circuit_breaker_threshold,
            cooldown_seconds=s.runtime.circuit_breaker_cooldown,
        )

        # Telegram Alerter
        self.alerter = TelegramAlerter(
            admin_chat=s.telegram.admin_chat,
            cooldown_seconds=s.runtime.alert_cooldown_seconds,
        )

        # Wire circuit breaker → alerter
        self.circuit_breaker.on_state_change(self._on_breaker_change)

        # MessageEdited handler
        self.update_handler = MessageUpdateHandler(
            parser=self.parser,
            storage=self.storage,
        )

        # Telegram Listener
        self.listener = TelegramListener(
            api_id=s.telegram.api_id,
            api_hash=s.telegram.api_hash,
            session_name=s.telegram.session_name,
            phone=s.telegram.phone,
            source_chats=s.telegram.source_chats,
            session_reset_hours=s.telegram.session_reset_hours,
        )
        self.listener.set_pipeline_callback(self._process_signal)
        self.listener.set_edit_callback(self._process_edit)

        # Lifecycle Manager — check interval from config
        self.lifecycle_mgr = OrderLifecycleManager(
            executor=self.executor,
            ttl_minutes=s.safety.pending_order_ttl_minutes,
            check_interval_seconds=s.execution.lifecycle_check_interval_seconds,
        )

        # MT5 Watchdog — intervals from config
        self.watchdog = MT5Watchdog(
            executor=self.executor,
            check_interval_seconds=s.execution.watchdog_interval_seconds,
            max_reinit_retries=s.execution.watchdog_max_reinit,
            on_connection_lost=self._on_mt5_connection_lost,
            on_reinit_exhausted=self._on_mt5_reinit_exhausted,
        )

        # Daily Risk Guard — live mode only (no MT5 deal history in dry-run)
        if not s.runtime.dry_run:
            self.daily_guard = DailyRiskGuard(
                max_daily_trades=s.safety.max_daily_trades,
                max_daily_loss_usd=s.safety.max_daily_loss_usd,
                max_consecutive_losses=s.safety.max_consecutive_losses,
                poll_interval_minutes=s.safety.daily_risk_poll_minutes,
                on_limit_hit=self._on_daily_limit_hit,
            )

        # Exposure Guard — live mode only
        if not s.runtime.dry_run:
            corr_groups = []
            raw_groups = s.safety.correlation_groups.strip()
            if raw_groups:
                for group_str in raw_groups.split(","):
                    symbols = [sym.strip() for sym in group_str.split(":") if sym.strip()]
                    if len(symbols) >= 2:
                        corr_groups.append(symbols)

            self.exposure_guard = ExposureGuard(
                executor=self.executor,
                max_same_symbol_trades=s.safety.max_same_symbol_trades,
                max_correlated_trades=s.safety.max_correlated_trades,
                correlation_groups=corr_groups,
            )

        # Position Manager — live mode only
        if not s.runtime.dry_run:
            self.position_mgr = PositionManager(
                executor=self.executor,
                settings=s,
            )

        # Command Parser + Executor
        self.command_parser = CommandParser()
        self.command_executor = CommandExecutor(
            magic=s.execution.bot_magic_number,
        )

    # ── Alert Callbacks ──────────────────────────────────────────

    def _on_breaker_change(self, old_state, new_state) -> None:
        """Circuit breaker state change callback."""
        if new_state == BreakerState.OPEN:
            self.alerter.send_alert_sync(
                "circuit_breaker_open",
                "🔴 **CIRCUIT BREAKER OPENED**\n"
                "Trading paused due to consecutive execution failures.\n"
                f"Cooldown: {self.settings.runtime.circuit_breaker_cooldown}s",
            )
        elif new_state == BreakerState.CLOSED and old_state == BreakerState.HALF_OPEN:
            self.alerter.send_alert_sync(
                "circuit_breaker_close",
                "🟢 **CIRCUIT BREAKER CLOSED**\nTrading resumed.",
            )

    def _on_mt5_connection_lost(self) -> None:
        self.alerter.send_alert_sync(
            "mt5_connection_lost",
            "⚠️ **MT5 CONNECTION LOST**\nAttempting reinitialization...",
        )

    def _on_mt5_reinit_exhausted(self) -> None:
        self.alerter.send_alert_sync(
            "mt5_reinit_exhausted",
            "🔴 **MT5 REINIT FAILED**\nAll retries exhausted. Manual intervention required.",
        )

    def _on_daily_limit_hit(self, alert_key: str, message: str) -> None:
        """DailyRiskGuard limit breach callback → Telegram alert."""
        self.alerter.send_alert_sync(alert_key, message)

    # ── Smart Dry-Run Helpers ────────────────────────────────────

    def _simulate_tick(self, signal: ParsedSignal) -> tuple[float, float, float]:
        """Generate dynamic bid/ask from signal entry for dry-run.

        BUY signal → ask = entry, bid = entry - small_spread
        SELL signal → bid = entry, ask = entry + small_spread
        MARKET signal → use default simulated prices
        """
        # Determine simulated spread based on symbol
        spread = 0.5  # default for metals
        symbol = signal.symbol.upper()
        if any(fx in symbol for fx in ("USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF")):
            spread = 0.0002  # forex pairs
        elif "XAU" in symbol or "GOLD" in symbol:
            spread = 0.5
        elif "BTC" in symbol or "ETH" in symbol:
            spread = 10.0

        entry = signal.entry

        if entry is None:
            # Market order — use a reasonable synthetic price
            # based on SL/TP midpoint if available
            if signal.sl and signal.tp:
                entry = (signal.sl + signal.tp[0]) / 2
            elif signal.sl:
                entry = signal.sl + (50.0 * spread)
            elif signal.tp:
                entry = signal.tp[0] - (50.0 * spread)
            else:
                entry = 2000.0  # fallback for XAUUSD-like

        if signal.side == Side.BUY:
            ask = entry
            bid = entry - spread
        else:
            bid = entry
            ask = entry + spread

        spread_points = spread / (0.00001 if spread < 1 else 0.01)
        return bid, ask, spread_points

    # ── Pipeline ─────────────────────────────────────────────────

    def _process_signal(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Process a new signal through the full pipeline with exception safety."""
        try:
            self._do_process_signal(raw_text, chat_id, message_id)
        except Exception as exc:
            log_event(
                "pipeline_error",
                source_message_id=message_id,
                error=str(exc),
            )
            print(f"  [ERROR] Pipeline exception: {exc}")

    def _do_process_signal(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Internal pipeline logic."""
        dry_run = self.settings.runtime.dry_run
        t_start = time.monotonic()

        # ── Step 0: Check for management command ─────────────────
        cmd = self.command_parser.parse(raw_text)
        if cmd is not None:
            log_event("command_received", command=cmd.command_type.value, source_message_id=message_id)
            if dry_run:
                print(f"  [COMMAND] {cmd.command_type.value} — skipped (dry-run)")
                return
            summary = self.command_executor.execute(cmd)
            log_event("command_executed", command=cmd.command_type.value, summary=summary)
            print(f"  [COMMAND] {cmd.command_type.value} → {summary}")
            return

        # ── Step 1: Parse ────────────────────────────────────────
        result = self.parser.parse(
            raw_text,
            source_chat_id=chat_id,
            source_message_id=message_id,
        )

        if isinstance(result, ParseFailure):
            log_event(
                "parse_failed",
                fingerprint="",
                symbol="",
                reason=result.reason,
                source_message_id=message_id,
            )
            self.storage.store_event(
                fingerprint="",
                event_type="signal_received",
                details={"message_id": message_id, "outcome": "parse_failed"},
            )
            self.storage.store_event(
                fingerprint="",
                event_type="signal_parse_failed",
                details={"reason": result.reason, "message_id": message_id},
            )
            print(f"  [PIPELINE] parsed=FAIL reason=\"{result.reason}\"")
            return

        signal_obj: ParsedSignal = result
        fp = signal_obj.fingerprint[:12]

        # Count as parsed
        self._metrics.parsed += 1

        log_event(
            "parse_success",
            fingerprint=fp,
            symbol=signal_obj.symbol,
            side=signal_obj.side.value,
            entry=signal_obj.entry,
        )

        # DB lifecycle: signal_received → signal_parsed
        self.storage.store_event(
            fingerprint=fp,
            event_type="signal_received",
            symbol=signal_obj.symbol,
            details={"chat_id": chat_id, "message_id": message_id},
        )
        self.storage.store_event(
            fingerprint=fp,
            event_type="signal_parsed",
            symbol=signal_obj.symbol,
            details={
                "side": signal_obj.side.value,
                "entry": signal_obj.entry,
                "sl": signal_obj.sl,
                "tp": signal_obj.tp,
            },
        )

        # ── Step 2: Circuit breaker check ────────────────────────
        if not self.circuit_breaker.is_trading_allowed:
            reason = "circuit breaker OPEN — trading paused"
            log_event("validation_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=reason)
            self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": reason})
            self._metrics.rejected += 1
            print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=REJECTED reason=\"{reason}\"")
            return

        # ── Step 2b: Daily risk guard check ───────────────────────
        if self.daily_guard:
            allowed, guard_reason = self.daily_guard.is_trading_allowed
            if not allowed:
                log_event("validation_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=guard_reason)
                self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": guard_reason})
                self._metrics.rejected += 1
                print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=REJECTED reason=\"{guard_reason}\"")
                return

        # ── Step 2c: Exposure guard check ─────────────────────────
        if self.exposure_guard:
            exp_allowed, exp_reason = self.exposure_guard.is_allowed(signal_obj.symbol)
            if not exp_allowed:
                log_event("validation_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=exp_reason)
                self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": exp_reason})
                self._metrics.rejected += 1
                print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=REJECTED reason=\"{exp_reason}\"")
                return

        # ── Step 3: Duplicate check ──────────────────────────────
        is_dup = self.storage.is_duplicate(
            signal_obj.fingerprint,
            ttl_seconds=self.settings.safety.signal_age_ttl_seconds,
        )

        # ── Step 4: Get live market data ─────────────────────────
        #    Also resolve point / pip_size for this symbol.
        #    pip_size used by both validator (entry distance, spread)
        #    and order_builder (market tolerance).
        #
        #    XAUUSD: point=0.01, pip_size=0.1 (1 pip = 10 points)
        #    Forex:  point=0.00001, pip_size=0.0001
        #    JPY:    point=0.001, pip_size=0.01
        point = 0.00001
        pip_size = 0.0001  # forex default

        if dry_run:
            bid, ask, current_spread = self._simulate_tick(signal_obj)
            current_price = ask if signal_obj.side == Side.BUY else bid
            open_positions = 0
            # Estimate point/pip for dry run
            symbol = signal_obj.symbol.upper()
            if "XAU" in symbol or "GOLD" in symbol:
                point = 0.01
                pip_size = 0.1
            elif "JPY" in symbol:
                point = 0.001
                pip_size = 0.01
            else:
                point = 0.00001
                pip_size = 0.0001
        else:
            # Live: get point from MT5, derive pip_size
            try:
                import MetaTrader5 as mt5
                symbol_info = mt5.symbol_info(signal_obj.symbol)
                if symbol_info and symbol_info.point > 0:
                    point = symbol_info.point
                    # pip_size = point * 10 for 5-digit brokers,
                    # point itself for metals/JPY (2-3 digit)
                    digits = symbol_info.digits
                    if digits <= 3:
                        pip_size = point * 10  # XAU: 0.01*10=0.1
                    else:
                        pip_size = point * 10  # EUR: 0.00001*10=0.0001
            except Exception:
                pass

            tick = self.executor.get_tick(signal_obj.symbol)
            current_price = None
            current_spread = None
            bid, ask = 0.0, 0.0

            if tick:
                bid = tick.bid
                ask = tick.ask
                current_spread = tick.spread_points  # still in points here
                current_price = ask if signal_obj.side == Side.BUY else bid

            open_positions = self.executor.positions_total()

        # Convert spread from points to pips for validator
        current_spread_pips = None
        if current_spread is not None:
            current_spread_pips = current_spread / 10.0  # 10 points = 1 pip

        # ── Step 5: Validate ─────────────────────────────────────
        vr = self.validator.validate(
            signal_obj,
            current_price=current_price,
            current_spread_pips=current_spread_pips,
            open_positions=open_positions,
            is_duplicate=is_dup,
            pip_size=pip_size,
        )

        if not vr.valid:
            log_event("validation_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=vr.reason)
            self.storage.store_signal(signal_obj, SignalStatus.REJECTED)
            self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": vr.reason})
            self._metrics.rejected += 1
            print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=REJECTED reason=\"{vr.reason}\"")
            return

        # ── Step 6: Store signal ─────────────────────────────────
        self.storage.store_signal(signal_obj, SignalStatus.PARSED)

        # ── Step 7: Calculate volume ─────────────────────────────
        if dry_run:
            balance = 10000.0
        else:
            account = self.executor.account_info()
            balance = account["balance"] if account else 0.0

        volume = self.risk_manager.calculate_volume(
            balance=balance,
            entry=signal_obj.entry,
            sl=signal_obj.sl,
        )

        # ── Step 8: Build order ──────────────────────────────────
        # point and pip_size already resolved in Step 4

        decision = self.order_builder.decide_order_type(signal_obj, bid, ask, point)
        request = self.order_builder.build_request(
            signal_obj, decision, volume, bid, ask,
            spread_points=current_spread if current_spread else 0.0,
        )

        # ── Step 8b: Entry drift guard for MARKET orders ─────────
        #    When entry is explicit but order is MARKET (within tolerance),
        #    reject if price has drifted too far from signal entry.
        if decision.order_kind == OrderKind.MARKET and signal_obj.entry is not None:
            drift_result = self.validator.validate_entry_drift(
                signal_obj, current_price, pip_size
            )
            if not drift_result.valid:
                log_event("drift_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=drift_result.reason)
                self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.REJECTED)
                self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": drift_result.reason})
                self._metrics.rejected += 1
                print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=OK order=MARKET drift=REJECTED reason=\"{drift_result.reason}\"")
                return

        log_event(
            "order_submitted",
            fingerprint=fp,
            symbol=signal_obj.symbol,
            order_kind=decision.order_kind.value,
            volume=volume,
            price=request.get("price"),
        )
        self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.SUBMITTED)
        self.storage.store_event(fingerprint=fp, event_type="signal_submitted", symbol=signal_obj.symbol, details={"order_kind": decision.order_kind.value, "volume": volume, "price": request.get("price")})

        # ── Step 9: Execute ──────────────────────────────────────
        if dry_run:
            # Simulate execution
            log_event(
                "dry_run_execution",
                fingerprint=fp,
                symbol=signal_obj.symbol,
                order_kind=decision.order_kind.value,
                volume=volume,
                price=request.get("price"),
                sl=decision.sl,
                tp=decision.tp,
            )
            self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.EXECUTED)
            self.storage.store_event(fingerprint=fp, event_type="signal_executed", symbol=signal_obj.symbol, details={"dry_run": True, "order_kind": decision.order_kind.value})
            self.circuit_breaker.record_success()
            latency_ms = int((time.monotonic() - t_start) * 1000)
            self._metrics.executed += 1
            self._metrics.record_latency(latency_ms)
            print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=OK order={decision.order_kind.value} exec=DRY_RUN_OK vol={volume} latency={latency_ms}ms")
        else:
            exec_result = self.executor.execute(request, fingerprint=fp)

            if exec_result.success:
                self.circuit_breaker.record_success()
                self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.EXECUTED)
                self.storage.store_order(
                    ticket=exec_result.ticket, fingerprint=fp,
                    order_kind=decision.order_kind.value,
                    price=request.get("price"), sl=decision.sl, tp=decision.tp,
                    retcode=exec_result.retcode, success=True,
                )
                self.storage.store_event(fingerprint=fp, event_type="signal_executed", symbol=signal_obj.symbol, details={"ticket": exec_result.ticket, "retcode": exec_result.retcode})
                latency_ms = int((time.monotonic() - t_start) * 1000)
                self._metrics.executed += 1
                self._metrics.record_latency(latency_ms)
                print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=OK order={decision.order_kind.value} exec=SUCCESS ticket={exec_result.ticket} latency={latency_ms}ms")

                # Log remaining TPs
                if len(signal_obj.tp) > 1:
                    log_event("multi_tp_info", fingerprint=fp, symbol=signal_obj.symbol, remaining_tps=signal_obj.tp[1:])
            else:
                self.circuit_breaker.record_failure()
                self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.FAILED)
                self.storage.store_order(
                    ticket=None, fingerprint=fp,
                    order_kind=decision.order_kind.value,
                    price=request.get("price"), sl=decision.sl, tp=decision.tp,
                    retcode=exec_result.retcode, success=False,
                )
                self.storage.store_event(fingerprint=fp, event_type="signal_failed", symbol=signal_obj.symbol, details={"retcode": exec_result.retcode, "message": exec_result.message})
                latency_ms = int((time.monotonic() - t_start) * 1000)
                self._metrics.failed += 1
                print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=OK order={decision.order_kind.value} exec=FAILED retcode={exec_result.retcode} latency={latency_ms}ms")

    def _process_edit(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Process an edited message."""
        log_event("edit_received", source_chat_id=chat_id, source_message_id=message_id)

    # ── Background Tasks ─────────────────────────────────────────

    async def _storage_cleanup_loop(self) -> None:
        """Background cleanup of old storage records.

        Runs every 24 hours. Lightweight operation.
        """
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Every 24 hours
                retention = self.settings.runtime.storage_retention_days
                self.storage.cleanup_old_records(retention)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("storage_cleanup_error", error=str(exc))

    async def _heartbeat_loop(self) -> None:
        """Background heartbeat — logs rich session status every N minutes.

        Output format:
            [HEARTBEAT] uptime=Nm  parsed=N  executed=N  rejected=N  failed=N
                        avg_latency=Nms  max_latency=Nms
                        open_positions=N  pending_orders=N
                        mt5=OK  telegram=OK
        """
        interval = self.settings.runtime.heartbeat_interval_minutes * 60
        while True:
            try:
                await asyncio.sleep(interval)
                self._emit_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("heartbeat_error", error=str(exc))

    def _emit_heartbeat(self) -> None:
        """Collect system state and emit heartbeat log line."""
        dry_run = self.settings.runtime.dry_run
        m = self._metrics

        # Uptime
        uptime_s = int(time.monotonic() - self._start_time)
        uptime_min = uptime_s // 60

        # Live system state
        if dry_run:
            open_positions = "N/A"
            pending_orders = "N/A"
            mt5_status = "N/A (dry-run)"
        else:
            try:
                open_positions = self.executor.positions_total() if self.executor else "?"
                pending_orders = self.executor.orders_total() if self.executor else "?"
                mt5_status = "OK" if (self.executor and self.executor.is_connected) else "FAIL"
            except Exception:
                open_positions = "ERR"
                pending_orders = "ERR"
                mt5_status = "ERR"

        try:
            tg_status = "OK" if (self.listener and self.listener.is_connected) else "FAIL"
        except Exception:
            tg_status = "ERR"

        # Daily guard stats
        daily_guard_info = {}
        if self.daily_guard:
            daily_guard_info = self.daily_guard.daily_stats

        log_event(
            "heartbeat",
            uptime_min=uptime_min,
            parsed=m.parsed,
            executed=m.executed,
            rejected=m.rejected,
            failed=m.failed,
            avg_latency_ms=m.avg_execution_latency_ms,
            max_latency_ms=m.max_execution_latency_ms,
            open_positions=open_positions,
            pending_orders=pending_orders,
            mt5=mt5_status,
            telegram=tg_status,
            **daily_guard_info,
        )

        daily_str = ""
        if daily_guard_info:
            daily_str = (
                f"  daily_trades={daily_guard_info.get('daily_trades', 0)}"
                f"  daily_loss=${daily_guard_info.get('daily_loss_usd', 0)}"
                f"  consec_losses={daily_guard_info.get('consecutive_losses', 0)}"
            )

        print(
            f"  [HEARTBEAT] uptime={uptime_min}m"
            f"  parsed={m.parsed}  executed={m.executed}"
            f"  rejected={m.rejected}  failed={m.failed}"
            f"  avg_latency={m.avg_execution_latency_ms}ms"
            f"  max_latency={m.max_execution_latency_ms}ms"
            f"  open_positions={open_positions}  pending_orders={pending_orders}"
            f"  mt5={mt5_status}  telegram={tg_status}"
            f"{daily_str}"
        )

    # ── Startup Position Sync ─────────────────────────────────────

    def _sync_positions_on_startup(self) -> None:
        """Log audit of pre-existing MT5 state on startup.

        The validator already queries live MT5 on every signal, so no
        state injection is needed. This is purely for operator awareness.
        """
        positions = self.executor.positions_total()
        orders = self.executor.orders_total()
        max_open = self.settings.safety.max_open_trades

        log_event(
            "startup_position_sync",
            open_positions=positions,
            pending_orders=orders,
            max_open_trades=max_open,
        )
        print(f"  [STARTUP SYNC] positions={positions}  pending_orders={orders}")

        if positions >= max_open:
            msg = (
                f"⚠️ **STARTUP WARNING**\n"
                f"Open positions ({positions}) >= MAX_OPEN_TRADES ({max_open}).\n"
                f"Bot will refuse new signals until positions close."
            )
            log_event("startup_position_warning", positions=positions, max_open=max_open)
            print(f"  [WARNING] positions ({positions}) >= MAX_OPEN_TRADES ({max_open}) — new signals will be refused")
            self.alerter.send_alert_sync("startup_position_warning", msg)

    # ── Startup and Shutdown ─────────────────────────────────────

    async def run(self) -> None:
        """Start the bot and run until interrupted."""
        self._init_components()
        self._start_time = time.monotonic()

        dry_run = self.settings.runtime.dry_run

        # Init MT5
        if not dry_run:
            if not self.executor.init_mt5():
                print("[FATAL] MT5 initialization failed. Check .env credentials.")
                return
        else:
            print("[DRY RUN] MT5 execution disabled — simulating orders.")

        # Banner
        s = self.settings
        print("=" * 55)
        print(f"  telegram-mt5-bot  v0.5.1  {'[DRY RUN]' if dry_run else '[LIVE]'}")
        print("=" * 55)
        print(f"  Risk mode    : {s.risk.mode}")
        print(f"  Max spread   : {s.safety.max_spread_pips} pips")
        print(f"  Max distance : {s.safety.max_entry_distance_pips} pips")
        print(f"  Signal TTL   : {s.safety.signal_age_ttl_seconds}s")
        print(f"  Pending TTL  : {s.safety.pending_order_ttl_minutes}min")
        print(f"  Max trades   : {s.safety.max_open_trades}")
        print(f"  Breaker      : {s.runtime.circuit_breaker_threshold} fails → pause")
        print(f"  Session reset: {s.telegram.session_reset_hours}h")
        # Daily Risk Guard config
        if not dry_run and self.daily_guard:
            print(f"  Daily trades : {s.safety.max_daily_trades or 'unlimited'}")
            print(f"  Daily loss   : {'$' + str(s.safety.max_daily_loss_usd) if s.safety.max_daily_loss_usd > 0 else 'unlimited'}")
            print(f"  Consec losses: {s.safety.max_consecutive_losses or 'unlimited'}")
            print(f"  Risk poll    : {s.safety.daily_risk_poll_minutes}min")
        if dry_run:
            print(f"  Dry run      : ON (no real orders)")
        print("=" * 55)

        # Startup self-check + position sync
        if not dry_run:
            account = self.executor.account_info()
            if account:
                print(f"  MT5 Account  : {account['login']} @ {account['server']}")
                print(f"  Balance      : {account['balance']}")
                print(f"  Equity       : {account['equity']}")
                print("=" * 55)
            self._sync_positions_on_startup()

        # Start Telegram listener
        await self.listener.start()

        # Share Telethon client with alerter
        if self.listener.client:
            self.alerter.set_client(self.listener.client)

        # Start background services
        if not dry_run:
            await self.lifecycle_mgr.start()
            await self.watchdog.start()
            if self.daily_guard:
                await self.daily_guard.start()
            if self.position_mgr:
                await self.position_mgr.start()

        self._cleanup_task = asyncio.create_task(self._storage_cleanup_loop())

        # Start heartbeat if enabled
        hb_interval = self.settings.runtime.heartbeat_interval_minutes
        if hb_interval > 0:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            print(f"  Heartbeat    : every {hb_interval}min")
        else:
            print("  Heartbeat    : disabled")
        print("=" * 55)
        await self.alerter.send_alert(
            "bot_started",
            f"🟢 **BOT STARTED** {'[DRY RUN]' if dry_run else '[LIVE]'}\n"
            f"Pipeline active. Listening for signals.",
        )

        log_event("system_ready", dry_run=dry_run)
        print("\n[INFO] Bot is running. Ctrl+C to stop.\n")

        try:
            await self.listener.run_until_disconnected()
        except KeyboardInterrupt:
            pass
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        """Graceful shutdown."""
        log_event("system_shutdown")
        print("\n[INFO] Shutting down...")

        # Print session summary
        m = self._metrics
        uptime_s = int(time.monotonic() - self._start_time)
        print(
            f"  [SESSION] uptime={uptime_s // 60}m"
            f"  parsed={m.parsed}  rejected={m.rejected}"
            f"  executed={m.executed}  failed={m.failed}"
            f"  avg_latency={m.avg_execution_latency_ms}ms"
            f"  max_latency={m.max_execution_latency_ms}ms"
        )
        log_event(
            "session_summary",
            uptime_min=uptime_s // 60,
            parsed=m.parsed,
            rejected=m.rejected,
            executed=m.executed,
            failed=m.failed,
            avg_latency_ms=m.avg_execution_latency_ms,
            max_latency_ms=m.max_execution_latency_ms,
        )

        # Send shutdown alert
        try:
            await self.alerter.send_alert("bot_stopped", "🔴 **BOT STOPPED**")
        except Exception:
            pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.daily_guard:
            await self.daily_guard.stop()
        if self.position_mgr:
            await self.position_mgr.stop()
        if self.watchdog:
            await self.watchdog.stop()
        if self.lifecycle_mgr:
            await self.lifecycle_mgr.stop()
        if self.listener:
            await self.listener.stop()
        if self.executor and not self.settings.runtime.dry_run:
            self.executor.shutdown()
        if self.storage:
            self.storage.close()

        print("[INFO] Shutdown complete.")


def main() -> None:
    """Entry point."""
    bot = Bot()
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
