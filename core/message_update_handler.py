"""
core/message_update_handler.py

Handle Telegram MessageEdited events.
Detect updates to previously processed signals.
Decide whether to ignore, update, or cancel.
Prevent duplicate or conflicting trades from edited messages.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone

from core.models import ParsedSignal, ParseFailure
from core.signal_parser.parser import SignalParser
from core.storage import Storage
from utils.logger import log_event


class UpdateAction(str, enum.Enum):
    """Action to take on an edited message."""
    IGNORE = "ignore"
    UPDATE_ORDER = "update_order"
    CANCEL_ORDER = "cancel_order"
    NEW_SIGNAL = "new_signal"


@dataclass
class UpdateDecision:
    """Decision result for an edited message."""
    action: UpdateAction
    reason: str
    original_fingerprint: str = ""
    new_signal: ParsedSignal | None = None


class MessageUpdateHandler:
    """Handle Telegram MessageEdited events.

    Flow:
    1. Re-parse the edited message.
    2. Compare new fingerprint against stored original.
    3. Decide action:
       - Same fingerprint → ignore (no material change).
       - Different fingerprint + original order pending → cancel old + treat as new.
       - Different fingerprint + original order executed → ignore (too late).
       - Parse failure on edit → ignore (corrupted edit).
    """

    def __init__(self, parser: SignalParser, storage: Storage) -> None:
        self._parser = parser
        self._storage = storage

    def handle_edit(
        self,
        edited_text: str,
        source_chat_id: str,
        source_message_id: str,
        original_fingerprint: str,
    ) -> UpdateDecision:
        """Process an edited message and decide action.

        Args:
            edited_text: The new (edited) message text.
            source_chat_id: Chat/channel ID.
            source_message_id: Original message ID.
            original_fingerprint: Fingerprint of the original signal.

        Returns:
            UpdateDecision describing what action to take.
        """
        try:
            return self._do_handle(
                edited_text,
                source_chat_id,
                source_message_id,
                original_fingerprint,
            )
        except Exception as exc:
            log_event(
                "edit_handler_error",
                fingerprint=original_fingerprint,
                error=str(exc),
            )
            return UpdateDecision(
                action=UpdateAction.IGNORE,
                reason=f"edit handler error: {exc}",
                original_fingerprint=original_fingerprint,
            )

    def _do_handle(
        self,
        edited_text: str,
        source_chat_id: str,
        source_message_id: str,
        original_fingerprint: str,
    ) -> UpdateDecision:
        """Internal handler logic."""

        # Step 1: Re-parse edited message
        result = self._parser.parse(
            edited_text,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )

        # If re-parse fails, ignore the edit
        if isinstance(result, ParseFailure):
            log_event(
                "edit_parse_failed",
                fingerprint=original_fingerprint,
                reason=result.reason,
            )
            return UpdateDecision(
                action=UpdateAction.IGNORE,
                reason=f"edited message parse failed: {result.reason}",
                original_fingerprint=original_fingerprint,
            )

        new_signal: ParsedSignal = result

        # Step 2: Compare fingerprints
        if new_signal.fingerprint == original_fingerprint:
            log_event(
                "edit_no_change",
                fingerprint=original_fingerprint,
                symbol=new_signal.symbol,
            )
            return UpdateDecision(
                action=UpdateAction.IGNORE,
                reason="no material change in signal",
                original_fingerprint=original_fingerprint,
            )

        # Step 3: Fingerprint changed — check original order status
        # TODO: P2 — query MT5 for actual order status (pending vs executed)
        # For now, recommend cancel + new signal approach

        log_event(
            "edit_signal_changed",
            fingerprint=original_fingerprint,
            new_fingerprint=new_signal.fingerprint,
            symbol=new_signal.symbol,
        )

        return UpdateDecision(
            action=UpdateAction.CANCEL_ORDER,
            reason="signal parameters changed, cancel original order",
            original_fingerprint=original_fingerprint,
            new_signal=new_signal,
        )
