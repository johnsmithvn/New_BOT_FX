"""
core/signal_parser/entry_detector.py

Detect entry price from cleaned signal text.
Returns None when "market" / "now" intent is detected (meaning execute at market).
Exception-safe: returns None on failure.
"""

from __future__ import annotations

import re

from core.models import Side

# Side keywords for entry patterns — must stay in sync with side_detector.py
_SIDE_KW = r"(?:BUY|SELL|SEL|LONG|SHORT|BBUY|BUUY|BYU|SEEL|SSEL|SSELL|SEELL)"

# Pattern for explicit numeric entry range.
# Matches: ENTRY 2030 - 2035, BUY GOLD 2030/2035, BUY GOLD ZONE 2030 TO 2035
_ENTRY_RANGE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bENTRY\s*(?:PRICE)?\s*:?\s*(\d+\.?\d*)\s*[-\u2013/]\s*(\d+\.?\d*)"),
    re.compile(r"\bENTRY\s*(?:PRICE)?\s*:?\s*(\d+\.?\d*)\s+TO\s+(\d+\.?\d*)"),
    re.compile(rf"\b{_SIDE_KW}\s+(?:[A-Z]+\s+)*(\d+\.?\d*)\s*[-\u2013/]\s*(\d+\.?\d*)"),
    re.compile(rf"\b{_SIDE_KW}\s+(?:[A-Z]+\s+)*(\d+\.?\d*)\s+TO\s+(\d+\.?\d*)"),
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


def detect(text: str, side: Side | None = None) -> tuple[float | None, list[float] | None, bool, bool]:
    """Detect entry price and range from cleaned text.

    Returns:
        tuple (entry, entry_range, is_market, is_now):
        - entry: float | None (Explicit entry price)
        - entry_range: list[float] | None ([low, high] if range detected)
        - is_market: bool (True if explicit market keywords found AND no entry)
        - is_now: bool (True if NOW/MARKET keyword found, even alongside entry)
    """
    try:
        if not text:
            return None, None, False, False

        # Detect NOW/MARKET keywords early — used by order_builder
        # to force MARKET when price is within zone.
        has_now = bool(_MARKET_KEYWORDS.search(text))

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
                    return entry, entry_range, False, has_now

        # Try explicit entry patterns first
        for pattern in _ENTRY_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(1)
                price = float(value)
                if price > 0:
                    return price, None, False, has_now

        # Try to find a standalone price near BUY/SELL keyword.
        # Pattern: BUY <price> or SELL <price> (allows multiple words in between)
        side_price = re.search(
            rf"\b{_SIDE_KW}\s+(?:[A-Z]+\s+)*(\d+\.?\d*)\b",
            text,
        )
        if side_price:
            price = float(side_price.group(1))
            if price > 0:
                return price, None, False, has_now

        # No entry found — if NOW keyword present, treat as pure MARKET
        if has_now:
            return None, None, True, True

        return None, None, False, False
    except Exception:
        return None, None, False, False
