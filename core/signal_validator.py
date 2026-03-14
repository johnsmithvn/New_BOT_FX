"""
core/signal_validator.py

Validate parsed signals before trade execution.
Enforces safety rules and coherence checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.models import ParsedSignal, Side


@dataclass
class ValidationResult:
    """Result of signal validation."""

    valid: bool
    reason: str = ""


class SignalValidator:
    """Validate parsed signals against safety rules.

    Rules enforced:
    1. Required fields present (symbol, side).
    2. SL/TP numeric coherence relative to entry and side.
    3. Entry distance from reference price.
    4. Signal age (reject stale signals).
    5. Spread threshold check.
    6. Max open trades gate.
    7. Duplicate filtering via fingerprint.
    """

    def __init__(
        self,
        max_entry_distance_points: int = 500,
        signal_age_ttl_seconds: int = 60,
        max_spread_points: int = 50,
        max_open_trades: int = 5,
    ) -> None:
        self._max_entry_distance = max_entry_distance_points
        self._signal_age_ttl = signal_age_ttl_seconds
        self._max_spread = max_spread_points
        self._max_open_trades = max_open_trades

    def validate(
        self,
        signal: ParsedSignal,
        current_price: float | None = None,
        current_spread: float | None = None,
        open_positions: int | None = None,
        is_duplicate: bool = False,
    ) -> ValidationResult:
        """Run all validation checks on a parsed signal.

        Args:
            signal: The parsed signal to validate.
            current_price: Current market reference price (bid for SELL,
                          ask for BUY). None if unavailable.
            current_spread: Current spread in points. None if unavailable.
            open_positions: Number of currently open positions. None if unavailable.
            is_duplicate: True if signal fingerprint was found in dedupe window.

        Returns:
            ValidationResult with valid=True or reason for rejection.
        """
        # Rule 1: Required fields
        if not signal.symbol:
            return ValidationResult(False, "missing symbol")

        if not signal.side:
            return ValidationResult(False, "missing side")

        # Rule 2: Duplicate filter
        if is_duplicate:
            return ValidationResult(
                False,
                f"duplicate signal (fingerprint: {signal.fingerprint[:8]})",
            )

        # Rule 3: SL coherence
        result = self._validate_sl_coherence(signal)
        if not result.valid:
            return result

        # Rule 4: TP coherence
        result = self._validate_tp_coherence(signal)
        if not result.valid:
            return result

        # Rule 5: Entry distance (requires current_price)
        if current_price is not None and signal.entry is not None:
            result = self._validate_entry_distance(signal, current_price)
            if not result.valid:
                return result

        # Rule 6: Signal age
        result = self._validate_signal_age(signal)
        if not result.valid:
            return result

        # Rule 7: Spread gate
        if current_spread is not None:
            result = self._validate_spread(current_spread)
            if not result.valid:
                return result

        # Rule 8: Max open trades gate
        if open_positions is not None:
            result = self._validate_max_trades(open_positions)
            if not result.valid:
                return result

        return ValidationResult(True)

    def _validate_spread(self, spread: float) -> ValidationResult:
        """Reject if spread exceeds configured max."""
        if spread > self._max_spread:
            return ValidationResult(
                False,
                f"spread ({spread:.1f} pts) exceeds max ({self._max_spread})",
            )
        return ValidationResult(True)

    def _validate_max_trades(self, open_count: int) -> ValidationResult:
        """Reject if max open trades limit reached."""
        if open_count >= self._max_open_trades:
            return ValidationResult(
                False,
                f"max open trades reached ({open_count}/{self._max_open_trades})",
            )
        return ValidationResult(True)

    def _validate_sl_coherence(self, signal: ParsedSignal) -> ValidationResult:
        """BUY: SL must be below entry. SELL: SL must be above entry."""
        if signal.sl is None or signal.entry is None:
            return ValidationResult(True)

        if signal.side == Side.BUY and signal.sl >= signal.entry:
            return ValidationResult(
                False,
                f"BUY signal SL ({signal.sl}) must be below "
                f"entry ({signal.entry})",
            )

        if signal.side == Side.SELL and signal.sl <= signal.entry:
            return ValidationResult(
                False,
                f"SELL signal SL ({signal.sl}) must be above "
                f"entry ({signal.entry})",
            )

        return ValidationResult(True)

    def _validate_tp_coherence(self, signal: ParsedSignal) -> ValidationResult:
        """BUY: TP must be above entry. SELL: TP must be below entry."""
        if not signal.tp or signal.entry is None:
            return ValidationResult(True)

        for i, tp in enumerate(signal.tp):
            if signal.side == Side.BUY and tp <= signal.entry:
                return ValidationResult(
                    False,
                    f"BUY signal TP{i + 1} ({tp}) must be above "
                    f"entry ({signal.entry})",
                )
            if signal.side == Side.SELL and tp >= signal.entry:
                return ValidationResult(
                    False,
                    f"SELL signal TP{i + 1} ({tp}) must be below "
                    f"entry ({signal.entry})",
                )

        return ValidationResult(True)

    def _validate_entry_distance(
        self,
        signal: ParsedSignal,
        current_price: float,
    ) -> ValidationResult:
        """Reject if entry is too far from current market price."""
        if signal.entry is None:
            return ValidationResult(True)

        distance = abs(signal.entry - current_price)
        if distance > self._max_entry_distance:
            return ValidationResult(
                False,
                f"entry distance ({distance:.1f} points) exceeds "
                f"max ({self._max_entry_distance})",
            )

        return ValidationResult(True)

    def _validate_signal_age(self, signal: ParsedSignal) -> ValidationResult:
        """Reject signals older than configured TTL."""
        now = datetime.now(timezone.utc)
        age_seconds = (now - signal.received_at).total_seconds()

        if age_seconds > self._signal_age_ttl:
            return ValidationResult(
                False,
                f"signal age ({age_seconds:.0f}s) exceeds "
                f"TTL ({self._signal_age_ttl}s)",
            )

        return ValidationResult(True)
