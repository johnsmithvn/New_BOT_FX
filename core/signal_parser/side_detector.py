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
    # Exact keywords
    (re.compile(r"\bBUY\b"), "BUY"),
    (re.compile(r"\bSELL\b"), "SELL"),
    # LONG/SHORT aliases
    (re.compile(r"\bLONG\b"), "BUY"),
    (re.compile(r"\bSHORT\b"), "SELL"),
    # ── Common typos (safe: no collision with real English words) ──
    # SELL variants
    (re.compile(r"\bSEL\b"), "SELL"),       # missing L
    (re.compile(r"\bSELL+\b"), "SELL"),     # extra L(s): SELLL, SELLLL
    (re.compile(r"\bSEEL\b"), "SELL"),      # doubled E
    (re.compile(r"\bSSEL+\b"), "SELL"),     # doubled S: SSEL, SSELL
    (re.compile(r"\bSEELL\b"), "SELL"),     # double E + double L
    # BUY variants
    (re.compile(r"\bBBUY\b"), "BUY"),      # doubled B
    (re.compile(r"\bBUUY\b"), "BUY"),      # doubled U
    (re.compile(r"\bBYU\b"), "BUY"),       # transposition
    # NOTE: BY, BU intentionally excluded — too common in English
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
