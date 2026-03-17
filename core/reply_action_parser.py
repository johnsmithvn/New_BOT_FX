"""
core/reply_action_parser.py

Parse reply messages into trade management actions.

Separate from signal parser — replies are short imperative commands
("close", "SL 2035") vs full signals (symbol + side + entry + SL + TP).

Patterns are hardcoded defaults. Per-channel keyword overrides
can be added via channels.json in a future iteration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ReplyActionType(str, Enum):
    """Supported reply actions."""
    CLOSE = "close"
    CLOSE_PARTIAL = "close_partial"
    MOVE_SL = "move_sl"
    MOVE_TP = "move_tp"
    BREAKEVEN = "breakeven"


@dataclass
class ReplyAction:
    """Parsed reply action."""
    action: ReplyActionType
    price: float | None = None
    percent: int | None = None
    raw_text: str = ""


# ── Pattern definitions ──────────────────────────────────────────
# Order matters: more specific patterns first.

_CLOSE_WORDS = r"^(close|exit|out|đóng|đóng lệnh|close trade)$"
_CLOSE_PARTIAL = r"^close\s+(\d+)\s*%$"
_MOVE_SL = r"^(?:sl|move\s+sl|stoploss|stop\s+loss)\s+([\d]+(?:\.[\d]+)?)$"
_MOVE_TP = r"^(?:tp|move\s+tp|take\s+profit)\s+([\d]+(?:\.[\d]+)?)$"
_BREAKEVEN = r"^(be|breakeven|break\s+even|sl\s+entry)$"


class ReplyActionParser:
    """Parse reply text into a trade management action.

    Returns ReplyAction if the text matches a known pattern,
    or None if the text is not an actionable command (e.g. just a comment).

    To add custom keywords:
    - Subclass and override ``parse()``
    - Or add per-channel keyword maps to channels.json (future)
    """

    def parse(self, text: str) -> ReplyAction | None:
        """Try to parse text as a reply action.

        Validation rules:
        - MOVE_SL / MOVE_TP → price is required (else None)
        - CLOSE_PARTIAL → percent must be 1-100 (else None)
        """
        if not text or not text.strip():
            return None

        cleaned = text.strip()
        # Normalise whitespace
        cleaned_upper = re.sub(r"\s+", " ", cleaned).strip()
        # Keep original case for Vietnamese keywords, uppercase for matching
        match_text = cleaned_upper.upper()
        # Also try lowercase for Vietnamese
        match_lower = cleaned_upper.lower()

        # BREAKEVEN (before CLOSE to avoid "be" matching something else)
        if re.match(_BREAKEVEN, match_text, re.IGNORECASE):
            return ReplyAction(
                action=ReplyActionType.BREAKEVEN,
                raw_text=cleaned,
            )

        # CLOSE PARTIAL — "close 30%"
        m = re.match(_CLOSE_PARTIAL, match_text, re.IGNORECASE)
        if m:
            percent = int(m.group(1))
            if percent <= 0 or percent > 100:
                return None  # Invalid range
            return ReplyAction(
                action=ReplyActionType.CLOSE_PARTIAL,
                percent=percent,
                raw_text=cleaned,
            )

        # CLOSE — exact match
        if re.match(_CLOSE_WORDS, match_lower, re.IGNORECASE):
            return ReplyAction(
                action=ReplyActionType.CLOSE,
                raw_text=cleaned,
            )

        # MOVE SL — "SL 2035" or "move sl 2035.50"
        m = re.match(_MOVE_SL, match_text, re.IGNORECASE)
        if m:
            price = float(m.group(1))
            if price <= 0:
                return None
            return ReplyAction(
                action=ReplyActionType.MOVE_SL,
                price=price,
                raw_text=cleaned,
            )

        # MOVE TP — "TP 2045" or "move tp 2045.50"
        m = re.match(_MOVE_TP, match_text, re.IGNORECASE)
        if m:
            price = float(m.group(1))
            if price <= 0:
                return None
            return ReplyAction(
                action=ReplyActionType.MOVE_TP,
                price=price,
                raw_text=cleaned,
            )

        # Not a recognised action
        return None
