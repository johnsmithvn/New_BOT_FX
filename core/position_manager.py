"""
core/position_manager.py

Background position manager for open trades.

Runs a poll loop checking open positions against configurable rules:
  - Breakeven: move SL to entry + lock when profit >= trigger
  - Trailing stop: trail SL at fixed pip distance from current price
  - Partial close: close a percentage of volume at TP1

All features default to 0 = disabled. Only active in live mode.
"""

from __future__ import annotations

import asyncio
import time as _time
from typing import TYPE_CHECKING

from utils.logger import log_event

if TYPE_CHECKING:
    from core.trade_executor import TradeExecutor
    from config.settings import Settings
    from core.channel_manager import ChannelManager
    from core.storage import Storage
    from core.telegram_alerter import TelegramAlerter


class PositionManager:
    """Monitor and manage open positions for breakeven and trailing stop.

    Runs as a background asyncio task, polling MT5 positions
    every POSITION_MANAGER_POLL_SECONDS.

    Per-channel rules: if a position's ticket is mapped to a channel_id,
    uses channel-specific rules from ChannelManager. Falls back to global
    settings for unknown positions (pre-v0.6.0 or unmapped).
    """

    def __init__(
        self,
        executor: TradeExecutor,
        settings: Settings,
        channel_manager: ChannelManager | None = None,
        storage: Storage | None = None,
        alerter: TelegramAlerter | None = None,
    ) -> None:
        self._executor = executor
        self._storage = storage
        self._alerter = alerter

        # Global defaults — used as fallback when no channel config exists
        self._breakeven_trigger_pips: float = settings.safety.breakeven_trigger_pips
        self._breakeven_lock_pips: float = settings.safety.breakeven_lock_pips
        self._trailing_stop_pips: float = settings.safety.trailing_stop_pips
        self._partial_close_percent: int = settings.safety.partial_close_percent
        self._poll_seconds: int = settings.safety.position_manager_poll_seconds
        self._magic: int = settings.execution.bot_magic_number

        # Per-channel support
        self._channel_manager = channel_manager
        self._ticket_to_channel: dict[int, str] = {}

        # Track which positions we've already partially closed
        self._partially_closed: set[int] = set()
        # Track which positions we've already moved to breakeven
        self._breakeven_applied: set[int] = set()

        self._poll_task: asyncio.Task | None = None

        # Alert throttle: (ticket, event_type) -> last_alert_epoch
        self._last_alert_time: dict[tuple[int, str], float] = {}
        self._ALERT_COOLDOWN = 60  # seconds per (ticket, event_type)
        self._TRAILING_ALERT_MIN_PIPS = 5.0  # only alert if SL moved >= 5 pips
        self._last_trailing_sl: dict[int, float] = {}  # ticket -> last alerted SL

    @property
    def is_enabled(self) -> bool:
        """True if at least one position management feature is configured."""
        return (
            self._breakeven_trigger_pips > 0
            or self._trailing_stop_pips > 0
            or self._partial_close_percent > 0
        )

    async def start(self) -> None:
        """Start the background poll loop."""
        if not self.is_enabled:
            log_event("position_manager_disabled")
            return

        # Rebuild ticket→channel cache from DB on startup
        self._rebuild_cache()

        self._poll_task = asyncio.create_task(self._poll_loop())
        log_event(
            "position_manager_started",
            breakeven_trigger_pips=self._breakeven_trigger_pips,
            breakeven_lock_pips=self._breakeven_lock_pips,
            trailing_stop_pips=self._trailing_stop_pips,
            partial_close_percent=self._partial_close_percent,
            poll_seconds=self._poll_seconds,
            cached_tickets=len(self._ticket_to_channel),
        )

    async def stop(self) -> None:
        """Stop the background poll loop."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        log_event("position_manager_stopped")

    async def _poll_loop(self) -> None:
        """Poll MT5 positions and apply management rules."""
        while True:
            try:
                await asyncio.sleep(self._poll_seconds)
                self._check_positions()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("position_manager_error", error=str(exc))

    # ── Cache Management ─────────────────────────────────────────

    def register_ticket(self, ticket: int, channel_id: str) -> None:
        """Register a ticket→channel mapping after order execution.

        Called from the pipeline after successful order execution.
        """
        if ticket and channel_id:
            self._ticket_to_channel[ticket] = channel_id

    def _rebuild_cache(self) -> None:
        """Rebuild ticket→channel cache from DB on startup.

        Ensures positions opened before restart retain their channel context.
        """
        if not self._storage:
            return
        try:
            mapping = self._storage.get_open_tickets()
            self._ticket_to_channel.update(mapping)
            log_event(
                "position_manager_cache_rebuilt",
                tickets=len(mapping),
            )
        except Exception as exc:
            log_event(
                "position_manager_cache_error",
                error=str(exc),
            )

    def _get_rules_for_ticket(self, ticket: int) -> dict:
        """Get position management rules for a specific ticket.

        Looks up channel_id from cache, then gets channel-specific rules.
        Falls back to global defaults if no channel mapping or no ChannelManager.
        """
        defaults = {
            "breakeven_trigger_pips": self._breakeven_trigger_pips,
            "breakeven_lock_pips": self._breakeven_lock_pips,
            "trailing_stop_pips": self._trailing_stop_pips,
            "partial_close_percent": self._partial_close_percent,
        }

        if not self._channel_manager:
            return defaults

        channel_id = self._ticket_to_channel.get(ticket)
        if not channel_id:
            return defaults

        channel_rules = self._channel_manager.get_rules(channel_id)
        # Merge: channel rules override defaults
        merged = dict(defaults)
        for key in defaults:
            if key in channel_rules:
                merged[key] = channel_rules[key]
        return merged

    def _check_positions(self) -> None:
        """Check all open positions and apply rules."""
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return

        positions = mt5.positions_get()
        if positions is None:
            return

        # Only manage positions opened by this bot
        bot_positions = [p for p in positions if p.magic == self._magic]

        for pos in bot_positions:
            symbol_info = mt5.symbol_info(pos.symbol)
            if not symbol_info or symbol_info.point <= 0:
                continue

            point = symbol_info.point
            digits = symbol_info.digits
            pip_size = point * 10  # 1 pip = 10 points for 5-digit/3-digit brokers

            # Current profit in pips
            if pos.type == 0:  # BUY
                tick = mt5.symbol_info_tick(pos.symbol)
                if not tick:
                    continue
                current_price = tick.bid
                profit_pips = (current_price - pos.price_open) / pip_size
            elif pos.type == 1:  # SELL
                tick = mt5.symbol_info_tick(pos.symbol)
                if not tick:
                    continue
                current_price = tick.ask
                profit_pips = (pos.price_open - current_price) / pip_size
            else:
                continue

            # Get per-channel rules for this position
            rules = self._get_rules_for_ticket(pos.ticket)

            # Breakeven
            be_trigger = rules["breakeven_trigger_pips"]
            be_lock = rules["breakeven_lock_pips"]
            if be_trigger > 0:
                self._apply_breakeven(
                    mt5, pos, profit_pips, pip_size, point, digits,
                    trigger_pips=be_trigger, lock_pips=be_lock,
                )

            # Trailing stop
            trail_pips = rules["trailing_stop_pips"]
            if trail_pips > 0:
                self._apply_trailing_stop(
                    mt5, pos, current_price, profit_pips, pip_size, point, digits,
                    trail_pips=trail_pips,
                )

            # Partial close
            pc_percent = rules["partial_close_percent"]
            if pc_percent > 0:
                self._apply_partial_close(
                    mt5, pos, profit_pips, symbol_info,
                    close_percent=pc_percent,
                )

    def _apply_breakeven(
        self, mt5, pos, profit_pips: float,
        pip_size: float, point: float, digits: int,
        trigger_pips: float = 0, lock_pips: float = 0,
    ) -> None:
        """Move SL to entry + lock pips when profit reaches trigger."""
        if pos.ticket in self._breakeven_applied:
            return

        if profit_pips < trigger_pips:
            return

        # Calculate breakeven SL
        lock_distance = lock_pips * pip_size

        if pos.type == 0:  # BUY
            new_sl = pos.price_open + lock_distance
            # Only move if new SL is better than current
            if pos.sl > 0 and new_sl <= pos.sl:
                return
        else:  # SELL
            new_sl = pos.price_open - lock_distance
            if pos.sl > 0 and new_sl >= pos.sl:
                return

        new_sl = round(new_sl, digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": pos.tp,
        }

        result = mt5.order_send(request)
        if result and result.retcode in (10008, 10009):
            self._breakeven_applied.add(pos.ticket)
            log_event(
                "breakeven_applied",
                ticket=pos.ticket,
                symbol=pos.symbol,
                new_sl=new_sl,
                profit_pips=round(profit_pips, 1),
            )
            self._send_position_alert(
                pos.ticket, "breakeven_alert", pos.symbol,
                f"🔒 **Breakeven** on `{pos.symbol}` #{pos.ticket}\n"
                f"SL moved to {new_sl} (+{lock_pips}p lock)",
            )
        else:
            retcode = result.retcode if result else -1
            log_event(
                "breakeven_failed",
                ticket=pos.ticket,
                symbol=pos.symbol,
                retcode=retcode,
            )

    def _apply_trailing_stop(
        self, mt5, pos, current_price: float,
        profit_pips: float, pip_size: float, point: float, digits: int,
        trail_pips: float = 0,
    ) -> None:
        """Trail SL at fixed pip distance from current price."""
        # Only trail when in profit
        if profit_pips <= 0:
            return

        trail_distance = trail_pips * pip_size

        if pos.type == 0:  # BUY
            new_sl = current_price - trail_distance
            # Only move SL up, never down
            if pos.sl > 0 and new_sl <= pos.sl:
                return
            # Don't trail below entry
            if new_sl < pos.price_open:
                return
        else:  # SELL
            new_sl = current_price + trail_distance
            # Only move SL down, never up
            if pos.sl > 0 and new_sl >= pos.sl:
                return
            # Don't trail above entry
            if new_sl > pos.price_open:
                return

        new_sl = round(new_sl, digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": pos.tp,
        }

        result = mt5.order_send(request)
        if result and result.retcode in (10008, 10009):
            log_event(
                "trailing_stop_moved",
                ticket=pos.ticket,
                symbol=pos.symbol,
                new_sl=new_sl,
                profit_pips=round(profit_pips, 1),
            )
            # Only alert if SL moved significantly
            pip_size = point * 10
            last_sl = self._last_trailing_sl.get(pos.ticket)
            if last_sl is None or abs(new_sl - last_sl) / pip_size >= self._TRAILING_ALERT_MIN_PIPS:
                self._last_trailing_sl[pos.ticket] = new_sl
                self._send_position_alert(
                    pos.ticket, "trailing_alert", pos.symbol,
                    f"📐 **Trailing SL** on `{pos.symbol}` #{pos.ticket}\n"
                    f"SL → {new_sl} (profit: {round(profit_pips, 1)}p)",
                )

    def _apply_partial_close(
        self, mt5, pos, profit_pips: float, symbol_info,
        close_percent: int = 0,
    ) -> None:
        """Close a percentage of volume when first TP is reached."""
        if pos.ticket in self._partially_closed:
            return

        # Only partial close when position has a TP set and is in profit
        if pos.tp <= 0 or profit_pips <= 0:
            return

        # Check if price has reached TP zone (within 1 pip)
        tp_distance_pips = abs(pos.tp - (mt5.symbol_info_tick(pos.symbol).bid
                              if pos.type == 0 else
                              mt5.symbol_info_tick(pos.symbol).ask))
        pip_size = symbol_info.point * 10
        if tp_distance_pips / pip_size > 1.0:
            # Not near TP yet
            return

        # Calculate partial volume
        close_volume = pos.volume * (close_percent / 100.0)
        close_volume = max(symbol_info.volume_min, close_volume)
        close_volume = round(
            close_volume / symbol_info.volume_step
        ) * symbol_info.volume_step
        close_volume = round(close_volume, 2)

        if close_volume <= 0:
            return

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": close_volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "deviation": 20,
            "magic": self._magic,
            "comment": f"partial_close:{pos.ticket}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        tick = mt5.symbol_info_tick(pos.symbol)
        if tick:
            request["price"] = tick.bid if pos.type == 0 else tick.ask

        result = mt5.order_send(request)
        if result and result.retcode in (10008, 10009, 10010):
            self._partially_closed.add(pos.ticket)
            log_event(
                "partial_close_executed",
                ticket=pos.ticket,
                symbol=pos.symbol,
                closed_volume=close_volume,
                remaining_volume=round(pos.volume - close_volume, 2),
                percent=close_percent,
            )
            self._send_position_alert(
                pos.ticket, "partial_close_alert", pos.symbol,
                f"✂️ **Partial Close** on `{pos.symbol}` #{pos.ticket}\n"
                f"Closed {close_volume} lots ({close_percent}%)",
            )
        else:
            retcode = result.retcode if result else -1
            log_event(
                "partial_close_failed",
                ticket=pos.ticket,
                symbol=pos.symbol,
                retcode=retcode,
            )

    # ── Alert helpers ─────────────────────────────────────────────

    def _should_alert(self, ticket: int, event_type: str) -> bool:
        """Check per-ticket cooldown for alert throttling."""
        key = (ticket, event_type)
        now = _time.time()
        last = self._last_alert_time.get(key, 0.0)
        if (now - last) < self._ALERT_COOLDOWN:
            return False
        self._last_alert_time[key] = now
        return True

    def _send_position_alert(
        self, ticket: int, alert_type: str, symbol: str, message: str,
    ) -> None:
        """Send throttled alert with channel context."""
        if not self._alerter or not self._should_alert(ticket, alert_type):
            return

        # Add channel context if available
        channel_id = self._ticket_to_channel.get(ticket)
        if channel_id and self._channel_manager:
            ch_name = self._channel_manager.get_channel_name(channel_id)
            message = f"[{ch_name}] {message}"

        self._alerter.send_alert_sync(alert_type, message)
