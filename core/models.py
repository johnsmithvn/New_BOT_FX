"""
core/models.py

Data contracts for the signal processing pipeline.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime


class Side(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderKind(str, enum.Enum):
    MARKET = "MARKET"
    BUY_LIMIT = "BUY_LIMIT"
    BUY_STOP = "BUY_STOP"
    SELL_LIMIT = "SELL_LIMIT"
    SELL_STOP = "SELL_STOP"


class SignalStatus(str, enum.Enum):
    RECEIVED = "received"
    PARSED = "parsed"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    EXECUTED = "executed"
    FAILED = "failed"


@dataclass
class ParsedSignal:
    """Normalized signal extracted from a Telegram message."""

    symbol: str
    side: Side
    entry: float | None  # None means market execution
    sl: float | None
    entry_range: list[float] | None = None  # [low, high] if range detected
    tp: list[float] = field(default_factory=list)
    raw_text: str = ""
    source_chat_id: str = ""
    source_message_id: str = ""
    received_at: datetime = field(default_factory=datetime.utcnow)
    fingerprint: str = ""


@dataclass
class ParseFailure:
    """Structured failure when the parser cannot interpret a message."""

    reason: str
    raw_text: str = ""
    source_chat_id: str = ""
    source_message_id: str = ""
    received_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradeDecision:
    """Order decision produced by the order builder."""

    order_kind: OrderKind
    price: float | None = None
    sl: float | None = None
    tp: float | None = None


@dataclass
class ExecutionResult:
    """Normalized result from MT5 order execution."""

    success: bool
    retcode: int
    ticket: int | None = None
    message: str = ""
