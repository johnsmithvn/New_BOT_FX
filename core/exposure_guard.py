"""
core/exposure_guard.py

Prevent over-concentration on correlated symbols.

Queries MT5 positions_get() to check:
  - MAX_SAME_SYMBOL_TRADES: max open positions on the same symbol
  - MAX_CORRELATED_TRADES: max open across a correlation group

All limits default to 0 = disabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logger import log_event

if TYPE_CHECKING:
    from core.trade_executor import TradeExecutor


class ExposureGuard:
    """Check symbol exposure before allowing new trades.

    Queries live MT5 position state on every call — no stale counters.
    """

    def __init__(
        self,
        executor: TradeExecutor,
        max_same_symbol_trades: int = 0,
        max_correlated_trades: int = 0,
        correlation_groups: list[list[str]] | None = None,
    ) -> None:
        """Args:
            executor: TradeExecutor for querying MT5 positions.
            max_same_symbol_trades: Max open positions on same symbol. 0 = disabled.
            max_correlated_trades: Max open positions across correlation group. 0 = disabled.
            correlation_groups: List of groups, each a list of correlated symbols.
                Example: [["XAUUSD", "XAGUSD"], ["EURUSD", "GBPUSD", "EURGBP"]]
        """
        self._executor = executor
        self._max_same = max_same_symbol_trades
        self._max_correlated = max_correlated_trades
        self._groups = correlation_groups or []

    def is_allowed(self, symbol: str) -> tuple[bool, str]:
        """Check if opening a new position on symbol is allowed.

        Returns:
            (allowed, reason) — reason is empty string if allowed.
        """
        # No limits configured → always allow
        if self._max_same <= 0 and self._max_correlated <= 0:
            return True, ""

        positions = self._get_open_positions()

        # Check same-symbol limit
        if self._max_same > 0:
            same_count = sum(1 for p in positions if p == symbol)
            if same_count >= self._max_same:
                reason = (
                    f"same-symbol limit reached for {symbol} "
                    f"({same_count}/{self._max_same})"
                )
                log_event("exposure_blocked", symbol=symbol, reason=reason)
                return False, reason

        # Check correlated group limit
        if self._max_correlated > 0:
            group = self._find_group(symbol)
            if group:
                group_count = sum(1 for p in positions if p in group)
                if group_count >= self._max_correlated:
                    reason = (
                        f"correlated group limit reached "
                        f"({group_count}/{self._max_correlated}) "
                        f"group={','.join(sorted(group))}"
                    )
                    log_event("exposure_blocked", symbol=symbol, reason=reason)
                    return False, reason

        return True, ""

    def _find_group(self, symbol: str) -> set[str] | None:
        """Find the correlation group containing this symbol."""
        for group in self._groups:
            if symbol in group:
                return set(group)
        return None

    def _get_open_positions(self) -> list[str]:
        """Get list of symbols from open MT5 positions via TradeExecutor."""
        return self._executor.get_position_symbols()
