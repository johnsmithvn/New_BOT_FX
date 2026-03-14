"""
core/signal_parser/side_detector.py

Detect BUY or SELL direction from cleaned signal text.
Handles LONG/SHORT aliases and order-type suffixes.
Exception-safe: returns None on failure.
"""

from __future__ import annotations

import re

# Ordered patterns — more specific first to avoid partial matches.
_SIDE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Explicit BUY/SELL with optional order type suffix
    (re.compile(r"\bBUY\s*STOP\b"), "BUY"),
    (re.compile(r"\bBUY\s*LIMIT\b"), "BUY"),
    (re.compile(r"\bSELL\s*STOP\b"), "SELL"),
    (re.compile(r"\bSELL\s*LIMIT\b"), "SELL"),
    (re.compile(r"\bBUY\b"), "BUY"),
    (re.compile(r"\bSELL\b"), "SELL"),
    # LONG/SHORT aliases
    (re.compile(r"\bLONG\b"), "BUY"),
    (re.compile(r"\bSHORT\b"), "SELL"),
]


def detect(text: str) -> str | None:
    """Detect trade direction from cleaned text.

    Returns "BUY" or "SELL", or None if no direction detected.
    """
    try:
        if not text:
            return None

        for pattern, side in _SIDE_PATTERNS:
            if pattern.search(text):
                return side

        return None
    except Exception:
        return None
