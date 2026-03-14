"""
main.py

Startup orchestration for telegram-mt5-bot.
Full pipeline: Telegram → Parser → Validator → Risk → Order Builder → Executor → Storage.
"""

from __future__ import annotations

import asyncio
import signal
import sys

from config.settings import load_settings
from core.models import ParsedSignal, ParseFailure, Side, SignalStatus
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
from utils.logger import setup_logger, log_event
from utils.symbol_mapper import SymbolMapper


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

        # Validator
        self.validator = SignalValidator(
            max_entry_distance_points=s.safety.max_entry_distance_points,
            signal_age_ttl_seconds=s.safety.signal_age_ttl_seconds,
            max_spread_points=s.safety.max_spread_points,
            max_open_trades=s.safety.max_open_trades,
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

        # Order Builder
        self.order_builder = OrderBuilder()

        # Trade Executor
        self.executor = TradeExecutor(
            mt5_path=s.mt5.path,
            login=s.mt5.login,
            password=s.mt5.password,
            server=s.mt5.server,
        )

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
        )
        self.listener.set_pipeline_callback(self._process_signal)
        self.listener.set_edit_callback(self._process_edit)

        # Lifecycle Manager
        self.lifecycle_mgr = OrderLifecycleManager(
            executor=self.executor,
            ttl_minutes=s.safety.pending_order_ttl_minutes,
        )

        # MT5 Watchdog
        self.watchdog = MT5Watchdog(executor=self.executor)

    def _process_signal(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Process a new signal message through the full pipeline.

        Flow:
        1. Parse raw text.
        2. Check duplicate.
        3. Validate signal (SL/TP, spread, max trades, age, distance).
        4. Calculate volume.
        5. Build order.
        6. Execute order.
        7. Store results.
        """
        # Step 1: Parse
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
                event_type="parse_failed",
                details={"reason": result.reason, "message_id": message_id},
            )
            return

        signal_obj: ParsedSignal = result
        fp = signal_obj.fingerprint

        log_event(
            "parse_success",
            fingerprint=fp,
            symbol=signal_obj.symbol,
            side=signal_obj.side.value,
            entry=signal_obj.entry,
        )

        # Step 2: Check duplicate
        is_dup = self.storage.is_duplicate(
            fp,
            ttl_seconds=self.settings.safety.signal_age_ttl_seconds,
        )

        # Step 3: Get live market data
        tick = self.executor.get_tick(signal_obj.symbol)
        current_price = None
        current_spread = None
        bid, ask = 0.0, 0.0

        if tick:
            bid = tick.bid
            ask = tick.ask
            current_spread = tick.spread_points
            current_price = ask if signal_obj.side == Side.BUY else bid

        open_positions = self.executor.positions_total()

        # Step 4: Validate
        vr = self.validator.validate(
            signal_obj,
            current_price=current_price,
            current_spread=current_spread,
            open_positions=open_positions,
            is_duplicate=is_dup,
        )

        if not vr.valid:
            log_event(
                "validation_rejected",
                fingerprint=fp,
                symbol=signal_obj.symbol,
                reason=vr.reason,
            )
            self.storage.store_signal(signal_obj, SignalStatus.REJECTED)
            self.storage.store_event(
                fingerprint=fp,
                event_type="validation_rejected",
                symbol=signal_obj.symbol,
                details={"reason": vr.reason},
            )
            return

        # Step 5: Store signal as parsed
        self.storage.store_signal(signal_obj, SignalStatus.PARSED)

        # Step 6: Calculate volume
        account = self.executor.account_info()
        balance = account["balance"] if account else 0.0
        volume = self.risk_manager.calculate_volume(
            balance=balance,
            entry=signal_obj.entry,
            sl=signal_obj.sl,
        )

        # Step 7: Build order
        symbol_info = None
        try:
            import MetaTrader5 as mt5
            symbol_info = mt5.symbol_info(signal_obj.symbol)
        except Exception:
            pass
        point = symbol_info.point if symbol_info and symbol_info.point > 0 else 0.00001

        decision = self.order_builder.decide_order_type(
            signal_obj, bid, ask, point,
        )
        request = self.order_builder.build_request(
            signal_obj, decision, volume, bid, ask,
        )

        log_event(
            "order_submitted",
            fingerprint=fp,
            symbol=signal_obj.symbol,
            order_kind=decision.order_kind.value,
            volume=volume,
            price=request.get("price"),
        )
        self.storage.update_signal_status(fp, SignalStatus.SUBMITTED)

        # Step 8: Execute
        exec_result = self.executor.execute(request, fingerprint=fp)

        if exec_result.success:
            self.storage.update_signal_status(fp, SignalStatus.EXECUTED)
            self.storage.store_order(
                ticket=exec_result.ticket,
                fingerprint=fp,
                order_kind=decision.order_kind.value,
                price=request.get("price"),
                sl=decision.sl,
                tp=decision.tp,
                retcode=exec_result.retcode,
                success=True,
            )
            # Log remaining TPs for manual management
            if len(signal_obj.tp) > 1:
                log_event(
                    "multi_tp_info",
                    fingerprint=fp,
                    symbol=signal_obj.symbol,
                    remaining_tps=signal_obj.tp[1:],
                    note="Only TP1 sent to MT5. Remaining TPs logged for manual management.",
                )
        else:
            self.storage.update_signal_status(fp, SignalStatus.FAILED)
            self.storage.store_order(
                ticket=None,
                fingerprint=fp,
                order_kind=decision.order_kind.value,
                price=request.get("price"),
                sl=decision.sl,
                tp=decision.tp,
                retcode=exec_result.retcode,
                success=False,
            )

        log_event(
            "order_result",
            fingerprint=fp,
            symbol=signal_obj.symbol,
            success=exec_result.success,
            retcode=exec_result.retcode,
            ticket=exec_result.ticket,
            message=exec_result.message,
        )

    def _process_edit(
        self,
        raw_text: str,
        chat_id: str,
        message_id: str,
    ) -> None:
        """Process an edited message via MessageUpdateHandler.

        TODO: Retrieve original fingerprint from storage by message_id.
        For now, re-parse and compare fingerprints.
        """
        # TODO: Look up original fingerprint by source_message_id in storage
        log_event(
            "edit_received",
            source_chat_id=chat_id,
            source_message_id=message_id,
        )

    async def run(self) -> None:
        """Start the bot and run until interrupted."""
        self._init_components()

        # Init MT5
        if not self.executor.init_mt5():
            print("[FATAL] MT5 initialization failed. Check .env credentials.")
            return

        print("=" * 50)
        print("  telegram-mt5-bot  v0.2.0")
        print("=" * 50)
        print(f"  Risk mode  : {self.settings.risk.mode}")
        print(f"  Max spread : {self.settings.safety.max_spread_points} pts")
        print(f"  Signal TTL : {self.settings.safety.signal_age_ttl_seconds}s")
        print(f"  Pending TTL: {self.settings.safety.pending_order_ttl_minutes}min")
        print(f"  Max trades : {self.settings.safety.max_open_trades}")
        print("=" * 50)

        # Start Telegram listener
        await self.listener.start()

        # Start background services
        await self.lifecycle_mgr.start()
        await self.watchdog.start()

        log_event("system_ready")
        print("\n[INFO] Bot is running. Ctrl+C to stop.")

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

        if self.watchdog:
            await self.watchdog.stop()
        if self.lifecycle_mgr:
            await self.lifecycle_mgr.stop()
        if self.listener:
            await self.listener.stop()
        if self.executor:
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
