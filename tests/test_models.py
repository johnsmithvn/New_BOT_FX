"""
tests/test_models.py

Unit tests for core/models.py — data contracts and enums.
"""

from core.models import (
    Side,
    OrderKind,
    SignalStatus,
    SignalLifecycle,
    GroupStatus,
    ParsedSignal,
    ParseFailure,
    TradeDecision,
    ExecutionResult,
    EntryPlan,
    SignalState,
    OrderGroup,
    order_fingerprint,
)


class TestEnums:
    """Verify enum values and string representations."""

    def test_side_values(self):
        assert Side.BUY == "BUY"
        assert Side.SELL == "SELL"

    def test_order_kind_values(self):
        kinds = [OrderKind.MARKET, OrderKind.BUY_LIMIT, OrderKind.BUY_STOP,
                 OrderKind.SELL_LIMIT, OrderKind.SELL_STOP]
        assert len(kinds) == 5

    def test_signal_status_values(self):
        assert SignalStatus.RECEIVED == "received"
        assert SignalStatus.EXECUTED == "executed"
        assert SignalStatus.FAILED == "failed"

    def test_signal_lifecycle_states(self):
        assert SignalLifecycle.PENDING == "pending"
        assert SignalLifecycle.PARTIAL == "partial"
        assert SignalLifecycle.COMPLETED == "completed"
        assert SignalLifecycle.EXPIRED == "expired"

    def test_group_status(self):
        assert GroupStatus.ACTIVE == "active"
        assert GroupStatus.COMPLETED == "completed"
        assert GroupStatus.EXPIRED == "expired"


class TestOrderFingerprint:
    """Tests for order_fingerprint() helper."""

    def test_level_zero(self):
        assert order_fingerprint("abc123", 0) == "abc123:L0"

    def test_level_positive(self):
        assert order_fingerprint("abc123", 3) == "abc123:L3"

    def test_format(self):
        fp = order_fingerprint("fp_base", 1)
        assert ":L" in fp
        assert fp.endswith("1")


class TestParsedSignalDefaults:
    """Verify ParsedSignal defaults."""

    def test_default_tp_empty(self):
        sig = ParsedSignal(symbol="XAUUSD", side=Side.BUY, entry=2030.0, sl=2020.0)
        assert sig.tp == []

    def test_default_entry_none(self):
        sig = ParsedSignal(symbol="XAUUSD", side=Side.BUY, entry=None, sl=2020.0)
        assert sig.entry is None

    def test_default_fingerprint_empty(self):
        sig = ParsedSignal(symbol="XAUUSD", side=Side.BUY, entry=2030.0, sl=2020.0)
        assert sig.fingerprint == ""

    def test_default_parse_confidence(self):
        sig = ParsedSignal(symbol="XAUUSD", side=Side.BUY, entry=2030.0, sl=2020.0)
        assert sig.parse_confidence == 1.0

    def test_default_parse_source(self):
        sig = ParsedSignal(symbol="XAUUSD", side=Side.BUY, entry=2030.0, sl=2020.0)
        assert sig.parse_source == "standard"


class TestEntryPlanDefaults:
    """Verify EntryPlan defaults."""

    def test_default_status_pending(self):
        plan = EntryPlan(level=2030.0, order_kind=OrderKind.MARKET, level_id=0)
        assert plan.status == "pending"

    def test_default_label_empty(self):
        plan = EntryPlan(level=2030.0, order_kind=OrderKind.MARKET, level_id=0)
        assert plan.label == ""


class TestOrderGroupDefaults:
    """Verify OrderGroup defaults."""

    def test_default_status_active(self):
        group = OrderGroup(
            fingerprint="fp1", symbol="XAUUSD", side=Side.BUY,
            channel_id="ch1", source_message_id="1",
            zone_low=None, zone_high=None, signal_sl=2020.0,
        )
        assert group.status == GroupStatus.ACTIVE

    def test_default_tickets_empty(self):
        group = OrderGroup(
            fingerprint="fp1", symbol="XAUUSD", side=Side.BUY,
            channel_id="ch1", source_message_id="1",
            zone_low=None, zone_high=None, signal_sl=2020.0,
        )
        assert group.tickets == []
