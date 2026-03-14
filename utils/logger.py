"""
utils/logger.py

Structured JSON logging via loguru.
All signal events include fingerprint, symbol, and timestamp.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


def setup_logger(level: str = "INFO", file_path: str = "logs/bot.log",
                 rotation: str = "10 MB") -> None:
    """Configure loguru sinks.

    - Console sink: human-readable for development.
    - File sink: structured JSON for traceability.
    """
    logger.remove()  # remove default stderr sink

    # Console: concise human-readable
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        ),
        colorize=True,
    )

    # File: structured JSON
    log_dir = Path(file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        file_path,
        level=level,
        format="{message}",
        rotation=rotation,
        retention="30 days",
        serialize=True,
    )


def log_event(
    event: str,
    fingerprint: str = "",
    symbol: str = "",
    **extra: object,
) -> None:
    """Emit a structured signal lifecycle event.

    All events include: event type, fingerprint, symbol, timestamp.
    Additional fields can be passed via **extra.

    Args:
        event: Event type (signal_received, parse_success, etc.).
        fingerprint: Unique signal fingerprint.
        symbol: Trading symbol.
        **extra: Additional key-value pairs for the event.
    """
    payload = {
        "event": event,
        "fingerprint": fingerprint,
        "symbol": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra,
    }

    logger.bind(**payload).info(
        "{event} | {symbol} | {fingerprint}",
        event=event,
        symbol=symbol,
        fingerprint=fingerprint,
    )
