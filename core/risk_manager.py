"""
core/risk_manager.py

Determine trade volume (lot size).
Supports fixed lot and risk-based sizing.
Ensures volume respects broker min/max constraints.
"""

from __future__ import annotations

import math


class RiskManager:
    """Calculate position size for trade execution.

    Modes:
    - FIXED_LOT: Use a fixed lot size from config.
    - RISK_PERCENT: Calculate lot size based on account balance,
                    entry-SL distance, and risk percentage.
    """

    def __init__(
        self,
        mode: str = "FIXED_LOT",
        fixed_lot_size: float = 0.01,
        risk_percent: float = 1.0,
        lot_min: float = 0.01,
        lot_max: float = 100.0,
        lot_step: float = 0.01,
    ) -> None:
        self._mode = mode.upper()
        self._fixed_lot = fixed_lot_size
        self._risk_percent = risk_percent
        self._lot_min = lot_min
        self._lot_max = lot_max
        self._lot_step = lot_step

    def calculate_volume(
        self,
        balance: float | None = None,
        entry: float | None = None,
        sl: float | None = None,
        pip_value: float | None = None,
    ) -> float:
        """Calculate trade volume.

        Args:
            balance: Account balance (required for RISK_PERCENT mode).
            entry: Entry price (required for RISK_PERCENT mode).
            sl: Stop loss price (required for RISK_PERCENT mode).
            pip_value: Value per pip per lot (required for RISK_PERCENT mode).

        Returns:
            Clamped and rounded lot size.
        """
        if self._mode == "RISK_PERCENT":
            volume = self._risk_based_volume(balance, entry, sl, pip_value)
        else:
            volume = self._fixed_lot

        return self._clamp_volume(volume)

    def _risk_based_volume(
        self,
        balance: float | None,
        entry: float | None,
        sl: float | None,
        pip_value: float | None,
    ) -> float:
        """Calculate lot size from risk percentage.

        Formula:
            risk_amount = balance * (risk_percent / 100)
            sl_distance = |entry - sl|
            volume = risk_amount / (sl_distance * pip_value)
        """
        if not all([balance, entry, sl, pip_value]):
            # Fallback to fixed lot when required inputs missing
            return self._fixed_lot

        if balance <= 0 or pip_value <= 0:
            return self._fixed_lot

        sl_distance = abs(entry - sl)
        if sl_distance == 0:
            return self._fixed_lot

        risk_amount = balance * (self._risk_percent / 100.0)
        volume = risk_amount / (sl_distance * pip_value)

        return volume

    def _clamp_volume(self, volume: float) -> float:
        """Clamp volume to broker constraints and round to lot step."""
        # Round down to nearest lot step
        volume = math.floor(volume / self._lot_step) * self._lot_step
        # Clamp to min/max
        volume = max(self._lot_min, min(volume, self._lot_max))
        # Round to avoid floating point artifacts
        decimals = len(str(self._lot_step).rstrip("0").split(".")[-1])
        volume = round(volume, decimals)
        return volume
