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
    parse_confidence: float = 1.0     # 0.0-1.0, how confident the parser is
    parse_source: str = "standard"    # which parser/rule produced this signal


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


# ── P9: Channel-Driven Strategy Architecture ────────────────────


class SignalLifecycle(str, enum.Enum):
    """State machine for active signal tracking (P9).

    Transitions:
        PENDING → PARTIAL  (first entry executed)
        PARTIAL → COMPLETED (all entries done or cancelled)
        PENDING → EXPIRED  (TTL exceeded)
        PARTIAL → EXPIRED  (TTL exceeded, cancel remaining)
    """

    PENDING = "pending"        # Signal received, plans created, nothing executed
    PARTIAL = "partial"        # At least one entry executed, more pending
    COMPLETED = "completed"    # All entry plans executed or cancelled
    EXPIRED = "expired"        # TTL exceeded, remaining plans cancelled


@dataclass
class EntryPlan:
    """One planned entry within a signal's strategy.

    Each plan represents a specific price level where an order
    should be placed. Multiple plans per signal = multi-order.
    """

    level: float              # Entry price for this order
    order_kind: OrderKind     # MARKET / BUY_LIMIT / BUY_STOP / SELL_LIMIT / SELL_STOP
    level_id: int             # 0 = initial, 1+ = re-entry
    label: str = ""           # Human-readable: "initial", "range_1", "reentry_2"
    status: str = "pending"   # pending / executed / cancelled


@dataclass
class SignalState:
    """Runtime state of an active signal being managed (P9).

    Tracks the lifecycle of a signal that may produce
    multiple orders over time (range/scale_in strategies).

    For 'single' mode signals, this is not used (fire-and-forget).
    """

    fingerprint: str          # Base fingerprint (from parser)
    symbol: str
    side: Side
    entry_range: list[float] | None  # [low, high] or None
    sl: float | None
    tp: list[float]
    source_chat_id: str
    source_message_id: str
    channel_id: str
    # Plan & tracking
    entry_plans: list[EntryPlan] = field(default_factory=list)
    total_volume: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=datetime.utcnow)
    # State machine
    status: SignalLifecycle = SignalLifecycle.PENDING
    last_price: float | None = None  # For price-cross detection


def order_fingerprint(base_fp: str, level_id: int) -> str:
    """Generate unique order fingerprint for multi-order signals.

    Each order gets a distinct fingerprint for debugging and tracking,
    while preserving the base fingerprint link to the original signal.

    Args:
        base_fp: Signal's base fingerprint from parser.
        level_id: Entry plan level (0 = initial, 1+ = re-entry).

    Returns:
        "{base_fp}:L{level_id}" — e.g. "a1b2c3d4:L0", "a1b2c3d4:L1"

    Usage:
        - Signal lookup / dedup: use base_fp
        - Order identification / debug: use order_fingerprint
        - Reply handler: uses source_message_id (not fingerprint)
    """
    return f"{base_fp}:L{level_id}"

