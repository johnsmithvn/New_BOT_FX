"""
core/signal_parser/parser.py

Orchestrate all detectors to produce a ParsedSignal or ParseFailure.
Generates signal fingerprint from normalized fields.
Exception-safe: never crashes on malformed input.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from core.models import ParsedSignal, ParseFailure, Side
from core.signal_parser import cleaner, symbol_detector, side_detector
from core.signal_parser import entry_detector, sl_detector, tp_detector
from utils.symbol_mapper import SymbolMapper


def generate_fingerprint(
    symbol: str,
    side: str,
    entry: float | None,
    sl: float | None,
    tp_list: list[float],
    source_chat_id: str = "",
) -> str:
    """Generate a deterministic fingerprint from normalized signal fields.

    Uses SHA-256 hash of concatenated fields.
    Includes source_chat_id to isolate dedup per channel (v0.6.0).

    BREAKING CHANGE: fingerprints from v0.5.x are NOT compatible
    with v0.6.0 due to the added source_chat_id prefix.
    """
    parts = [
        source_chat_id,
        symbol,
        side,
        str(entry) if entry is not None else "MARKET",
        str(sl) if sl is not None else "NONE",
        "|".join(str(t) for t in tp_list),
    ]
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class SignalParser:
    """Orchestrate the signal parsing pipeline.

    Flow:
    1. Clean raw text.
    2. Detect symbol.
    3. Detect side (BUY/SELL).
    4. Detect entry price.
    5. Detect SL.
    6. Detect TPs.
    7. Generate fingerprint.
    8. Return ParsedSignal or ParseFailure.
    """

    def __init__(
        self,
        symbol_mapper: SymbolMapper | None = None,
        max_message_length: int = 2000,
    ) -> None:
        self._mapper = symbol_mapper or SymbolMapper()
        self._max_length = max_message_length

    def parse(
        self,
        raw_text: str,
        source_chat_id: str = "",
        source_message_id: str = "",
        received_at: datetime | None = None,
    ) -> ParsedSignal | ParseFailure:
        """Parse a raw signal message.

        Args:
            raw_text: Raw Telegram message text.
            source_chat_id: Source chat/channel ID.
            source_message_id: Message ID.
            received_at: Timestamp when message was received.

        Returns:
            ParsedSignal on success, ParseFailure on failure.
        """
        if received_at is None:
            received_at = datetime.now(timezone.utc)

        common = {
            "raw_text": raw_text,
            "source_chat_id": source_chat_id,
            "source_message_id": source_message_id,
            "received_at": received_at,
        }

        try:
            return self._do_parse(raw_text, common)
        except Exception as exc:
            return ParseFailure(
                reason=f"unexpected parser error: {exc}",
                **common,
            )

    def _do_parse(
        self,
        raw_text: str,
        common: dict,
    ) -> ParsedSignal | ParseFailure:
        """Internal parse logic. May raise — caller wraps in try/except."""

        # Step 1: Clean
        cleaned = cleaner.clean(raw_text, max_length=self._max_length)
        if cleaned is None:
            return ParseFailure(
                reason="message rejected: empty or exceeds max length",
                **common,
            )

        # Step 2: Detect symbol
        symbol = symbol_detector.detect(cleaned, mapper=self._mapper)
        if symbol is None:
            return ParseFailure(
                reason="symbol not detected",
                **common,
            )

        # Step 3: Detect side
        side_str = side_detector.detect(cleaned)
        if side_str is None:
            return ParseFailure(
                reason="side not detected (BUY/SELL/LONG/SHORT)",
                **common,
            )
        side = Side(side_str)

        # Step 4: Detect entry
        entry, entry_range, is_market = entry_detector.detect(cleaned, side)

        # Reject if entry cannot be determined AND there is no explicit market intent
        if entry is None and not is_market:
            return ParseFailure(
                reason="entry price not detected and no explicit market keywords found",
                **common,
            )

        # Step 5: Detect SL
        sl = sl_detector.detect(cleaned)

        # Step 6: Detect TPs
        tp_list = tp_detector.detect(cleaned)

        # Step 7: Generate fingerprint (includes source_chat_id for channel isolation)
        fingerprint = generate_fingerprint(
            symbol=symbol,
            side=side_str,
            entry=entry,
            sl=sl,
            tp_list=tp_list,
            source_chat_id=common.get("source_chat_id", ""),
        )

        return ParsedSignal(
            symbol=symbol,
            side=side,
            entry=entry,
            entry_range=entry_range,
            sl=sl,
            tp=tp_list,
            fingerprint=fingerprint,
            **common,
        )
