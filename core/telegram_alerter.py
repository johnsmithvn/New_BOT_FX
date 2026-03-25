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
        admin_chat: str | int = "",
        cooldown_seconds: int = 300,
    ) -> None:
        self._client = client
        self._admin_chat = admin_chat
        self._cooldown = cooldown_seconds
        self._last_alert_times: dict[str, float] = {}
        self._admin_entity = None  # Cached entity for admin chat

    def set_client(self, client: TelegramClient) -> None:
        """Set the Telethon client (shared with listener)."""
        self._client = client
        self._admin_entity = None  # Invalidate cache on client change

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
            entity = await self._resolve_admin_entity()
            if not entity:
                return
            await self._client.send_message(entity, message, parse_mode="md")
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
            entity = await self._resolve_admin_entity()
            if not entity:
                return
            await self._client.send_message(entity, message, parse_mode="md")
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

    # ── Reply-to methods (trade outcome) ─────────────────────────

    async def reply_to_message(
        self, chat_id: str | int, message_id: int, text: str,
    ) -> None:
        """Reply to a specific message in a chat. No rate limiting.

        Used by TradeTracker to reply with PnL under the original signal.
        """
        if not self._client:
            log_event("reply_skipped", reason="no client")
            return

        try:
            # reply_to uses per-chat entity (not cached admin)
            # Telethon needs int for numeric chat IDs
            resolved_id = int(chat_id) if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit() else chat_id
            entity = await self._client.get_entity(resolved_id)
            await self._client.send_message(
                entity, text, reply_to=message_id, parse_mode="md",
            )
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

    # ── Entity resolution (cached) ────────────────────────────────

    async def _resolve_admin_entity(self):
        """Resolve and cache the admin chat entity.

        Avoids calling get_entity() on every alert.
        Cache is invalidated on client change via set_client().
        """
        if self._admin_entity is not None:
            return self._admin_entity
        try:
            self._admin_entity = await self._client.get_entity(self._admin_chat)
            return self._admin_entity
        except Exception as exc:
            log_event("admin_entity_resolve_failed", error=str(exc))
            return None
