"""
core/signal_parser/entry_detector.py

Detect entry price from cleaned signal text.
Returns None when "market" / "now" intent is detected (meaning execute at market).
Exception-safe: returns None on failure.
"""

from __future__ import annotations

import re

from core.models import Side

# Pattern for explicit numeric entry range.
# Matches: ENTRY 2030 - 2035, BUY 2030/2035, BUY GOLD 2030 TO 2035
_ENTRY_RANGE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bENTRY\s*(?:PRICE)?\s*:?\s*(\d+\.?\d*)\s*(?:-|/|TO)\s*(\d+\.?\d*)"),
    re.compile(r"\b(?:BUY|SELL|LONG|SHORT)\s+(?:[A-Z]+\s+)?(\d+\.?\d*)\s*(?:-|/|TO)\s*(\d+\.?\d*)"),
]

# Pattern for explicit numeric entry price.
# Matches: ENTRY 2030, ENTRY PRICE 2030.50, ENTRY: 2030, @ 2030
_ENTRY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bENTRY\s*(?:PRICE)?\s*:?\s*(\d+\.?\d*)"),
    re.compile(r"@\s*(\d+\.?\d*)"),
    re.compile(r"\bPRICE\s*:?\s*(\d+\.?\d*)"),
    re.compile(r"\bENTER\s*(?:AT)?\s*:?\s*(\d+\.?\d*)"),
]

# Market execution keywords — if found AND no numeric entry, treat as market.
_MARKET_KEYWORDS = re.compile(
    r"\b(?:NOW|MARKET|MARKET\s*(?:PRICE|EXECUTION)|CMP|CURRENT\s*(?:MARKET\s*)?PRICE)\b"
)


def detect(text: str, side: Side | None = None) -> tuple[float | None, list[float] | None, bool]:
    """Detect entry price and range from cleaned text.

    Returns:
        tuple (entry, entry_range, is_market):
        - entry: float | None (Explicit entry price)
        - entry_range: list[float] | None ([low, high] if range detected)
        - is_market: bool (True if explicit market keywords found)
    """
    try:
        if not text:
            return None, None, False

        # Try explicit entry range first
        for pattern in _ENTRY_RANGE_PATTERNS:
            match = pattern.search(text)
            if match:
                val1 = float(match.group(1))
                val2 = float(match.group(2))
                low = min(val1, val2)
                high = max(val1, val2)
                
                if low > 0 and high > 0:
                    entry_range = [low, high]
                    # Determine entry based on side
                    if side == Side.BUY:
                        entry = low
                    elif side == Side.SELL:
                        entry = high
                    else:
                        entry = low  # fallback
                    return entry, entry_range, False

        # Try explicit entry patterns first
        for pattern in _ENTRY_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(1)
                price = float(value)
                if price > 0:
                    return price, None, False

        # Check for market keywords
        if _MARKET_KEYWORDS.search(text):
            return None, None, True

        # Try to find a standalone price near BUY/SELL keyword.
        # Pattern: BUY <price> or SELL <price> (not followed by SL/TP keywords)
        side_price = re.search(
            r"\b(?:BUY|SELL|LONG|SHORT)\s+(?:[A-Z]+\s+)?(\d+\.?\d*)\b",
            text,
        )
        if side_price:
            price = float(side_price.group(1))
            if price > 0:
                return price, None, False

        return None, None, False
    except Exception:
        return None, None, False
