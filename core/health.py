"""
core/health.py

Runtime health stats tracker and lightweight HTTP health check endpoint.

Tracks:
- Bot uptime
- MT5 connection state
- Last signal received
- Daily counters (signals, orders, errors)
- Circuit breaker state

Exposes /health HTTP endpoint for remote monitoring.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from utils.logger import log_event


@dataclass
class HealthStats:
    """In-memory runtime statistics for health monitoring."""

    started_at: float = field(default_factory=time.time)

    # MT5 state (updated by watchdog)
    mt5_connected: bool = False
    mt5_last_check: str = ""

    # Telegram state
    telegram_connected: bool = False

    # Signal stats
    last_signal_time: str = ""
    last_signal_symbol: str = ""
    signals_today: int = 0
    orders_today: int = 0
    errors_today: int = 0

    # Circuit breaker
    circuit_breaker_state: str = "CLOSED"
    circuit_breaker_failures: int = 0

    # Counters reset date
    _counter_date: str = field(default_factory=lambda: "")

    def _check_daily_reset(self) -> None:
        """Reset daily counters at midnight UTC."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._counter_date != today:
            self.signals_today = 0
            self.orders_today = 0
            self.errors_today = 0
            self._counter_date = today

    def record_signal(self, symbol: str = "") -> None:
        """Track a signal received."""
        self._check_daily_reset()
        self.signals_today += 1
        self.last_signal_time = datetime.now(timezone.utc).isoformat()
        self.last_signal_symbol = symbol

    def record_order(self) -> None:
        """Track an order executed."""
        self._check_daily_reset()
        self.orders_today += 1

    def record_error(self) -> None:
        """Track an error."""
        self._check_daily_reset()
        self.errors_today += 1

    def set_mt5_status(self, connected: bool) -> None:
        """Update MT5 connection state."""
        self.mt5_connected = connected
        self.mt5_last_check = datetime.now(timezone.utc).isoformat()

    def set_circuit_breaker(self, state: str, failures: int = 0) -> None:
        """Update circuit breaker state."""
        self.circuit_breaker_state = state
        self.circuit_breaker_failures = failures

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.started_at

    @property
    def uptime_human(self) -> str:
        """Human-readable uptime string."""
        total = int(self.uptime_seconds)
        days, remainder = divmod(total, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)

    def to_dict(self) -> dict:
        """Serialize health state to dict."""
        self._check_daily_reset()
        status = "healthy"
        if not self.mt5_connected:
            status = "degraded"
        if self.circuit_breaker_state == "OPEN":
            status = "unhealthy"

        return {
            "status": status,
            "uptime": self.uptime_human,
            "uptime_seconds": round(self.uptime_seconds),
            "mt5_connected": self.mt5_connected,
            "mt5_last_check": self.mt5_last_check,
            "telegram_connected": self.telegram_connected,
            "last_signal_time": self.last_signal_time,
            "last_signal_symbol": self.last_signal_symbol,
            "signals_today": self.signals_today,
            "orders_today": self.orders_today,
            "errors_today": self.errors_today,
            "circuit_breaker": self.circuit_breaker_state,
            "circuit_breaker_failures": self.circuit_breaker_failures,
        }


class HealthCheckServer:
    """Lightweight async HTTP server serving /health endpoint.

    Runs on a separate port (default 8080) from the main bot.
    No external dependencies — uses asyncio.start_server.
    """

    def __init__(
        self,
        stats: HealthStats,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        self._stats = stats
        self._host = host
        self._port = port
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the health check HTTP server."""
        try:
            self._server = await asyncio.start_server(
                self._handle_request, self._host, self._port,
            )
            log_event(
                "health_server_started",
                host=self._host,
                port=self._port,
            )
        except OSError as exc:
            log_event(
                "health_server_failed",
                error=str(exc),
                port=self._port,
            )

    async def stop(self) -> None:
        """Stop the health check server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            log_event("health_server_stopped")

    async def _handle_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single HTTP request."""
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            request_line = data.decode("utf-8", errors="ignore").split("\r\n")[0]
            method, path, *_ = request_line.split(" ") if request_line else ("", "", "")

            if path == "/health" and method == "GET":
                body = json.dumps(self._stats.to_dict(), indent=2)
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    "\r\n"
                    f"{body}"
                )
            else:
                body = '{"error": "Not Found"}'
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "\r\n"
                    f"{body}"
                )

            writer.write(response.encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
