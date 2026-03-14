"""
core/telegram_listener.py

Connect to Telegram via Telethon user session.
Subscribe to configured source chats/channels.
Forward raw messages to the signal processing pipeline.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from telethon import TelegramClient, events

from utils.logger import log_event


# Type alias for the pipeline callback.
# Receives: raw_text, chat_id, message_id
PipelineCallback = Callable[[str, str, str], Awaitable[None] | None]

# Type alias for edit callback.
# Receives: raw_text, chat_id, message_id
EditCallback = Callable[[str, str, str], Awaitable[None] | None]


class TelegramListener:
    """Telethon-based Telegram listener.

    Uses a user session (not Bot API) to read from private
    groups and signal channels.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str = "forex_bot",
        phone: str = "",
        source_chats: list[str] | None = None,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_name = session_name
        self._phone = phone
        self._source_chats = source_chats or []
        self._client: TelegramClient | None = None
        self._pipeline_cb: PipelineCallback | None = None
        self._edit_cb: EditCallback | None = None

    def set_pipeline_callback(self, callback: PipelineCallback) -> None:
        """Set the callback for new signal messages."""
        self._pipeline_cb = callback

    def set_edit_callback(self, callback: EditCallback) -> None:
        """Set the callback for edited messages."""
        self._edit_cb = callback

    async def start(self) -> None:
        """Initialize Telethon client and start listening."""
        self._client = TelegramClient(
            self._session_name,
            self._api_id,
            self._api_hash,
        )

        # Pass phone to avoid interactive prompt.
        # First run will still ask for the OTP code.
        start_kwargs: dict = {}
        if self._phone:
            start_kwargs["phone"] = self._phone

        await self._client.start(**start_kwargs)

        # Resolve chat entities
        chat_entities = []
        for chat_id in self._source_chats:
            try:
                entity = await self._client.get_entity(chat_id)
                chat_entities.append(entity)
                log_event(
                    "telegram_chat_subscribed",
                    symbol="",
                    chat_id=str(chat_id),
                    chat_name=getattr(entity, "title", str(chat_id)),
                )
            except Exception as exc:
                log_event(
                    "telegram_chat_resolve_failed",
                    symbol="",
                    chat_id=str(chat_id),
                    error=str(exc),
                )

        # Register new message handler
        @self._client.on(events.NewMessage(chats=chat_entities or None))
        async def on_new_message(event: events.NewMessage.Event) -> None:
            await self._handle_new_message(event)

        # Register message edited handler
        @self._client.on(events.MessageEdited(chats=chat_entities or None))
        async def on_message_edited(event: events.MessageEdited.Event) -> None:
            await self._handle_edited_message(event)

        log_event(
            "telegram_listener_started",
            symbol="",
            chats_count=len(chat_entities),
        )

    async def _handle_new_message(
        self, event: events.NewMessage.Event
    ) -> None:
        """Process incoming new message."""
        message = event.message
        if not message or not message.text:
            return

        raw_text = message.text
        chat_id = str(message.chat_id) if message.chat_id else ""
        message_id = str(message.id) if message.id else ""

        log_event(
            "signal_received",
            symbol="",
            source_chat_id=chat_id,
            source_message_id=message_id,
            text_preview=raw_text[:80],
        )

        if self._pipeline_cb:
            try:
                result = self._pipeline_cb(raw_text, chat_id, message_id)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log_event(
                    "pipeline_callback_error",
                    symbol="",
                    source_message_id=message_id,
                    error=str(exc),
                )

    async def _handle_edited_message(
        self, event: events.MessageEdited.Event
    ) -> None:
        """Process edited message."""
        message = event.message
        if not message or not message.text:
            return

        raw_text = message.text
        chat_id = str(message.chat_id) if message.chat_id else ""
        message_id = str(message.id) if message.id else ""

        log_event(
            "message_edited",
            symbol="",
            source_chat_id=chat_id,
            source_message_id=message_id,
        )

        if self._edit_cb:
            try:
                result = self._edit_cb(raw_text, chat_id, message_id)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log_event(
                    "edit_callback_error",
                    symbol="",
                    source_message_id=message_id,
                    error=str(exc),
                )

    async def run_until_disconnected(self) -> None:
        """Block until the client disconnects."""
        if self._client:
            await self._client.run_until_disconnected()

    async def stop(self) -> None:
        """Gracefully disconnect."""
        if self._client:
            await self._client.disconnect()
            log_event("telegram_listener_stopped", symbol="")
