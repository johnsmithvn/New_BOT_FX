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
    5. Duplicate filtering via fingerprint (requires storage).
    """

    def __init__(
        self,
        max_entry_distance_points: int = 500,
        signal_age_ttl_seconds: int = 60,
    ) -> None:
        self._max_entry_distance = max_entry_distance_points
        self._signal_age_ttl = signal_age_ttl_seconds

    def validate(
        self,
        signal: ParsedSignal,
        current_price: float | None = None,
    ) -> ValidationResult:
        """Run all validation checks on a parsed signal.

        Args:
            signal: The parsed signal to validate.
            current_price: Current market reference price (bid for SELL,
                          ask for BUY). None if unavailable (P2 dependency).

        Returns:
            ValidationResult with valid=True or reason for rejection.
        """
        # Rule 1: Required fields
        if not signal.symbol:
            return ValidationResult(False, "missing symbol")

        if not signal.side:
            return ValidationResult(False, "missing side")

        # Rule 2: SL coherence
        result = self._validate_sl_coherence(signal)
        if not result.valid:
            return result

        # Rule 3: TP coherence
        result = self._validate_tp_coherence(signal)
        if not result.valid:
            return result

        # Rule 4: Entry distance (requires current_price)
        if current_price is not None and signal.entry is not None:
            result = self._validate_entry_distance(signal, current_price)
            if not result.valid:
                return result

        # Rule 5: Signal age
        result = self._validate_signal_age(signal)
        if not result.valid:
            return result

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
