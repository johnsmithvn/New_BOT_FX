"""
core/trade_executor.py

Initialize and manage MT5 connection.
Execute orders with bounded retry.
Return normalized ExecutionResult.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from core.mt5_bridge import mt5

from core.models import ExecutionResult
from utils.logger import log_event


# MT5 return code descriptions for traceability.
_RETCODE_MAP: dict[int, str] = {
    10004: "TRADE_RETCODE_REQUOTE",
    10006: "TRADE_RETCODE_REJECT",
    10007: "TRADE_RETCODE_CANCEL",
    10008: "TRADE_RETCODE_PLACED",
    10009: "TRADE_RETCODE_DONE",
    10010: "TRADE_RETCODE_DONE_PARTIAL",
    10011: "TRADE_RETCODE_ERROR",
    10012: "TRADE_RETCODE_TIMEOUT",
    10013: "TRADE_RETCODE_INVALID",
    10014: "TRADE_RETCODE_INVALID_VOLUME",
    10015: "TRADE_RETCODE_INVALID_PRICE",
    10016: "TRADE_RETCODE_INVALID_STOPS",
    10017: "TRADE_RETCODE_TRADE_DISABLED",
    10018: "TRADE_RETCODE_MARKET_CLOSED",
    10019: "TRADE_RETCODE_NO_MONEY",
    10020: "TRADE_RETCODE_PRICE_CHANGED",
    10021: "TRADE_RETCODE_PRICE_OFF",
    10022: "TRADE_RETCODE_INVALID_EXPIRATION",
    10023: "TRADE_RETCODE_ORDER_CHANGED",
    10024: "TRADE_RETCODE_TOO_MANY_REQUESTS",
    10025: "TRADE_RETCODE_NO_CHANGES",
    10026: "TRADE_RETCODE_SERVER_DISABLES_AT",
    10027: "TRADE_RETCODE_CLIENT_DISABLES_AT",
    10028: "TRADE_RETCODE_LOCKED",
    10029: "TRADE_RETCODE_FROZEN",
    10030: "TRADE_RETCODE_INVALID_FILL",
    10031: "TRADE_RETCODE_CONNECTION",
    10032: "TRADE_RETCODE_ONLY_REAL",
    10033: "TRADE_RETCODE_LIMIT_ORDERS",
    10034: "TRADE_RETCODE_LIMIT_VOLUME",
    10035: "TRADE_RETCODE_INVALID_ORDER",
    10036: "TRADE_RETCODE_POSITION_CLOSED",
}


def retcode_description(retcode: int) -> str:
    """Return human-readable description for MT5 return code."""
    return _RETCODE_MAP.get(retcode, f"UNKNOWN_RETCODE_{retcode}")


@dataclass
class TickData:
    """Live tick data from MT5."""
    bid: float
    ask: float
    spread_points: float
    time: int


class TradeExecutor:
    """Manages MT5 connection and order execution.

    Responsibilities:
    - Initialize/shutdown MT5 terminal.
    - Fetch live tick data.
    - Execute orders with bounded retry.
    - Query account and position state.
    """

    def __init__(
        self,
        mt5_path: str = "",
        login: int = 0,
        password: str = "",
        server: str = "",
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        """Args:
            max_retries: Max order_send attempts before giving up. Configurable via ORDER_MAX_RETRIES.
            retry_delay_seconds: Base delay between retries (multiplied by attempt). Via ORDER_RETRY_DELAY_SECONDS.
        """
        self._mt5_path = mt5_path
        self._login = login
        self._password = password
        self._server = server
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._initialized = False

    def init_mt5(self) -> bool:
        """Initialize MT5 terminal and log in.

        Returns True on success, False on failure.
        """
        kwargs: dict = {}
        if self._mt5_path:
            kwargs["path"] = self._mt5_path
        if self._login:
            kwargs["login"] = self._login
        if self._password:
            kwargs["password"] = self._password
        if self._server:
            kwargs["server"] = self._server

        if not mt5.initialize(**kwargs):
            error = mt5.last_error()
            log_event(
                "mt5_init_failed",
                error_code=error[0] if error else -1,
                error_msg=error[1] if error else "unknown",
            )
            return False

        account = mt5.account_info()
        if account is None:
            log_event("mt5_login_failed")
            mt5.shutdown()
            return False

        self._initialized = True
        log_event(
            "mt5_init_success",
            account_login=account.login,
            account_server=account.server,
            account_balance=account.balance,
        )
        return True

    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        mt5.shutdown()
        self._initialized = False
        log_event("mt5_shutdown")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def is_connected(self) -> bool:
        """Return True if MT5 is initialized and account info is accessible."""
        if not self._initialized:
            return False
        try:
            return mt5.account_info() is not None
        except Exception:
            return False

    def get_tick(self, symbol: str) -> TickData | None:
        """Fetch live tick data for a symbol.

        Returns TickData or None if unavailable.
        """
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        info = mt5.symbol_info(symbol)
        point = info.point if info and info.point > 0 else 0.00001
        spread_points = (tick.ask - tick.bid) / point

        return TickData(
            bid=tick.bid,
            ask=tick.ask,
            spread_points=spread_points,
            time=tick.time,
        )

    def positions_total(self) -> int:
        """Return the number of currently open positions."""
        total = mt5.positions_total()
        return total if total is not None else 0

    def get_position_symbols(self) -> list[str]:
        """Return list of symbols from all open MT5 positions.

        Used by ExposureGuard to check per-symbol / correlation limits.
        Returns empty list on failure.
        """
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            return [p.symbol for p in positions]
        except Exception:
            return []

    def orders_total(self) -> int:
        """Return the number of currently active pending orders."""
        total = mt5.orders_total()
        return total if total is not None else 0

    def account_info(self) -> dict | None:
        """Fetch account info for health check.

        Returns dict with balance, equity, margin, etc. or None.
        """
        info = mt5.account_info()
        if info is None:
            return None
        return {
            "login": info.login,
            "server": info.server,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "margin_free": info.margin_free,
        }

    def execute(
        self,
        request: dict,
        fingerprint: str = "",
    ) -> ExecutionResult:
        """Execute an MT5 order with bounded retry.

        Args:
            request: MT5 order request dict (action, type, symbol, etc.).
            fingerprint: Signal fingerprint for log tracing.

        Returns:
            Normalized ExecutionResult.
        """
        last_error_msg = ""

        for attempt in range(1, self._max_retries + 1):
            log_event(
                "order_send_attempt",
                fingerprint=fingerprint,
                symbol=request.get("symbol", ""),
                attempt=attempt,
                max_retries=self._max_retries,
            )

            result = mt5.order_send(request)

            if result is None:
                error = mt5.last_error()
                last_error_msg = f"order_send returned None: {error}"
                log_event(
                    "order_send_null",
                    fingerprint=fingerprint,
                    attempt=attempt,
                    error=last_error_msg,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
                continue

            retcode = result.retcode
            retcode_desc = retcode_description(retcode)

            # Success codes
            if retcode in (10008, 10009, 10010):
                log_event(
                    "order_result",
                    fingerprint=fingerprint,
                    symbol=request.get("symbol", ""),
                    retcode=retcode,
                    retcode_desc=retcode_desc,
                    ticket=result.order,
                    success=True,
                )
                return ExecutionResult(
                    success=True,
                    retcode=retcode,
                    ticket=result.order,
                    message=retcode_desc,
                )

            # Retryable codes
            if retcode in (10004, 10020, 10021, 10024, 10031):
                last_error_msg = retcode_desc
                log_event(
                    "order_send_retry",
                    fingerprint=fingerprint,
                    attempt=attempt,
                    retcode=retcode,
                    retcode_desc=retcode_desc,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
                continue

            # Non-retryable failure
            log_event(
                "order_result",
                fingerprint=fingerprint,
                symbol=request.get("symbol", ""),
                retcode=retcode,
                retcode_desc=retcode_desc,
                success=False,
            )
            return ExecutionResult(
                success=False,
                retcode=retcode,
                ticket=None,
                message=retcode_desc,
            )

        # All retries exhausted
        log_event(
            "order_send_exhausted",
            fingerprint=fingerprint,
            max_retries=self._max_retries,
            last_error=last_error_msg,
        )
        return ExecutionResult(
            success=False,
            retcode=-1,
            ticket=None,
            message=f"all retries exhausted: {last_error_msg}",
        )

    def get_pending_orders(self, symbol: str | None = None) -> list[dict]:
        """Get pending orders, optionally filtered by symbol."""
        if symbol:
            orders = mt5.orders_get(symbol=symbol)
        else:
            orders = mt5.orders_get()

        if orders is None:
            return []

        return [
            {
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": o.type,
                "volume": o.volume_current,
                "price_open": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "time_setup": o.time_setup,
                "magic": o.magic,
                "comment": o.comment,
            }
            for o in orders
        ]

    def cancel_order(self, ticket: int, fingerprint: str = "") -> bool:
        """Cancel a pending order by ticket.

        Returns True if cancellation succeeded.
        """
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }
        result = mt5.order_send(request)
        if result is None:
            log_event(
                "order_cancel_failed",
                fingerprint=fingerprint,
                ticket=ticket,
                error="order_send returned None",
            )
            return False

        success = result.retcode in (10008, 10009)
        log_event(
            "order_cancel_result",
            fingerprint=fingerprint,
            ticket=ticket,
            retcode=result.retcode,
            success=success,
        )
        return success
