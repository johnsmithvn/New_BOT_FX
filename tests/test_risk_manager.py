"""
tests/test_risk_manager.py

Unit tests for core/risk_manager.py — position sizing.
"""

from core.risk_manager import RiskManager


class TestFixedLotMode:
    """FIXED_LOT mode — always returns configured lot size."""

    def test_returns_fixed_lot(self):
        rm = RiskManager(mode="FIXED_LOT", fixed_lot_size=0.05)
        assert rm.calculate_volume() == 0.05

    def test_ignores_balance_params(self):
        rm = RiskManager(mode="FIXED_LOT", fixed_lot_size=0.10)
        assert rm.calculate_volume(balance=100000, entry=2030, sl=2020) == 0.10


class TestRiskPercentMode:
    """RISK_PERCENT mode — risk-based volume calculation."""

    def test_normal_calculation(self):
        rm = RiskManager(
            mode="RISK_PERCENT",
            risk_percent=1.0,
            lot_min=0.01,
            lot_max=100.0,
            lot_step=0.01,
        )
        # balance=10000, risk=1% → risk_amount=100
        # entry=2030, sl=2020 → sl_distance=10
        # pip_value=10 → volume = 100 / (10 * 10) = 1.0
        vol = rm.calculate_volume(balance=10000, entry=2030, sl=2020, pip_value=10)
        assert vol == 1.0

    def test_missing_balance_fallback(self):
        rm = RiskManager(mode="RISK_PERCENT", fixed_lot_size=0.05)
        vol = rm.calculate_volume(balance=None, entry=2030, sl=2020, pip_value=10)
        assert vol == 0.05

    def test_missing_sl_fallback(self):
        rm = RiskManager(mode="RISK_PERCENT", fixed_lot_size=0.05)
        vol = rm.calculate_volume(balance=10000, entry=2030, sl=None, pip_value=10)
        assert vol == 0.05

    def test_sl_distance_zero_fallback(self):
        rm = RiskManager(mode="RISK_PERCENT", fixed_lot_size=0.05)
        # entry == sl → sl_distance = 0
        vol = rm.calculate_volume(balance=10000, entry=2030, sl=2030, pip_value=10)
        assert vol == 0.05

    def test_zero_balance_fallback(self):
        rm = RiskManager(mode="RISK_PERCENT", fixed_lot_size=0.05)
        vol = rm.calculate_volume(balance=0, entry=2030, sl=2020, pip_value=10)
        assert vol == 0.05

    def test_negative_pip_value_fallback(self):
        rm = RiskManager(mode="RISK_PERCENT", fixed_lot_size=0.05)
        vol = rm.calculate_volume(balance=10000, entry=2030, sl=2020, pip_value=-1)
        assert vol == 0.05


class TestClampVolume:
    """Volume clamping and rounding."""

    def test_clamp_to_lot_min(self):
        rm = RiskManager(mode="FIXED_LOT", fixed_lot_size=0.001, lot_min=0.01)
        assert rm.calculate_volume() == 0.01

    def test_clamp_to_lot_max(self):
        rm = RiskManager(mode="FIXED_LOT", fixed_lot_size=200.0, lot_max=100.0)
        assert rm.calculate_volume() == 100.0

    def test_round_to_lot_step(self):
        rm = RiskManager(
            mode="RISK_PERCENT",
            risk_percent=1.0,
            lot_step=0.01,
            lot_min=0.01,
        )
        # Expect result to be rounded to nearest 0.01
        vol = rm.calculate_volume(balance=10000, entry=2030, sl=2020, pip_value=10)
        # 100 / (10 * 10) = 1.0 → already clean
        assert vol == 1.0
        # Verify precision: no floating-point noise
        assert vol == round(vol, 2)

    def test_lot_step_005(self):
        rm = RiskManager(
            mode="FIXED_LOT",
            fixed_lot_size=0.037,
            lot_step=0.05,
            lot_min=0.05,
        )
        # 0.037 → floor to 0.05 step → 0.0 → clamped to lot_min=0.05
        assert rm.calculate_volume() == 0.05
