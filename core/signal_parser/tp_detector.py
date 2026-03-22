"""
core/signal_parser/tp_detector.py

Detect Take Profit values from cleaned signal text.
Supports TP, TP1, TP2, TP3, and TAKE PROFIT patterns.
Returns deterministic ascending-ordered list.
Exception-safe: returns [] on failure.

IMPORTANT: Relative offsets like "TP: 30 PIPS" are NOT valid TPs.
Only absolute price levels are captured.
"""

from __future__ import annotations

import re

# Relative TP indicator — values followed by these are pip offsets, not prices.
_RELATIVE_SUFFIX = re.compile(r"\bPIPS?\b|\bPOINTS?\b|\bPTS?\b")

# Numbered TP patterns: TP1, TP2, TP3, etc.
# Capture the number AND the trailing word (same line only) to check for pip keywords.
_TP_NUMBERED = re.compile(r"\bTP\s*(\d)\s*:?\s*(\d+\.?\d*)[ ]*(\w*)")

# Single TP pattern: TP or TAKE PROFIT
# (?!\d) prevents matching TP1/TP2 (numbered TPs handled above)
_TP_SINGLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bTAKE\s*PROFIT\s*:?\s*(\d+\.?\d*)[ ]*(\w*)"),
    re.compile(r"\bT/P\s*:?\s*(\d+\.?\d*)[ ]*(\w*)"),
    re.compile(r"\bTP(?!\d)\s*:?\s*(\d+\.?\d*)[ ]*(\w*)"),
]


def _is_relative(suffix: str) -> bool:
    """Check if the word after the number indicates a relative offset."""
    return bool(_RELATIVE_SUFFIX.match(suffix))


def detect(text: str) -> list[float]:
    """Detect TP values from cleaned text.

    Returns sorted list of TP values (ascending).
    Returns empty list if none found.

    Skips relative pip offsets (e.g., "TP: 30 PIPS").
    """
    try:
        if not text:
            return []

        tp_values: dict[int, float] = {}

        # Find numbered TPs first: TP1, TP2, TP3
        for match in _TP_NUMBERED.finditer(text):
            index = int(match.group(1))
            value = float(match.group(2))
            suffix = match.group(3)
            if value > 0 and not _is_relative(suffix):
                tp_values[index] = value

        # If numbered TPs found, return sorted by index
        if tp_values:
            return [tp_values[k] for k in sorted(tp_values.keys())]

        # Try single TP patterns
        for pattern in _TP_SINGLE_PATTERNS:
            values: list[float] = []
            for match in pattern.finditer(text):
                v = float(match.group(1))
                suffix = match.group(2)
                if v > 0 and not _is_relative(suffix):
                    values.append(v)
            if values:
                return sorted(set(values))

        return []
    except Exception:
        return []
