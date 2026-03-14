"""
core/signal_parser/entry_detector.py

Detect entry price from cleaned signal text.
Returns None when "market" / "now" intent is detected (meaning execute at market).
Exception-safe: returns None on failure.
"""

from __future__ import annotations

import re

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


def detect(text: str) -> float | None:
    """Detect entry price from cleaned text.

    Returns:
        float: Explicit entry price.
        None: Market execution intent or no entry detected.
    """
    try:
        if not text:
            return None

        # Try explicit entry patterns first
        for pattern in _ENTRY_PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(1)
                price = float(value)
                if price > 0:
                    return price

        # Check for market keywords
        if _MARKET_KEYWORDS.search(text):
            return None

        # Try to find a standalone price near BUY/SELL keyword.
        # Pattern: BUY <price> or SELL <price> (not followed by SL/TP keywords)
        side_price = re.search(
            r"\b(?:BUY|SELL|LONG|SHORT)\s+(\d+\.?\d*)\b",
            text,
        )
        if side_price:
            price = float(side_price.group(1))
            if price > 0:
                return price

        return None
    except Exception:
        return None
