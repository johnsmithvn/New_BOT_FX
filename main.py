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
from core.models import ParsedSignal, ParseFailure, Side, SignalStatus, OrderKind, TradeDecision
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
from core.channel_manager import ChannelManager
from core.trade_tracker import TradeTracker
from core.command_parser import CommandParser
from core.command_executor import CommandExecutor
from core.reply_action_parser import ReplyActionParser, ReplyActionType
from core.reply_command_executor import ReplyCommandExecutor
from core.entry_strategy import EntryStrategy
from core.signal_state_manager import SignalStateManager
from core.pipeline import SignalPipeline
from core.range_monitor import RangeMonitor
from core.health import HealthStats, HealthCheckServer
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

    def as_summary(self) -> str:
        """One-line summary for heartbeat per-channel breakdown."""
        return f"p={self.parsed} e={self.executed} r={self.rejected} f={self.failed}"


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
        self.channel_mgr: ChannelManager | None = None
        self.trade_tracker: TradeTracker | None = None
        self.command_parser: CommandParser | None = None
        self.command_executor: CommandExecutor | None = None
        self.reply_parser: ReplyActionParser | None = None
        self.reply_executor: ReplyCommandExecutor | None = None
        self.signal_pipeline: SignalPipeline | None = None
        self.range_monitor: RangeMonitor | None = None
        self._state_mgr: SignalStateManager | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._metrics = _SessionMetrics()
        self._channel_metrics: dict[str, _SessionMetrics] = {}
        self._start_time: float = 0.0
        self._health = HealthStats()
        self._health_server: HealthCheckServer | None = None

    def _get_ch_metrics(self, chat_id: str) -> _SessionMetrics:
        """Lazy-init per-channel metrics."""
        if chat_id not in self._channel_metrics:
            self._channel_metrics[chat_id] = _SessionMetrics()
        return self._channel_metrics[chat_id]

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
        self.listener.set_reply_callback(self._process_reply)
        self.listener.set_delete_callback(self._process_delete)

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
            on_health_update=self._on_watchdog_health,
        )

        # Health check server (port from env or default 8080)
        import os
        health_port = int(os.getenv("HEALTH_CHECK_PORT", "8080"))
        self._health_server = HealthCheckServer(
            stats=self._health,
            port=health_port,
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

        # Channel Manager — always init (fallback to defaults if no config)
        self.channel_mgr = ChannelManager()

        # Position Manager — live mode only, with channel + storage DI
        if not s.runtime.dry_run:
            self.position_mgr = PositionManager(
                executor=self.executor,
                settings=s,
                channel_manager=self.channel_mgr,
                storage=self.storage,
                alerter=self.alerter,
            )

        # Trade Tracker — live mode only
        if not s.runtime.dry_run:
            self.trade_tracker = TradeTracker(
                storage=self.storage,
                alerter=self.alerter,
                magic_number=s.execution.bot_magic_number,
                poll_seconds=s.execution.trade_tracker_poll_seconds,
            )

        # Command Parser + Executor
        self.command_parser = CommandParser()
        self.command_executor = CommandExecutor(
            magic=s.execution.bot_magic_number,
        )

        # Reply Parser + Executor
        self.reply_parser = ReplyActionParser()
        self.reply_executor = ReplyCommandExecutor(
            magic=s.execution.bot_magic_number,
        )

        # ── P9: Signal Pipeline + Range Monitor ──────────────────
        entry_strategy = EntryStrategy()
        self._state_mgr = SignalStateManager(self.storage)

        self.signal_pipeline = SignalPipeline(
            entry_strategy=entry_strategy,
            state_manager=self._state_mgr,
            channel_manager=self.channel_mgr,
            order_builder=self.order_builder,
            risk_manager=self.risk_manager,
            executor=self.executor,
            storage=self.storage,
            validator=self.validator,
            circuit_breaker=self.circuit_breaker,
            daily_guard=self.daily_guard,
            exposure_guard=self.exposure_guard,
            position_mgr=self.position_mgr,
        )

        self.range_monitor = RangeMonitor(
            executor=self.executor,
            state_manager=self._state_mgr,
            on_reentry=self.signal_pipeline.handle_reentry,
        )

    # ── Alert Callbacks ──────────────────────────────────────────

    def _on_breaker_change(self, old_state, new_state) -> None:
        """Circuit breaker state change callback."""
        self._health.set_circuit_breaker(
            state=new_state.value,
            failures=self.circuit_breaker._consecutive_failures,
        )
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

    def _on_watchdog_health(self, connected: bool) -> None:
        """Watchdog health update callback."""
        self._health.set_mt5_status(connected)

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

    # ── Signal Debug ─────────────────────────────────────────────

    def _send_signal_debug(
        self,
        raw_text: str,
        signal: ParsedSignal | None,
        bid: float,
        ask: float,
        spread: float | None,
        *,
        rejected: bool = False,
        reject_reason: str = "",
        decision: TradeDecision | None = None,
        volume: float | None = None,
        request: dict | None = None,
    ) -> None:
        """Send pipeline debug message to admin Telegram.

        Called at 4 pipeline points:
        - Parse FAIL       (signal=None, rejected=True, reject_reason set)
        - Validation FAIL  (rejected=True, reject_reason set)
        - Drift FAIL       (rejected=True, reject_reason set)
        - Order Decision   (decision + volume + request set)
        """
        if not self.settings.runtime.debug_signal_decision:
            return

        lines: list[str] = []

        # Header
        if rejected:
            lines.append("📡 SIGNAL DEBUG — REJECTED")
        else:
            lines.append("📡 SIGNAL DEBUG — ORDER")
        lines.append("")

        # Raw signal (truncate to 500 chars)
        lines.append("Raw:")
        raw_display = raw_text[:500]
        lines.append(raw_display)
        lines.append("")

        # Parsed
        if signal:
            lines.append("Parsed:")
            lines.append(f"  symbol: {signal.symbol}")
            lines.append(f"  side: {signal.side.value}")
            lines.append(f"  entry: {signal.entry}")
            lines.append(f"  sl: {signal.sl}")
            lines.append(f"  tp: {signal.tp}")
            lines.append("")
        else:
            lines.append("Parsed: FAIL (could not parse)")
            lines.append("")

        # Market (skip if no market data, e.g. parse failure)
        if bid > 0 or ask > 0:
            lines.append("Market:")
            lines.append(f"  bid: {bid}  |  ask: {ask}")
            lines.append(f"  spread: {spread} pts")
            lines.append("")

        # Decision or Rejection
        if rejected:
            lines.append(f"❌ Rejected: {reject_reason}")
        elif decision is not None:
            dry_run = self.settings.runtime.dry_run
            lines.append("✅ Decision:")
            lines.append(f"  order_type: {decision.order_kind.value}")
            lines.append(f"  volume: {volume}")
            lines.append(f"  price: {request.get('price') if request else decision.price}")
            lines.append(f"  sl: {decision.sl}  |  tp: {decision.tp}")
            lines.append(f"  deviation: {request.get('deviation') if request else '?'}")
            lines.append(f"  dry_run: {dry_run}")

        msg = "\n".join(lines)
        self.alerter.send_debug_sync(msg)

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
            # Reply to user in source chat
            try:
                msg_id_int = int(message_id) if message_id else None
                if msg_id_int:
                    self.alerter.reply_to_message_sync(
                        chat_id, msg_id_int,
                        f"📋 **{cmd.command_type.value}**\n{summary}",
                    )
            except (ValueError, TypeError):
                pass
            # Admin log
            self.alerter.send_alert_sync(
                "command_response",
                f"📋 **{cmd.command_type.value}**\n{summary}",
            )
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
                channel_id=chat_id,
            )
            self.storage.store_event(
                fingerprint="",
                event_type="signal_parse_failed",
                details={"reason": result.reason, "message_id": message_id},
                channel_id=chat_id,
            )
            self._send_signal_debug(
                raw_text, None, 0.0, 0.0, None,
                rejected=True, reject_reason=f"parse failed: {result.reason}",
            )
            print(f"  [PIPELINE] parsed=FAIL reason=\"{result.reason}\"")
            return

        signal_obj: ParsedSignal = result
        fp = signal_obj.fingerprint

        # Count as parsed
        self._metrics.parsed += 1
        self._health.record_signal(symbol=signal_obj.symbol)
        self._get_ch_metrics(chat_id).parsed += 1

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
            self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": reason}, channel_id=signal_obj.source_chat_id)
            self._metrics.rejected += 1
            self._get_ch_metrics(signal_obj.source_chat_id).rejected += 1
            print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=REJECTED reason=\"{reason}\"")
            return

        # ── Step 2b: Daily risk guard check ───────────────────────
        if self.daily_guard:
            allowed, guard_reason = self.daily_guard.is_trading_allowed
            if not allowed:
                log_event("validation_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=guard_reason)
                self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": guard_reason}, channel_id=signal_obj.source_chat_id)
                self._metrics.rejected += 1
                self._get_ch_metrics(signal_obj.source_chat_id).rejected += 1
                print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=REJECTED reason=\"{guard_reason}\"")
                return

        # ── Step 2c: Exposure guard check ─────────────────────────
        if self.exposure_guard:
            exp_allowed, exp_reason = self.exposure_guard.is_allowed(signal_obj.symbol)
            if not exp_allowed:
                log_event("validation_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=exp_reason)
                self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": exp_reason}, channel_id=signal_obj.source_chat_id)
                self._metrics.rejected += 1
                self._get_ch_metrics(signal_obj.source_chat_id).rejected += 1
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
            except Exception as exc:
                log_event(
                    "pip_size_lookup_failed",
                    symbol=signal_obj.symbol,
                    error=str(exc),
                )
                # Fallback: assume 5-digit broker defaults
                point = 0.00001
                pip_size = 0.0001

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
            self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": vr.reason}, channel_id=signal_obj.source_chat_id)
            self._metrics.rejected += 1
            self._get_ch_metrics(signal_obj.source_chat_id).rejected += 1
            self._send_signal_debug(
                raw_text, signal_obj, bid, ask, current_spread,
                rejected=True, reject_reason=vr.reason,
            )
            print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=REJECTED reason=\"{vr.reason}\"")
            return

        # ── Step 6: Store signal ─────────────────────────────────
        self.storage.store_signal(signal_obj, SignalStatus.PARSED)

        # ── Step 7-9: Execute via Pipeline (P9) ──────────────────
        #    Pipeline handles single/range/scale_in modes, volume calc,
        #    order building, execution, and state management.
        if dry_run:
            balance = 10000.0
        else:
            account = self.executor.account_info()
            balance = account["balance"] if account else 0.0

        # Entry drift guard (check before pipeline execution)
        # Quick check: if single MARKET order would drift too far, reject early
        test_decision = self.order_builder.decide_order_type(signal_obj, bid, ask, point)
        if test_decision.order_kind == OrderKind.MARKET and signal_obj.entry is not None:
            drift_result = self.validator.validate_entry_drift(
                signal_obj, current_price, pip_size
            )
            if not drift_result.valid:
                log_event("drift_rejected", fingerprint=fp, symbol=signal_obj.symbol, reason=drift_result.reason)
                self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.REJECTED)
                self.storage.store_event(fingerprint=fp, event_type="signal_rejected", symbol=signal_obj.symbol, details={"reason": drift_result.reason}, channel_id=signal_obj.source_chat_id)
                self._metrics.rejected += 1
                self._get_ch_metrics(signal_obj.source_chat_id).rejected += 1
                self._send_signal_debug(
                    raw_text, signal_obj, bid, ask, current_spread,
                    rejected=True, reject_reason=f"entry drift: {drift_result.reason}",
                )
                print(f"  [PIPELINE] fp={fp} symbol={signal_obj.symbol} parsed=OK validated=OK order=MARKET drift=REJECTED reason=\"{drift_result.reason}\"")
                return

        # Delegate to SignalPipeline for execution (single or multi-order)
        results = self.signal_pipeline.execute_signal_plans(
            signal=signal_obj,
            bid=bid,
            ask=ask,
            point=point,
            balance=balance,
            current_spread=current_spread,
            dry_run=dry_run,
        )

        # Process results and update metrics
        latency_ms = int((time.monotonic() - t_start) * 1000)
        any_success = False
        any_failure = False

        for r in results:
            r_fp = r.get("fingerprint", fp)
            r_kind = r.get("order_kind", "MARKET")
            r_vol = r.get("volume", 0)
            r_decision = r.get("decision")
            r_request = r.get("request")

            if r.get("dry_run"):
                # Dry run path
                log_event(
                    "dry_run_execution", fingerprint=r_fp,
                    symbol=signal_obj.symbol, order_kind=r_kind,
                    volume=r_vol, level_id=r.get("level_id", 0),
                )
                any_success = True
                # Debug message for first result only
                if r.get("level_id", 0) == 0 and r_decision:
                    self._send_signal_debug(
                        raw_text, signal_obj, bid, ask, current_spread,
                        decision=r_decision, volume=r_vol, request=r_request,
                    )
                print(f"  [PIPELINE] fp={r_fp} symbol={signal_obj.symbol} order={r_kind} exec=DRY_RUN_OK vol={r_vol} level={r.get('level_id', 0)}")

            elif r.get("success"):
                any_success = True
                # Debug message for first result only
                if r.get("level_id", 0) == 0 and r_decision:
                    self._send_signal_debug(
                        raw_text, signal_obj, bid, ask, current_spread,
                        decision=r_decision, volume=r_vol, request=r_request,
                    )
                print(f"  [PIPELINE] fp={r_fp} symbol={signal_obj.symbol} order={r_kind} exec=SUCCESS ticket={r.get('ticket')} vol={r_vol} level={r.get('level_id', 0)}")

            else:
                any_failure = True
                print(f"  [PIPELINE] fp={r_fp} symbol={signal_obj.symbol} order={r_kind} exec=FAILED retcode={r.get('retcode')} level={r.get('level_id', 0)}")

        # Update signal status
        if any_success:
            self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.EXECUTED)
            self.storage.store_event(fingerprint=fp, event_type="signal_executed", symbol=signal_obj.symbol, details={"orders": len(results), "mode": self.channel_mgr.get_strategy(chat_id).get("mode", "single")}, channel_id=signal_obj.source_chat_id)
            self._metrics.executed += 1
            self._health.record_order()
            self._metrics.record_latency(latency_ms)
            self._get_ch_metrics(signal_obj.source_chat_id).executed += 1
        elif any_failure:
            self.storage.update_signal_status(signal_obj.fingerprint, SignalStatus.FAILED)
            self.storage.store_event(fingerprint=fp, event_type="signal_failed", symbol=signal_obj.symbol, details={"orders": len(results)}, channel_id=signal_obj.source_chat_id)
            self._metrics.failed += 1
            self._get_ch_metrics(signal_obj.source_chat_id).failed += 1

        # Log remaining TPs
        if len(signal_obj.tp) > 1:
            log_event("multi_tp_info", fingerprint=fp, symbol=signal_obj.symbol, remaining_tps=signal_obj.tp[1:])

        print(f"  [PIPELINE] fp={fp} total_orders={len(results)} latency={latency_ms}ms")

    def _process_edit(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Process an edited signal message.

        Flow:
        1. Look up original fingerprint by (chat_id, message_id).
        2. Check group status for filled orders (P10.1).
        3. Delegate to MessageUpdateHandler for decision.
        4. Act on decision:
           - IGNORE: log only.
           - CANCEL_GROUP_PENDING: cancel pending orders in group only.
           - CANCEL_ORDER: cancel pending order via lifecycle_mgr + re-process.
        """
        log_event("edit_received", source_chat_id=chat_id, source_message_id=message_id)

        # Step 1: Find original signal fingerprint
        original_fp = self.storage.get_fingerprint_by_message(chat_id, message_id)
        if not original_fp:
            log_event(
                "edit_no_original",
                source_chat_id=chat_id,
                source_message_id=message_id,
                reason="no signal found for this message",
            )
            return

        # Step 2: Check group for filled orders (P10.1)
        has_filled = False
        group = self.position_mgr.get_group(original_fp) if self.position_mgr else None
        if group:
            try:
                import MetaTrader5 as mt5
                for ticket in group.tickets:
                    positions = mt5.positions_get(ticket=ticket)
                    if positions and len(positions) > 0:
                        has_filled = True
                        break
            except ImportError:
                pass

        # Step 3: Delegate to handler
        decision = self.update_handler.handle_edit(
            edited_text=raw_text,
            source_chat_id=chat_id,
            source_message_id=message_id,
            original_fingerprint=original_fp,
            has_filled_orders=has_filled,
        )

        log_event(
            "edit_decision",
            action=decision.action.value,
            reason=decision.reason,
            original_fingerprint=original_fp,
            has_filled_orders=has_filled,
        )

        # Step 4: Act on decision
        if decision.action == UpdateAction.IGNORE:
            return

        if decision.action == UpdateAction.CANCEL_GROUP_PENDING:
            # P10.1: Cancel pending orders in group, keep filled running
            if self.position_mgr and not self.settings.runtime.dry_run:
                cancel_result = self.position_mgr.cancel_group_pending_orders(
                    original_fp,
                    executor=self.executor,
                )
                self.storage.store_event(
                    fingerprint=original_fp,
                    event_type="edit_group_pending_cancelled",
                    details={
                        "reason": decision.reason,
                        "cancelled": cancel_result["cancelled"],
                        "filled_kept": cancel_result["filled_kept"],
                    },
                    channel_id=chat_id,
                )
            return

        if decision.action == UpdateAction.CANCEL_ORDER:
            # Legacy: cancel via lifecycle manager (no group or no filled)
            if group and self.position_mgr and not self.settings.runtime.dry_run:
                # Use group-aware cancel for all pending
                self.position_mgr.cancel_group_pending_orders(
                    original_fp,
                    executor=self.executor,
                )
            elif self.lifecycle_mgr and not self.settings.runtime.dry_run:
                cancelled = self.lifecycle_mgr.cancel_by_fingerprint(original_fp)
                log_event(
                    "edit_cancel_attempted",
                    fingerprint=original_fp,
                    cancelled=cancelled,
                )

            self.storage.store_event(
                fingerprint=original_fp,
                event_type="edit_order_cancelled",
                details={"reason": decision.reason},
                channel_id=chat_id,
            )

            # If handler also produced a new signal, re-process it
            if decision.new_signal:
                log_event(
                    "edit_reprocess",
                    fingerprint=original_fp,
                    new_fingerprint=decision.new_signal.fingerprint,
                )
                self._do_process_signal(raw_text, chat_id, message_id)

    # ── Delete Handler (P10.1) ────────────────────────────────────

    def _process_delete(
        self,
        chat_id: str,
        message_ids: list[str],
    ) -> None:
        """Handle deleted signal messages.

        For each deleted message:
        1. Look up fingerprint by (chat_id, message_id).
        2. If group exists → cancel pending orders only.
        3. If no group → cancel via lifecycle_mgr.
        4. Log event.
        """
        for message_id in message_ids:
            fp = self.storage.get_fingerprint_by_message(chat_id, message_id)
            if not fp:
                continue

            log_event(
                "delete_signal_detected",
                fingerprint=fp,
                source_chat_id=chat_id,
                source_message_id=message_id,
            )

            if self.settings.runtime.dry_run:
                self.storage.store_event(
                    fingerprint=fp,
                    event_type="delete_signal_dry_run",
                    details={"message_id": message_id},
                    channel_id=chat_id,
                )
                continue

            # Try group-aware cancel first
            group = self.position_mgr.get_group(fp) if self.position_mgr else None
            if group:
                cancel_result = self.position_mgr.cancel_group_pending_orders(
                    fp,
                    executor=self.executor,
                )
                self.storage.store_event(
                    fingerprint=fp,
                    event_type="delete_group_pending_cancelled",
                    details={
                        "cancelled": cancel_result["cancelled"],
                        "filled_kept": cancel_result["filled_kept"],
                        "group_completed": cancel_result["group_completed"],
                    },
                    channel_id=chat_id,
                )
            elif self.lifecycle_mgr:
                # Legacy fallback: cancel single pending order by fingerprint
                cancelled = self.lifecycle_mgr.cancel_by_fingerprint(fp)
                self.storage.store_event(
                    fingerprint=fp,
                    event_type="delete_order_cancelled",
                    details={"cancelled": cancelled},
                    channel_id=chat_id,
                )

    # ── Reply Handler ─────────────────────────────────────────────

    def _process_reply(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
        reply_to_msg_id: str,
    ) -> None:
        """Handle a reply to a previously processed signal.

        Flow:
        1. Lookup ALL orders by (chat_id, reply_to_msg_id).
        2. Channel guard: filter orders matching current chat.
        3. Parse reply text as a trade action.
        4. Execute on each matching ticket (with position check).
        5. Reply with grouped results.
        """
        try:
            self._do_process_reply(raw_text, chat_id, message_id, reply_to_msg_id)
        except Exception as exc:
            log_event(
                "reply_handler_error",
                source_chat_id=chat_id,
                source_message_id=message_id,
                reply_to=reply_to_msg_id,
                error=str(exc),
            )

    def _do_process_reply(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
        reply_to_msg_id: str,
    ) -> None:
        """Internal reply processing logic."""
        dry_run = self.settings.runtime.dry_run

        # Step 1: Lookup ALL orders for the original signal message
        orders = self.storage.get_orders_by_message(chat_id, reply_to_msg_id)
        if not orders:
            log_event(
                "reply_no_orders",
                source_chat_id=chat_id,
                reply_to=reply_to_msg_id,
            )
            try:
                msg_id_int = int(message_id) if message_id else None
                if msg_id_int:
                    self.alerter.reply_to_message_sync(
                        chat_id, msg_id_int,
                        "⚠️ No active trade found for this message",
                    )
            except (ValueError, TypeError):
                pass
            return

        # Step 2: Channel guard + success filter
        orders = [
            o for o in orders
            if o["channel_id"] == chat_id and o["success"]
        ]
        if not orders:
            log_event(
                "reply_no_matching_orders",
                source_chat_id=chat_id,
                reply_to=reply_to_msg_id,
                reason="no successful orders from this channel",
            )
            return

        # Step 3: Parse reply text as action
        action = self.reply_parser.parse(raw_text)
        if not action:
            # Not an actionable reply — just a comment, skip silently
            log_event(
                "reply_not_action",
                source_chat_id=chat_id,
                reply_to=reply_to_msg_id,
                text_preview=raw_text[:80],
            )
            return

        log_event(
            "reply_action_parsed",
            action=action.action.value,
            price=action.price,
            percent=action.percent,
            source_chat_id=chat_id,
            reply_to=reply_to_msg_id,
        )

        # Step 4: Execute on each order
        # ── P10f: Group-aware selective close ────────────────────
        # If this is a CLOSE action and there's a group with selective
        # strategy, route through PositionManager instead of closing all.
        if (
            action.action == ReplyActionType.CLOSE
            and hasattr(self, "position_mgr")
            and self.position_mgr
        ):
            # Try to find group by first order's fingerprint
            first_fp = orders[0]["fingerprint"]
            # Strip level suffix to get base fingerprint
            base_fp = first_fp.split(":L")[0] if ":L" in first_fp else first_fp
            group = self.position_mgr.get_group(base_fp)

            if group and group.reply_close_strategy != "all":
                # Selective close: close ONE order based on strategy
                result = self.position_mgr.close_selective_entry(
                    base_fp,
                    reply_executor=self.reply_executor,
                    dry_run=dry_run,
                )
                if result and result.get("status") == "closed":
                    ticket = result["ticket"]
                    remaining = result["remaining_count"]
                    total = result["total_count"]
                    entry_price = result["entry_price"]

                    # Mark for TradeTracker suppression
                    if self.trade_tracker and not dry_run:
                        self.trade_tracker.mark_reply_closed(ticket)

                    msg = (
                        f"📋 **CLOSE** (selective: {group.reply_close_strategy})\n"
                        f"✅ Closed #{ticket} (entry {entry_price})\n"
                        f"Remaining: {remaining}/{total} orders"
                    )
                    try:
                        msg_id_int = int(message_id) if message_id else None
                        if msg_id_int:
                            self.alerter.reply_to_message_sync(chat_id, msg_id_int, msg)
                    except (ValueError, TypeError):
                        pass
                    self.alerter.send_alert_sync("reply_command", msg)
                    print(f"  [REPLY] selective_close → #{ticket}, {remaining} remaining")
                    return
                elif result and result.get("status") == "no_open_orders":
                    # All orders already closed
                    pass  # Fall through to existing logic

        # ── Original close-all logic (for strategy="all" or no group) ─
        success_results: list[str] = []
        skipped_tickets: list[str] = []

        for order in orders:
            ticket = order["ticket"]
            fp = order["fingerprint"]
            symbol = order["symbol"]

            log_event(
                "reply_action",
                fingerprint=fp,
                ticket=ticket,
                symbol=symbol,
                action=action.action.value,
                chat_id=chat_id,
            )

            summary = self.reply_executor.execute(
                ticket, action,
                expected_symbol=symbol,
                dry_run=dry_run,
            )

            if summary.startswith("⚠️"):
                skipped_tickets.append(f"#{ticket}")
            else:
                success_results.append(f"#{ticket}: {summary}")

            # Mark for TradeTracker suppression
            if (
                action.action in (ReplyActionType.CLOSE, ReplyActionType.CLOSE_PARTIAL)
                and self.trade_tracker
                and not dry_run
            ):
                self.trade_tracker.mark_reply_closed(ticket)

            self.storage.store_event(
                fingerprint=fp,
                event_type="reply_executed",
                symbol=symbol,
                details={
                    "action": action.action.value,
                    "ticket": ticket,
                    "summary": summary,
                },
                channel_id=chat_id,
            )

        # Step 5: Aggregated reply
        parts: list[str] = []
        if success_results:
            parts.append("✅ " + "\n".join(success_results))
        if skipped_tickets:
            parts.append(f"⏭ Already closed: {', '.join(skipped_tickets)}")

        if parts:
            msg = f"📋 **{action.action.value.upper()}**\n" + "\n".join(parts)
            try:
                msg_id_int = int(message_id) if message_id else None
                if msg_id_int:
                    self.alerter.reply_to_message_sync(chat_id, msg_id_int, msg)
            except (ValueError, TypeError):
                pass
            # Admin log
            self.alerter.send_alert_sync("reply_command", msg)
            print(f"  [REPLY] {action.action.value} → {len(success_results)} ok, {len(skipped_tickets)} skipped")

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

        # Per-channel breakdown (if multi-channel)
        if len(self._channel_metrics) > 1:
            for ch_id, ch_m in sorted(self._channel_metrics.items()):
                ch_name = self.channel_mgr.get_channel_name(ch_id) if self.channel_mgr else ch_id
                print(f"             [{ch_name}] {ch_m.as_summary()}")
                log_event(
                    "heartbeat_channel",
                    channel_id=ch_id,
                    channel_name=ch_name,
                    parsed=ch_m.parsed,
                    executed=ch_m.executed,
                    rejected=ch_m.rejected,
                    failed=ch_m.failed,
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

            # R4 fix: Restore position groups AFTER MT5 is initialized
            if self.position_mgr:
                self.position_mgr.restore_groups()
        else:
            print("[DRY RUN] MT5 execution disabled — simulating orders.")

        # Banner
        s = self.settings
        print("=" * 55)
        print(f"  telegram-mt5-bot  v0.9.0  {'[DRY RUN]' if dry_run else '[LIVE]'}")
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
            if self.trade_tracker:
                await self.trade_tracker.start()
            # P9: Rebuild active signals from DB and start range monitor
            if self._state_mgr:
                restored = self._state_mgr.rebuild_from_db()
                if restored > 0:
                    print(f"  [P9] Restored {restored} active signals from DB")
            if self.range_monitor:
                await self.range_monitor.start()

        # Health check server
        if self._health_server:
            await self._health_server.start()

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

        # P9: Stop range monitor
        if self.range_monitor:
            await self.range_monitor.stop()
        if self.daily_guard:
            await self.daily_guard.stop()
        if self.position_mgr:
            await self.position_mgr.stop()
        if self.trade_tracker:
            await self.trade_tracker.stop()
        if self._health_server:
            await self._health_server.stop()
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
