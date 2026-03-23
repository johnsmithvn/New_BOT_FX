"""
core/reply_command_executor.py

Execute trade management actions on specific MT5 position tickets.

Unlike CommandExecutor (operates on ALL positions), this executor
targets a single ticket — used when channel admin replies to a signal.
"""

from __future__ import annotations

from utils.logger import log_event

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore[assignment]

from core.reply_action_parser import ReplyAction, ReplyActionType


class ReplyCommandExecutor:
    """Execute reply actions on specific MT5 position tickets."""

    def __init__(self, magic: int = 234000, reply_be_lock_pips: float = 1.0) -> None:
        self._magic = magic
        self._reply_be_lock_pips = reply_be_lock_pips

    # ── Public API ────────────────────────────────────────────────

    def position_exists(self, ticket: int) -> bool:
        """Check if an MT5 position with this ticket is still open."""
        if not mt5:
            return False
        positions = mt5.positions_get(ticket=ticket)
        return bool(positions and len(positions) > 0)

    def get_position(self, ticket: int):
        """Get MT5 position by ticket. Returns position or None."""
        if not mt5:
            return None
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            return positions[0]
        return None

    def execute(
        self,
        ticket: int,
        action: ReplyAction,
        expected_symbol: str = "",
        dry_run: bool = False,
        reply_be_lock_pips: float | None = None,
    ) -> str:
        """Execute action on a specific ticket.

        Args:
            ticket: MT5 position ticket.
            action: Parsed reply action.
            expected_symbol: If provided, verify position symbol matches.
            dry_run: If True, log but don't execute.

        Returns:
            Human-readable summary string.
        """
        # Position existence check
        pos = self.get_position(ticket)
        if not pos:
            return "⚠️ Position already closed"

        # Symbol consistency check
        if expected_symbol and pos.symbol != expected_symbol:
            log_event(
                "reply_symbol_mismatch",
                ticket=ticket,
                expected=expected_symbol,
                actual=pos.symbol,
            )
            return f"⚠️ Symbol mismatch: expected {expected_symbol}, got {pos.symbol}"

        if dry_run:
            return f"🧪 [DRY] Would {action.action.value} on #{ticket} ({pos.symbol})"

        # Dispatch
        if action.action == ReplyActionType.CLOSE:
            return self._close(pos)
        elif action.action == ReplyActionType.CLOSE_PARTIAL:
            return self._close_partial(pos, action.percent or 50)
        elif action.action == ReplyActionType.MOVE_SL:
            return self._move_sl(pos, action.price or 0.0)
        elif action.action == ReplyActionType.MOVE_TP:
            return self._move_tp(pos, action.price or 0.0)
        elif action.action == ReplyActionType.BREAKEVEN:
            lock = reply_be_lock_pips if reply_be_lock_pips is not None else self._reply_be_lock_pips
            return self._breakeven(pos, lock)
        else:
            return f"❌ Unknown action: {action.action}"

    # ── Private handlers ──────────────────────────────────────────

    def _close(self, pos) -> str:
        """Close position entirely."""
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY
                     else mt5.symbol_info_tick(pos.symbol).ask,
            "magic": self._magic,
            "comment": "reply_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log_event("reply_close_ok", ticket=pos.ticket, symbol=pos.symbol)
            return f"✅ Closed {pos.symbol} #{pos.ticket} ({pos.volume} lots)"
        retcode = result.retcode if result else -1
        log_event("reply_close_fail", ticket=pos.ticket, retcode=retcode)
        return f"❌ Close failed (retcode={retcode})"

    def _close_partial(self, pos, percent: int) -> str:
        """Close a percentage of the position volume."""
        symbol_info = mt5.symbol_info(pos.symbol)
        if not symbol_info:
            return f"❌ Symbol info not found for {pos.symbol}"

        min_volume = symbol_info.volume_min
        step = symbol_info.volume_step
        close_volume = pos.volume * (percent / 100)
        # Round to step
        close_volume = max(min_volume, round(close_volume / step) * step)
        close_volume = round(close_volume, 2)

        if close_volume >= pos.volume:
            return self._close(pos)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": close_volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY
                     else mt5.symbol_info_tick(pos.symbol).ask,
            "magic": self._magic,
            "comment": f"reply_partial_{percent}pct",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log_event("reply_partial_ok", ticket=pos.ticket, percent=percent,
                      volume=close_volume)
            return f"✅ Closed {percent}% ({close_volume} lots) of {pos.symbol} #{pos.ticket}"
        retcode = result.retcode if result else -1
        log_event("reply_partial_fail", ticket=pos.ticket, retcode=retcode)
        return f"❌ Partial close failed (retcode={retcode})"

    def _move_sl(self, pos, new_sl: float) -> str:
        """Modify SL on position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": pos.tp,
            "magic": self._magic,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log_event("reply_move_sl_ok", ticket=pos.ticket, new_sl=new_sl)
            return f"✅ SL → {new_sl} on {pos.symbol} #{pos.ticket}"
        retcode = result.retcode if result else -1
        log_event("reply_move_sl_fail", ticket=pos.ticket, retcode=retcode)
        return f"❌ Move SL failed (retcode={retcode})"

    def _move_tp(self, pos, new_tp: float) -> str:
        """Modify TP on position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": pos.sl,
            "tp": new_tp,
            "magic": self._magic,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log_event("reply_move_tp_ok", ticket=pos.ticket, new_tp=new_tp)
            return f"✅ TP → {new_tp} on {pos.symbol} #{pos.ticket}"
        retcode = result.retcode if result else -1
        log_event("reply_move_tp_fail", ticket=pos.ticket, retcode=retcode)
        return f"❌ Move TP failed (retcode={retcode})"

    def _breakeven(self, pos, lock_pips: float = 1.0) -> str:
        """Move SL to entry + lock pips (profitable side).

        Uses reply_be_lock_pips to offset SL into profit territory.
        BUY: SL = entry + lock_distance (above entry)
        SELL: SL = entry - lock_distance (below entry)
        """
        entry = pos.price_open

        # Calculate lock offset
        lock_distance = 0.0
        if lock_pips > 0:
            sym_info = mt5.symbol_info(pos.symbol)
            pip_size = sym_info.point * 10 if sym_info and sym_info.point > 0 else 0.1
            lock_distance = lock_pips * pip_size

        if pos.type == 0:  # BUY
            new_sl = entry + lock_distance
            # Guard: only move SL up, never down (keep better SL)
            if pos.sl > 0 and new_sl <= pos.sl:
                return f"ℹ️ SL already at {pos.sl} (better than BE {new_sl})"
        else:  # SELL
            new_sl = entry - lock_distance
            # Guard: only move SL down, never up (keep better SL)
            if pos.sl > 0 and new_sl >= pos.sl:
                return f"ℹ️ SL already at {pos.sl} (better than BE {new_sl})"

        # Round to symbol digits
        sym_info = mt5.symbol_info(pos.symbol)
        digits = sym_info.digits if sym_info else 5
        new_sl = round(new_sl, digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": pos.tp,
            "magic": self._magic,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log_event("reply_breakeven_ok", ticket=pos.ticket, sl=new_sl,
                      lock_pips=self._reply_be_lock_pips)
            return f"\u2705 BE \u2192 SL={new_sl} on {pos.symbol} #{pos.ticket}"
        retcode = result.retcode if result else -1
        log_event("reply_breakeven_fail", ticket=pos.ticket, retcode=retcode)
        return f"\u274c Breakeven failed (retcode={retcode})"
