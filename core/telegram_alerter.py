"""
core/telegram_alerter.py

Send critical alerts to admin via Telegram Bot API.
Rate-limited to prevent spam.

v0.23.0: Migrated from Telethon user session to Bot API (AdminBot).
Telethon no longer needed for alert/debug/PnL.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from utils.logger import log_event

if TYPE_CHECKING:
    from core.admin_bot import AdminBot


class TelegramAlerter:
    """Send alerts to admin via Telegram Bot API.

    Features:
    - Rate limiting via cooldown to prevent spam.
    - Non-blocking: alerts queued and sent asynchronously.
    - Graceful degradation: alert failures don't crash the bot.
    - Routes all messages through AdminBot (Bot API).
    """

    def __init__(
        self,
        admin_bot: AdminBot | None = None,
        cooldown_seconds: int = 300,
    ) -> None:
        self._bot = admin_bot
        self._cooldown = cooldown_seconds
        self._last_alert_times: dict[str, float] = {}

    def set_bot(self, bot: AdminBot) -> None:
        """Set or update the AdminBot instance."""
        self._bot = bot

    def _is_rate_limited(self, alert_type: str) -> bool:
        """Check if this alert type is rate-limited."""
        now = time.time()
        last = self._last_alert_times.get(alert_type, 0)
        if now - last < self._cooldown:
            return True
        self._last_alert_times[alert_type] = now
        return False

    async def send_alert(self, alert_type: str, message: str) -> None:
        """Send an alert message to admin via Bot API.

        Rate-limited per alert_type.
        """
        if not self._bot:
            log_event(
                "alert_skipped",
                alert_type=alert_type,
                reason="no admin bot configured",
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
            await self._bot.send_message(message)
            log_event("alert_sent", alert_type=alert_type)
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
        """Send a debug message to admin — NO rate limiting."""
        if not self._bot:
            log_event("debug_skipped", reason="no admin bot configured")
            return

        try:
            await self._bot.send_message(message)
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

    # ── Reply-to methods (PnL tracking) ──────────────────────────

    async def reply_to_message(
        self, chat_id: str | int, message_id: int, text: str,
    ) -> None:
        """Send PnL result to admin bot chat.

        Note: In v0.23.0+, this no longer replies under the original signal
        in the source channel. Instead, the PnL message is sent as a flat
        message to the admin bot chat.
        """
        if not self._bot:
            log_event("reply_skipped", reason="no admin bot configured")
            return

        try:
            await self._bot.send_message(text)
            log_event(
                "reply_sent",
                chat_id=str(chat_id),
                message_id=message_id,
            )
        except Exception as exc:
            log_event(
                "reply_send_failed",
                chat_id=str(chat_id),
                message_id=message_id,
                error=str(exc),
            )

    def reply_to_message_sync(
        self, chat_id: str | int, message_id: int, text: str,
    ) -> None:
        """Schedule reply from sync context."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.reply_to_message(chat_id, message_id, text))
        except RuntimeError:
            log_event("reply_skipped", reason="no event loop")
