"""
tests/test_signal_validator.py

Unit tests for core/signal_validator.py — signal safety validation.
"""

from datetime import datetime, timezone, timedelta

from core.signal_validator import SignalValidator
from core.models import ParsedSignal, Side


def _make_signal(**overrides) -> ParsedSignal:
    """Helper to create a valid ParsedSignal with sensible defaults."""
    defaults = dict(
        symbol="XAUUSD",
        side=Side.BUY,
        entry=2030.0,
        sl=2020.0,
        tp=[2050.0],
        fingerprint="abc123",
        received_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return ParsedSignal(**defaults)


class TestValidateRequiredFields:
    """Rule 1: Required fields."""

    def setup_method(self):
        self.v = SignalValidator()

    def test_missing_symbol(self):
        sig = _make_signal(symbol="")
        r = self.v.validate(sig)
        assert not r.valid
        assert "symbol" in r.reason

    def test_missing_side(self):
        sig = _make_signal(side=None)
        r = self.v.validate(sig)
        assert not r.valid
        assert "side" in r.reason

    def test_missing_sl(self):
        sig = _make_signal(sl=None)
        r = self.v.validate(sig)
        assert not r.valid
        assert "Stop Loss" in r.reason


class TestValidateDuplicate:
    """Rule 2: Duplicate filter."""

    def setup_method(self):
        self.v = SignalValidator()

    def test_duplicate_rejected(self):
        sig = _make_signal()
        r = self.v.validate(sig, is_duplicate=True)
        assert not r.valid
        assert "duplicate" in r.reason

    def test_non_duplicate_passes(self):
        sig = _make_signal()
        r = self.v.validate(sig, is_duplicate=False)
        assert r.valid


class TestValidateSlCoherence:
    """Rule 3: SL coherence (BUY: SL<entry, SELL: SL>entry)."""

    def setup_method(self):
        self.v = SignalValidator()

    def test_buy_sl_above_entry_rejected(self):
        sig = _make_signal(side=Side.BUY, entry=2030.0, sl=2040.0)
        r = self.v.validate(sig)
        assert not r.valid
        assert "SL" in r.reason

    def test_buy_sl_equal_entry_rejected(self):
        sig = _make_signal(side=Side.BUY, entry=2030.0, sl=2030.0)
        r = self.v.validate(sig)
        assert not r.valid

    def test_sell_sl_below_entry_rejected(self):
        sig = _make_signal(side=Side.SELL, entry=2030.0, sl=2020.0, tp=[2010.0])
        r = self.v.validate(sig)
        assert not r.valid

    def test_buy_sl_below_entry_passes(self):
        sig = _make_signal(side=Side.BUY, entry=2030.0, sl=2020.0)
        r = self.v.validate(sig)
        assert r.valid

    def test_sell_sl_above_entry_passes(self):
        sig = _make_signal(side=Side.SELL, entry=2030.0, sl=2040.0, tp=[2010.0])
        r = self.v.validate(sig)
        assert r.valid

    def test_sl_none_skips_check(self):
        """SL=None → already caught by required fields, but coherence skips."""
        sig = _make_signal(entry=2030.0, sl=None)
        # Will fail on required fields before reaching coherence
        r = self.v.validate(sig)
        assert not r.valid  # fails for missing SL


class TestValidateTpCoherence:
    """Rule 4: TP coherence (BUY: TP>entry, SELL: TP<entry)."""

    def setup_method(self):
        self.v = SignalValidator()

    def test_buy_tp_below_entry_rejected(self):
        sig = _make_signal(side=Side.BUY, entry=2030.0, tp=[2020.0])
        r = self.v.validate(sig)
        assert not r.valid
        assert "TP" in r.reason

    def test_sell_tp_above_entry_rejected(self):
        sig = _make_signal(side=Side.SELL, entry=2030.0, sl=2040.0, tp=[2050.0])
        r = self.v.validate(sig)
        assert not r.valid

    def test_buy_tp_above_entry_passes(self):
        sig = _make_signal(side=Side.BUY, entry=2030.0, tp=[2050.0])
        r = self.v.validate(sig)
        assert r.valid

    def test_no_tp_skips_check(self):
        sig = _make_signal(tp=[])
        r = self.v.validate(sig)
        assert r.valid


class TestValidateEntryDistance:
    """Rule 5: Entry distance from live price (pips)."""

    def setup_method(self):
        self.v = SignalValidator(max_entry_distance_pips=50.0)

    def test_distance_exceeds_max_rejected(self):
        sig = _make_signal(entry=2030.0)
        # |2030-2036|=6, 6/0.1=60 pips > 50 → should fail
        r = self.v.validate(sig, current_price=2036.0, pip_size=0.1)
        assert not r.valid
        assert "entry distance" in r.reason

    def test_distance_within_range_passes(self):
        sig = _make_signal(entry=2030.0)
        # 30 pips away: |2030 - 2033| = 3, 3/0.1 = 30 pips ≤ 50
        r = self.v.validate(sig, current_price=2033.0, pip_size=0.1)
        assert r.valid

    def test_no_price_skips_check(self):
        sig = _make_signal(entry=2030.0)
        r = self.v.validate(sig, current_price=None)
        assert r.valid

    def test_no_entry_skips_check(self):
        sig = _make_signal(entry=None)
        r = self.v.validate(sig, current_price=2030.0)
        assert r.valid


class TestValidateSignalAge:
    """Rule 6: Signal age (reject stale signals)."""

    def setup_method(self):
        self.v = SignalValidator(signal_age_ttl_seconds=60)

    def test_stale_signal_rejected(self):
        old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        sig = _make_signal(received_at=old_time)
        r = self.v.validate(sig)
        assert not r.valid
        assert "age" in r.reason

    def test_fresh_signal_passes(self):
        sig = _make_signal(received_at=datetime.now(timezone.utc))
        r = self.v.validate(sig)
        assert r.valid


class TestValidateMaxTrades:
    """Rule 8: Max open trades gate."""

    def setup_method(self):
        self.v = SignalValidator(max_open_trades=5)

    def test_max_trades_reached_rejected(self):
        sig = _make_signal()
        r = self.v.validate(sig, open_positions=5)
        assert not r.valid
        assert "max open" in r.reason

    def test_under_limit_passes(self):
        sig = _make_signal()
        r = self.v.validate(sig, open_positions=3)
        assert r.valid

    def test_no_position_count_skips_check(self):
        sig = _make_signal()
        r = self.v.validate(sig, open_positions=None)
        assert r.valid


class TestValidateEntryDrift:
    """validate_entry_drift() — tight guard for MARKET orders."""

    def setup_method(self):
        self.v = SignalValidator(max_entry_drift_pips=10.0)

    def test_drift_within_threshold_passes(self):
        sig = _make_signal(entry=2030.0)
        r = self.v.validate_entry_drift(sig, current_price=2030.5, pip_size=0.1)
        assert r.valid  # 0.5/0.1 = 5 pips ≤ 10

    def test_drift_exceeds_threshold_rejected(self):
        sig = _make_signal(entry=2030.0)
        r = self.v.validate_entry_drift(sig, current_price=2031.5, pip_size=0.1)
        assert not r.valid  # 1.5/0.1 = 15 pips > 10

    def test_no_entry_skips(self):
        sig = _make_signal(entry=None)
        r = self.v.validate_entry_drift(sig, current_price=2030.0, pip_size=0.1)
        assert r.valid


class TestFullValidation:
    """End-to-end validation — all rules pass."""

    def test_valid_signal_passes_all_rules(self):
        v = SignalValidator(
            max_entry_distance_pips=50.0,
            signal_age_ttl_seconds=60,
            max_open_trades=10,
        )
        sig = _make_signal(
            received_at=datetime.now(timezone.utc),
        )
        r = v.validate(
            sig,
            current_price=2031.0,
            pip_size=0.1,
            open_positions=3,
            is_duplicate=False,
        )
        assert r.valid
