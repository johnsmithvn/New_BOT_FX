"""
core/signal_parser/cleaner.py

Normalize raw Telegram message text for downstream detectors.
"""

from __future__ import annotations

import re
import unicodedata


def clean(raw_text: str, max_length: int = 2000) -> str | None:
    """Clean and normalize a raw signal message.

    Returns cleaned text or None if the message is rejected
    (empty or exceeds max length).

    Steps:
    1. Guard: reject oversized messages.
    2. Strip emoji and non-printable characters.
    3. Normalize to uppercase.
    4. Collapse excessive whitespace and blank lines.
    5. Strip leading/trailing whitespace per line.
    """
    if not raw_text or not raw_text.strip():
        return None

    if len(raw_text) > max_length:
        return None

    text = _strip_emoji(raw_text)
    text = _strip_non_printable(text)
    text = text.upper()
    text = _normalize_whitespace(text)
    text = text.strip()

    if not text:
        return None

    return text


def _strip_emoji(text: str) -> str:
    """Remove emoji and pictographic characters."""
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("So", "Sk", "Cs")
    )


def _strip_non_printable(text: str) -> str:
    """Remove non-printable control characters except newline/tab."""
    return "".join(
        ch for ch in text
        if ch in ("\n", "\t") or (ch.isprintable())
    )


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces and blank lines."""
    # Replace tabs with spaces
    text = text.replace("\t", " ")
    # Collapse multiple spaces into one (per line)
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = re.sub(r" {2,}", " ", line).strip()
        if stripped:
            cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)
