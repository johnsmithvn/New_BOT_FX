"""
core/signal_parser/tp_detector.py

Detect Take Profit values from cleaned signal text.
Supports TP, TP1, TP2, TP3, and TAKE PROFIT patterns.
Returns deterministic ascending-ordered list.
Exception-safe: returns [] on failure.
"""

from __future__ import annotations

import re

# Numbered TP patterns: TP1, TP2, TP3, etc.
_TP_NUMBERED = re.compile(r"\bTP\s*(\d)\s*:?\s*(\d+\.?\d*)")

# Single TP pattern: TP or TAKE PROFIT
_TP_SINGLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bTAKE\s*PROFIT\s*:?\s*(\d+\.?\d*)"),
    re.compile(r"\bT/P\s*:?\s*(\d+\.?\d*)"),
    re.compile(r"\bTP\s*:?\s*(\d+\.?\d*)"),
]


def detect(text: str) -> list[float]:
    """Detect TP values from cleaned text.

    Returns sorted list of TP values (ascending).
    Returns empty list if none found.
    """
    try:
        if not text:
            return []

        tp_values: dict[int, float] = {}

        # Find numbered TPs first: TP1, TP2, TP3
        for match in _TP_NUMBERED.finditer(text):
            index = int(match.group(1))
            value = float(match.group(2))
            if value > 0:
                tp_values[index] = value

        # If numbered TPs found, return sorted by index
        if tp_values:
            return [tp_values[k] for k in sorted(tp_values.keys())]

        # Try single TP patterns
        for pattern in _TP_SINGLE_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                values = []
                for m in matches:
                    v = float(m)
                    if v > 0:
                        values.append(v)
                if values:
                    return sorted(set(values))

        return []
    except Exception:
        return []
