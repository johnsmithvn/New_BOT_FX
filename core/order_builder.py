"""
core/order_builder.py

Read live bid/ask from MT5 tick.
Decide order type using correct price reference:
  BUY: compare entry vs ASK
  SELL: compare entry vs BID
Build MT5-compatible request payload.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from core.models import ParsedSignal, TradeDecision, OrderKind, Side


# Magic number to identify orders placed by this bot.
BOT_MAGIC_NUMBER = 234000

# Default deviation in points for market orders.
DEFAULT_DEVIATION = 20


class OrderBuilder:
    """Build MT5 order requests from parsed signals.

    Decision matrix:
        BUY + entry is None          → MARKET
        BUY + |entry - ask| ≤ tol    → MARKET
        BUY + entry < ask            → BUY_LIMIT
        BUY + entry > ask            → BUY_STOP

        SELL + entry is None         → MARKET
        SELL + |entry - bid| ≤ tol   → MARKET
        SELL + entry > bid           → SELL_LIMIT
        SELL + entry < bid           → SELL_STOP
    """

    def __init__(
        self,
        market_tolerance_points: float = 5.0,
        deviation: int = DEFAULT_DEVIATION,
        magic: int = BOT_MAGIC_NUMBER,
    ) -> None:
        self._tolerance = market_tolerance_points
        self._deviation = deviation
        self._magic = magic

    def decide_order_type(
        self,
        signal: ParsedSignal,
        bid: float,
        ask: float,
        point: float = 0.00001,
    ) -> TradeDecision:
        """Decide the order type based on signal and live prices.

        Args:
            signal: Parsed signal with side and entry.
            bid: Current bid price.
            ask: Current ask price.
            point: Symbol point value for tolerance calc.

        Returns:
            TradeDecision with order_kind and execution price.
        """
        tolerance = self._tolerance * point

        if signal.side == Side.BUY:
            return self._decide_buy(signal, ask, tolerance)
        else:
            return self._decide_sell(signal, bid, tolerance)

    def _decide_buy(
        self,
        signal: ParsedSignal,
        ask: float,
        tolerance: float,
    ) -> TradeDecision:
        """BUY decision: compare entry against ASK price."""
        # Market execution
        if signal.entry is None:
            return TradeDecision(
                order_kind=OrderKind.MARKET,
                price=None,
                sl=signal.sl,
                tp=signal.tp[0] if signal.tp else None,
            )

        # Within tolerance of current ASK → treat as market
        if abs(signal.entry - ask) <= tolerance:
            return TradeDecision(
                order_kind=OrderKind.MARKET,
                price=None,
                sl=signal.sl,
                tp=signal.tp[0] if signal.tp else None,
            )

        # Entry below ASK → BUY_LIMIT
        if signal.entry < ask:
            return TradeDecision(
                order_kind=OrderKind.BUY_LIMIT,
                price=signal.entry,
                sl=signal.sl,
                tp=signal.tp[0] if signal.tp else None,
            )

        # Entry above ASK → BUY_STOP
        return TradeDecision(
            order_kind=OrderKind.BUY_STOP,
            price=signal.entry,
            sl=signal.sl,
            tp=signal.tp[0] if signal.tp else None,
        )

    def _decide_sell(
        self,
        signal: ParsedSignal,
        bid: float,
        tolerance: float,
    ) -> TradeDecision:
        """SELL decision: compare entry against BID price."""
        # Market execution
        if signal.entry is None:
            return TradeDecision(
                order_kind=OrderKind.MARKET,
                price=None,
                sl=signal.sl,
                tp=signal.tp[0] if signal.tp else None,
            )

        # Within tolerance of current BID → treat as market
        if abs(signal.entry - bid) <= tolerance:
            return TradeDecision(
                order_kind=OrderKind.MARKET,
                price=None,
                sl=signal.sl,
                tp=signal.tp[0] if signal.tp else None,
            )

        # Entry above BID → SELL_LIMIT
        if signal.entry > bid:
            return TradeDecision(
                order_kind=OrderKind.SELL_LIMIT,
                price=signal.entry,
                sl=signal.sl,
                tp=signal.tp[0] if signal.tp else None,
            )

        # Entry below BID → SELL_STOP
        return TradeDecision(
            order_kind=OrderKind.SELL_STOP,
            price=signal.entry,
            sl=signal.sl,
            tp=signal.tp[0] if signal.tp else None,
        )

    def build_request(
        self,
        signal: ParsedSignal,
        decision: TradeDecision,
        volume: float,
        bid: float,
        ask: float,
    ) -> dict:
        """Build a complete MT5 order request dict.

        Args:
            signal: Parsed signal for metadata.
            decision: Trade decision with order type.
            volume: Calculated lot size.
            bid: Current bid price.
            ask: Current ask price.

        Returns:
            MT5-compatible request dict.
        """
        request: dict = {
            "symbol": signal.symbol,
            "volume": volume,
            "sl": decision.sl if decision.sl else 0.0,
            "tp": decision.tp if decision.tp else 0.0,
            "deviation": self._deviation,
            "magic": self._magic,
            "comment": f"signal:{signal.fingerprint[:8]}",
        }

        if decision.order_kind == OrderKind.MARKET:
            if signal.side == Side.BUY:
                request["action"] = mt5.TRADE_ACTION_DEAL
                request["type"] = mt5.ORDER_TYPE_BUY
                request["price"] = ask
            else:
                request["action"] = mt5.TRADE_ACTION_DEAL
                request["type"] = mt5.ORDER_TYPE_SELL
                request["price"] = bid

            request["type_filling"] = mt5.ORDER_FILLING_IOC
        else:
            request["action"] = mt5.TRADE_ACTION_PENDING
            request["price"] = decision.price

            _ORDER_TYPE_MAP = {
                OrderKind.BUY_LIMIT: mt5.ORDER_TYPE_BUY_LIMIT,
                OrderKind.BUY_STOP: mt5.ORDER_TYPE_BUY_STOP,
                OrderKind.SELL_LIMIT: mt5.ORDER_TYPE_SELL_LIMIT,
                OrderKind.SELL_STOP: mt5.ORDER_TYPE_SELL_STOP,
            }
            request["type"] = _ORDER_TYPE_MAP[decision.order_kind]
            request["type_time"] = mt5.ORDER_TIME_GTC
            request["type_filling"] = mt5.ORDER_FILLING_RETURN

        return request
