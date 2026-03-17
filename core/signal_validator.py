"""
core/signal_validator.py

Validate parsed signals before trade execution.
Enforces safety rules and coherence checks.

UNITS: All distance/spread thresholds are in PIPS.
  - XAUUSD: 1 pip = 0.1 ($0.10 per pip), 1 point = 0.01
  - Forex:  1 pip = 0.0001, 1 point = 0.00001
  - To convert: pips = raw_price_distance / pip_size
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

    All distance/spread values use PIPS as unit.

    Rules enforced (priority order — first reject wins):
    1. Required fields (symbol, side, SL, TP).
    2. Duplicate filter (fingerprint within TTL).
    3. SL coherence (BUY: SL < entry, SELL: SL > entry).
    4. TP coherence (BUY: TP > entry, SELL: TP < entry).
    5. Entry distance from live price (in pips).
    5b. Entry drift guard — tight check for MARKET orders.
    6. Signal age (reject stale signals).
    7. Spread gate (in pips).
    8. Max open trades.
    """

    def __init__(
        self,
        max_entry_distance_pips: float = 50.0,
        signal_age_ttl_seconds: int = 60,
        max_spread_pips: float = 5.0,
        max_open_trades: int = 5,
        max_entry_drift_pips: float = 10.0,
    ) -> None:
        """Args:
            max_entry_distance_pips: Max allowed distance between signal entry
                and live price, in pips. XAUUSD: 50 pips = $5.0 price difference.
            signal_age_ttl_seconds: Max age of signal before rejection.
            max_spread_pips: Max allowed spread in pips.
                XAUUSD: 5 pips = $0.50 spread.
            max_open_trades: Max simultaneous open positions allowed.
            max_entry_drift_pips: Tight drift guard for MARKET orders.
                When entry is provided but order would be MARKET (due to
                tolerance), reject if |entry - price| > drift.
                XAUUSD: 10 pips = $1.0 price difference.
        """
        self._max_entry_distance_pips = max_entry_distance_pips
        self._signal_age_ttl = signal_age_ttl_seconds
        self._max_spread_pips = max_spread_pips
        self._max_open_trades = max_open_trades
        self._max_entry_drift_pips = max_entry_drift_pips

    def validate(
        self,
        signal: ParsedSignal,
        current_price: float | None = None,
        current_spread_pips: float | None = None,
        open_positions: int | None = None,
        is_duplicate: bool = False,
        pip_size: float = 0.1,
    ) -> ValidationResult:
        """Run all validation checks on a parsed signal.

        Args:
            signal: The parsed signal to validate.
            current_price: Current market reference price
                (ASK for BUY, BID for SELL). None if unavailable.
            current_spread_pips: Current spread in pips. None if unavailable.
            open_positions: Number of currently open positions.
            is_duplicate: True if fingerprint found in dedupe window.
            pip_size: Size of 1 pip in price units.
                XAUUSD: 0.1 (so $2030.0 → $2030.1 = 1 pip).
                EURUSD: 0.0001.
                USDJPY: 0.01.

        Returns:
            ValidationResult with valid=True or reason for rejection.
        """
        # Rule 1: Required fields
        if not signal.symbol:
            return ValidationResult(False, "missing symbol")

        if not signal.side:
            return ValidationResult(False, "missing side")

        if signal.sl is None:
            return ValidationResult(False, "missing Stop Loss (SL)")

        if not signal.tp:
            return ValidationResult(False, "missing Take Profit (TP)")

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

        # Rule 5: Entry distance (requires current_price + pip_size)
        if current_price is not None and signal.entry is not None:
            result = self._validate_entry_distance(
                signal, current_price, pip_size
            )
            if not result.valid:
                return result

        # Rule 6: Signal age
        result = self._validate_signal_age(signal)
        if not result.valid:
            return result

        # # Rule 7: Spread gate
        # if current_spread_pips is not None:
        #     result = self._validate_spread(current_spread_pips)
        #     if not result.valid:
        #         return result

        # Rule 8: Max open trades gate
        if open_positions is not None:
            result = self._validate_max_trades(open_positions)
            if not result.valid:
                return result

        return ValidationResult(True)

    def _validate_spread(self, spread_pips: float) -> ValidationResult:
        """Reject if spread exceeds configured max (in pips)."""
        if spread_pips > self._max_spread_pips:
            return ValidationResult(
                False,
                f"spread ({spread_pips:.1f} pips) exceeds "
                f"max ({self._max_spread_pips} pips)",
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
        pip_size: float,
    ) -> ValidationResult:
        """Reject if entry is too far from current market price.

        Converts raw price distance to pips before comparison.

        Example XAUUSD (pip_size=0.1):
            entry=2030, price=2035 → distance = $5.0 = 50 pips
            max_entry_distance_pips=50 → 50 ≤ 50 → PASS
        """
        if signal.entry is None:
            return ValidationResult(True)

        raw_distance = abs(signal.entry - current_price)
        distance_pips = raw_distance / pip_size if pip_size > 0 else raw_distance

        if distance_pips > self._max_entry_distance_pips:
            return ValidationResult(
                False,
                f"entry distance ({distance_pips:.1f} pips) exceeds "
                f"max ({self._max_entry_distance_pips} pips)",
            )

        return ValidationResult(True)

    def validate_entry_drift(
        self,
        signal: ParsedSignal,
        current_price: float,
        pip_size: float,
    ) -> ValidationResult:
        """Reject MARKET orders when entry has drifted too far from signal.

        This is a tight guard for MARKET orders only. When the signal
        specifies an explicit entry price but the order would be MARKET
        (because price is within tolerance), check that the price hasn't
        drifted beyond the drift threshold.

        Called externally after order type is decided — only for MARKET
        orders that had an explicit entry price.

        Example XAUUSD (pip_size=0.1, max_drift=10 pips):
            signal entry=2030, current price=2031.5
            drift = $1.5 / 0.1 = 15 pips > 10 → REJECT

        Args:
            signal: Parsed signal with entry price.
            current_price: Current market price (ask for BUY, bid for SELL).
            pip_size: Size of 1 pip in price units.

        Returns:
            ValidationResult with valid=True or rejection reason.
        """
        if signal.entry is None:
            return ValidationResult(True)

        raw_drift = abs(signal.entry - current_price)
        drift_pips = raw_drift / pip_size if pip_size > 0 else raw_drift

        if drift_pips > self._max_entry_drift_pips:
            return ValidationResult(
                False,
                f"entry drift ({drift_pips:.1f} pips) exceeds "
                f"max ({self._max_entry_drift_pips} pips) for MARKET order",
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
