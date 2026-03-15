"""
core/telegram_alerter.py

Send critical alerts to admin Telegram chat.
Rate-limited to prevent spam.
"""

from __future__ import annotations

import asyncio
import time

from telethon import TelegramClient

from utils.logger import log_event


class TelegramAlerter:
    """Send alerts to an admin Telegram chat.

    Features:
    - Rate limiting via cooldown to prevent spam.
    - Non-blocking: alerts queued and sent asynchronously.
    - Graceful degradation: alert failures don't crash the bot.
    """

    def __init__(
        self,
        client: TelegramClient | None = None,
        admin_chat: str = "",
        cooldown_seconds: int = 300,
    ) -> None:
        self._client = client
        self._admin_chat = admin_chat
        self._cooldown = cooldown_seconds
        self._last_alert_times: dict[str, float] = {}

    def set_client(self, client: TelegramClient) -> None:
        """Set the Telethon client (shared with listener)."""
        self._client = client

    def _is_rate_limited(self, alert_type: str) -> bool:
        """Check if this alert type is rate-limited."""
        now = time.time()
        last = self._last_alert_times.get(alert_type, 0)
        if now - last < self._cooldown:
            return True
        self._last_alert_times[alert_type] = now
        return False

    async def send_alert(self, alert_type: str, message: str) -> None:
        """Send an alert message to admin chat.

        Rate-limited per alert_type.
        """
        if not self._client or not self._admin_chat:
            log_event(
                "alert_skipped",
                alert_type=alert_type,
                reason="no client or admin chat configured",
            )
            return

        if self._is_rate_limited(alert_type):
            log_event(
                "alert_rate_limited",
                alert_type=alert_type,
                cooldown=self._cooldown,
            )
            return

        try:
            entity = await self._client.get_entity(self._admin_chat)
            await self._client.send_message(entity, message)
            log_event(
                "alert_sent",
                alert_type=alert_type,
            )
        except Exception as exc:
            log_event(
                "alert_send_failed",
                alert_type=alert_type,
                error=str(exc),
            )

    def send_alert_sync(self, alert_type: str, message: str) -> None:
        """Schedule alert from sync context."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_alert(alert_type, message))
        except RuntimeError:
            # No event loop running; skip alert
            log_event(
                "alert_skipped",
                alert_type=alert_type,
                reason="no event loop",
            )

    # ── Debug methods (no rate limiting) ─────────────────────────

    async def send_debug(self, message: str) -> None:
        """Send a debug message to admin chat — NO rate limiting."""
        if not self._client or not self._admin_chat:
            log_event("debug_skipped", reason="no client or admin chat configured")
            return

        try:
            entity = await self._client.get_entity(self._admin_chat)
            await self._client.send_message(entity, message)
            log_event("debug_sent")
        except Exception as exc:
            log_event("debug_send_failed", error=str(exc))

    def send_debug_sync(self, message: str) -> None:
        """Schedule debug message from sync context — NO rate limiting."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_debug(message))
        except RuntimeError:
            log_event("debug_skipped", reason="no event loop")

    # ── Convenience methods ──────────────────────────────────────

    async def alert_circuit_breaker_opened(self) -> None:
        await self.send_alert(
            "circuit_breaker_open",
            "🔴 **CIRCUIT BREAKER OPENED**\n"
            "Trading paused due to consecutive execution failures.\n"
            "Bot will auto-probe after cooldown.",
        )

    async def alert_circuit_breaker_closed(self) -> None:
        await self.send_alert(
            "circuit_breaker_close",
            "🟢 **CIRCUIT BREAKER CLOSED**\n"
            "Trading resumed. Probe execution succeeded.",
        )

    async def alert_mt5_connection_lost(self) -> None:
        await self.send_alert(
            "mt5_connection_lost",
            "⚠️ **MT5 CONNECTION LOST**\n"
            "Watchdog detected connection failure.\n"
            "Attempting reinitialization...",
        )

    async def alert_mt5_reinit_exhausted(self) -> None:
        await self.send_alert(
            "mt5_reinit_exhausted",
            "🔴 **MT5 REINIT FAILED**\n"
            "All reinit retries exhausted.\n"
            "Manual intervention required.",
        )

    async def alert_bot_started(self) -> None:
        await self.send_alert(
            "bot_started",
            "🟢 **BOT STARTED**\n"
            "Signal processing pipeline active.",
        )

    async def alert_bot_stopped(self) -> None:
        await self.send_alert(
            "bot_stopped",
            "🔴 **BOT STOPPED**\n"
            "Signal processing pipeline inactive.",
        )
