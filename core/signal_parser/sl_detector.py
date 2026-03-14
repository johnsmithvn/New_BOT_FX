"""
core/signal_parser/sl_detector.py

Detect Stop Loss value from cleaned signal text.
Strict numeric extraction only.
Exception-safe: returns None on failure.
"""

from __future__ import annotations

import re

# SL patterns — ordered by specificity.
_SL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bSTOP\s*LOSS\s*:?\s*(\d+\.?\d*)"),
    re.compile(r"\bSTOPLOSS\s*:?\s*(\d+\.?\d*)"),
    re.compile(r"\bSL\s*:?\s*(\d+\.?\d*)"),
    re.compile(r"\bS/L\s*:?\s*(\d+\.?\d*)"),
]


def detect(text: str) -> float | None:
    """Detect SL price from cleaned text.

    Returns SL value as float, or None if not found.
    """
    try:
        if not text:
            return None

        for pattern in _SL_PATTERNS:
            match = pattern.search(text)
            if match:
                value = float(match.group(1))
                if value > 0:
                    return value

        return None
    except Exception:
        return None
