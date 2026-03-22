"""
core/telegram_listener.py

Connect to Telegram via Telethon user session.
Subscribe to configured source chats/channels.
Forward raw messages to the signal processing pipeline.
Proactive session reset to prevent memory leaks.
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

# Type alias for reply callback.
# Receives: raw_text, chat_id, message_id, reply_to_msg_id
ReplyCallback = Callable[[str, str, str, str], Awaitable[None] | None]

# Type alias for delete callback.
# Receives: chat_id, message_ids
DeleteCallback = Callable[[str, list[str]], Awaitable[None] | None]


class TelegramListener:
    """Telethon-based Telegram listener.

    Uses a user session (not Bot API) to read from private
    groups and signal channels.

    Features:
    - Auto-reconnect on disconnect with exponential backoff.
    - Proactive session reset every N hours to prevent memory leaks.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str = "forex_bot",
        phone: str = "",
        source_chats: list[str | int] | None = None,
        session_reset_hours: int = 12,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_name = session_name
        self._phone = phone
        self._source_chats = source_chats or []
        self._session_reset_hours = session_reset_hours
        self._client: TelegramClient | None = None
        self._pipeline_cb: PipelineCallback | None = None
        self._edit_cb: EditCallback | None = None
        self._reply_cb: ReplyCallback | None = None
        self._delete_cb: DeleteCallback | None = None
        self._reset_task: asyncio.Task | None = None
        self._running = False

    def set_pipeline_callback(self, callback: PipelineCallback) -> None:
        """Set the callback for new signal messages."""
        self._pipeline_cb = callback

    def set_edit_callback(self, callback: EditCallback) -> None:
        """Set the callback for edited messages."""
        self._edit_cb = callback

    def set_reply_callback(self, callback: ReplyCallback) -> None:
        """Set the callback for reply messages."""
        self._reply_cb = callback

    def set_delete_callback(self, callback: DeleteCallback) -> None:
        """Set the callback for deleted messages."""
        self._delete_cb = callback

    @property
    def client(self) -> TelegramClient | None:
        """Expose client for alerter reuse."""
        return self._client

    @property
    def is_connected(self) -> bool:
        """Return True if Telethon client is active and connected."""
        return (
            self._client is not None
            and self._client.is_connected()
        )

    async def start(self) -> None:
        """Initialize Telethon client and start listening."""
        self._running = True
        await self._connect()

        # Start proactive session reset loop
        if self._session_reset_hours > 0:
            self._reset_task = asyncio.create_task(self._session_reset_loop())

    async def _connect(self) -> None:
        """Create client, connect, and register handlers."""
        self._client = TelegramClient(
            self._session_name,
            self._api_id,
            self._api_hash,
        )

        # Pass phone to avoid interactive prompt.
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

        # Register message deleted handler (P10.1)
        @self._client.on(events.MessageDeleted())
        async def on_message_deleted(event: events.MessageDeleted.Event) -> None:
            await self._handle_deleted_message(event)

        log_event(
            "telegram_listener_started",
            symbol="",
            chats_count=len(chat_entities),
        )

    async def _session_reset_loop(self) -> None:
        """Proactively reset Telethon session every N hours.

        Prevents memory leaks from long-running sessions.
        """
        interval = self._session_reset_hours * 3600
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break

                log_event("telegram_session_reset_start")

                # Disconnect and reconnect
                if self._client:
                    await self._client.disconnect()

                await self._connect()

                log_event("telegram_session_reset_complete")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event(
                    "telegram_session_reset_error",
                    error=str(exc),
                )
                # Wait before retry
                await asyncio.sleep(60)

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

        # Check if this is a reply to another message
        reply_to_id = getattr(message.reply_to, "reply_to_msg_id", None) if message.reply_to else None

        if reply_to_id and self._reply_cb:
            log_event(
                "reply_received",
                symbol="",
                source_chat_id=chat_id,
                source_message_id=message_id,
                reply_to_msg_id=str(reply_to_id),
                text_preview=raw_text[:80],
            )
            try:
                result = self._reply_cb(raw_text, chat_id, message_id, str(reply_to_id))
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log_event(
                    "reply_callback_error",
                    symbol="",
                    source_message_id=message_id,
                    error=str(exc),
                )
            return  # Don't fall through to signal parser

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

    async def _handle_deleted_message(
        self, event: events.MessageDeleted.Event
    ) -> None:
        """Process deleted message(s).

        Telethon provides only chat_id + deleted_ids (no message text).
        Forward to delete callback for fingerprint lookup + cancel.
        """
        chat_id = str(event.chat_id) if event.chat_id else ""
        deleted_ids = [str(mid) for mid in (event.deleted_ids or [])]

        if not deleted_ids:
            return

        # Filter: only process if chat_id is in our source chats
        # Note: event.chat_id may be None for private chats
        if chat_id and self._source_chats:
            source_ids = [str(c) for c in self._source_chats]
            if chat_id not in source_ids:
                return

        log_event(
            "message_deleted",
            symbol="",
            source_chat_id=chat_id,
            deleted_count=len(deleted_ids),
        )

        if self._delete_cb:
            try:
                result = self._delete_cb(chat_id, deleted_ids)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log_event(
                    "delete_callback_error",
                    symbol="",
                    source_chat_id=chat_id,
                    error=str(exc),
                )

    async def run_until_disconnected(self) -> None:
        """Block until the client disconnects. Auto-reconnect on failure."""
        max_retries = 10
        retry = 0

        while self._running:
            try:
                if self._client:
                    await self._client.run_until_disconnected()

                if not self._running:
                    break

                # Unexpected disconnect — reconnect
                retry += 1
                if retry > max_retries:
                    log_event(
                        "telegram_reconnect_exhausted",
                        max_retries=max_retries,
                    )
                    break

                delay = min(2 ** retry, 300)  # Exponential backoff, max 5 min
                log_event(
                    "telegram_reconnect",
                    attempt=retry,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
                await self._connect()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event(
                    "telegram_connection_error",
                    error=str(exc),
                )
                retry += 1
                if retry > max_retries:
                    break
                delay = min(2 ** retry, 300)
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        """Gracefully disconnect."""
        self._running = False
        if self._reset_task:
            self._reset_task.cancel()
            try:
                await self._reset_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.disconnect()
            log_event("telegram_listener_stopped", symbol="")
