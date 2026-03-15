"""
core/command_executor.py

Execute parsed management commands against MT5.

Handles: CLOSE_ALL, CLOSE_SYMBOL, CLOSE_HALF, MOVE_SL, BREAKEVEN.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.command_parser import ManagementCommand, CommandType
from utils.logger import log_event

if TYPE_CHECKING:
    from config.settings import Settings


class CommandExecutor:
    """Execute management commands against MT5 positions.

    Each command operates on positions matching the bot's magic number.
    Returns a summary string for Telegram response.
    """

    def __init__(self, magic: int = 234000) -> None:
        self._magic = magic

    def execute(self, command: ManagementCommand) -> str:
        """Execute a management command.

        Returns:
            Summary string describing what was done.
        """
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return "❌ MetaTrader5 not available"

        handlers = {
            CommandType.CLOSE_ALL: self._close_all,
            CommandType.CLOSE_SYMBOL: self._close_symbol,
            CommandType.CLOSE_HALF: self._close_half,
            CommandType.MOVE_SL: self._move_sl,
            CommandType.BREAKEVEN: self._breakeven,
        }

        handler = handlers.get(command.command_type)
        if not handler:
            return f"❌ Unknown command: {command.command_type}"

        try:
            return handler(mt5, command)
        except Exception as exc:
            log_event("command_execution_error", error=str(exc),
                      command=command.command_type.value)
            return f"❌ Command failed: {exc}"

    def _get_bot_positions(self, mt5, symbol: str | None = None) -> list:
        """Get positions opened by this bot, optionally filtered by symbol."""
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        return [p for p in positions if p.magic == self._magic]

    def _close_position(self, mt5, pos) -> bool:
        """Close a single position."""
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": tick.bid if pos.type == 0 else tick.ask,
            "deviation": 20,
            "magic": self._magic,
            "comment": "cmd_close",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        success = result is not None and result.retcode in (10008, 10009, 10010)

        log_event(
            "command_close_position",
            ticket=pos.ticket,
            symbol=pos.symbol,
            volume=pos.volume,
            success=success,
            retcode=result.retcode if result else -1,
        )
        return success

    def _close_all(self, mt5, command: ManagementCommand) -> str:
        """Close all bot positions."""
        positions = self._get_bot_positions(mt5)
        if not positions:
            return "ℹ️ No open positions to close."

        closed = 0
        failed = 0
        for pos in positions:
            if self._close_position(mt5, pos):
                closed += 1
            else:
                failed += 1

        return (
            f"✅ Closed {closed}/{len(positions)} positions"
            f"{f' ({failed} failed)' if failed else ''}"
        )

    def _close_symbol(self, mt5, command: ManagementCommand) -> str:
        """Close all bot positions for a specific symbol."""
        symbol = command.symbol
        positions = self._get_bot_positions(mt5, symbol=symbol)
        if not positions:
            return f"ℹ️ No open positions for {symbol}."

        closed = 0
        failed = 0
        for pos in positions:
            if self._close_position(mt5, pos):
                closed += 1
            else:
                failed += 1

        return (
            f"✅ Closed {closed}/{len(positions)} {symbol} positions"
            f"{f' ({failed} failed)' if failed else ''}"
        )

    def _close_half(self, mt5, command: ManagementCommand) -> str:
        """Close 50% of each bot position volume."""
        positions = self._get_bot_positions(mt5)
        if not positions:
            return "ℹ️ No open positions to close."

        closed = 0
        failed = 0
        for pos in positions:
            symbol_info = mt5.symbol_info(pos.symbol)
            if not symbol_info:
                failed += 1
                continue

            half_volume = pos.volume * 0.5
            half_volume = max(symbol_info.volume_min, half_volume)
            half_volume = round(
                half_volume / symbol_info.volume_step
            ) * symbol_info.volume_step
            half_volume = round(half_volume, 2)

            if half_volume <= 0:
                failed += 1
                continue

            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                failed += 1
                continue

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": half_volume,
                "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": pos.ticket,
                "price": tick.bid if pos.type == 0 else tick.ask,
                "deviation": 20,
                "magic": self._magic,
                "comment": "cmd_half_close",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result and result.retcode in (10008, 10009, 10010):
                closed += 1
                log_event(
                    "command_half_close",
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    closed_volume=half_volume,
                )
            else:
                failed += 1

        return (
            f"✅ Half-closed {closed}/{len(positions)} positions"
            f"{f' ({failed} failed)' if failed else ''}"
        )

    def _move_sl(self, mt5, command: ManagementCommand) -> str:
        """Move SL to a specific price on all bot positions."""
        new_sl = command.price
        if new_sl is None:
            return "❌ No price specified for MOVE SL."

        positions = self._get_bot_positions(mt5)
        if not positions:
            return "ℹ️ No open positions."

        moved = 0
        failed = 0
        for pos in positions:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "sl": new_sl,
                "tp": pos.tp,
            }

            result = mt5.order_send(request)
            if result and result.retcode in (10008, 10009):
                moved += 1
                log_event(
                    "command_move_sl",
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    new_sl=new_sl,
                )
            else:
                failed += 1

        return (
            f"✅ Moved SL to {new_sl} on {moved}/{len(positions)} positions"
            f"{f' ({failed} failed)' if failed else ''}"
        )

    def _breakeven(self, mt5, command: ManagementCommand) -> str:
        """Move SL to entry on all profitable bot positions."""
        positions = self._get_bot_positions(mt5)
        if not positions:
            return "ℹ️ No open positions."

        moved = 0
        skipped = 0
        failed = 0
        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                failed += 1
                continue

            # Check if position is in profit
            if pos.type == 0:  # BUY
                in_profit = tick.bid > pos.price_open
            else:  # SELL
                in_profit = tick.ask < pos.price_open

            if not in_profit:
                skipped += 1
                continue

            # Already at or better than breakeven
            if pos.type == 0 and pos.sl >= pos.price_open:
                skipped += 1
                continue
            if pos.type == 1 and pos.sl > 0 and pos.sl <= pos.price_open:
                skipped += 1
                continue

            symbol_info = mt5.symbol_info(pos.symbol)
            digits = symbol_info.digits if symbol_info else 5
            new_sl = round(pos.price_open, digits)

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "sl": new_sl,
                "tp": pos.tp,
            }

            result = mt5.order_send(request)
            if result and result.retcode in (10008, 10009):
                moved += 1
                log_event(
                    "command_breakeven",
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    sl=new_sl,
                )
            else:
                failed += 1

        return (
            f"✅ Breakeven: {moved} moved, {skipped} skipped (not in profit)"
            f"{f', {failed} failed' if failed else ''}"
        )
