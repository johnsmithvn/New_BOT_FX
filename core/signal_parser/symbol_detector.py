"""
core/signal_parser/symbol_detector.py

Detect trading symbol from cleaned signal text.
Uses SymbolMapper for alias resolution.
Exception-safe: returns None on failure.
"""

from __future__ import annotations

import re

from utils.symbol_mapper import SymbolMapper

# Pre-compiled pattern to find symbol-like tokens.
# Matches 3-10 uppercase letter sequences that could be symbols.
_SYMBOL_PATTERN = re.compile(r"\b([A-Z]{3,10})\b")


def detect(text: str, mapper: SymbolMapper | None = None) -> str | None:
    """Detect and resolve the trading symbol from cleaned text.

    Strategy:
    1. Try explicit symbol patterns first (e.g. "XAUUSD", "GOLD").
    2. Try compound patterns like "XAU/USD" or "XAU USD".
    3. Resolve via SymbolMapper alias map.

    Returns broker-normalized symbol or None.
    """
    try:
        if mapper is None:
            mapper = SymbolMapper()

        if not text:
            return None

        # Try slash-separated pair first (e.g. "XAU/USD")
        slash_match = re.search(r"\b([A-Z]{2,5})\s*/\s*([A-Z]{2,5})\b", text)
        if slash_match:
            combined = slash_match.group(1) + slash_match.group(2)
            resolved = mapper.resolve(combined)
            if resolved:
                return resolved

        # Find all uppercase tokens and try to resolve each
        matches = _SYMBOL_PATTERN.findall(text)
        for token in matches:
            resolved = mapper.resolve(token)
            if resolved:
                return resolved

        return None
    except Exception:
        return None
