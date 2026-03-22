"""
tests/test_entry_strategy.py

Unit tests for core/entry_strategy.py — entry plan generation.
"""

from core.entry_strategy import EntryStrategy
from core.models import ParsedSignal, Side, OrderKind, EntryPlan


def _make_signal(**overrides) -> ParsedSignal:
    defaults = dict(
        symbol="XAUUSD",
        side=Side.BUY,
        entry=2030.0,
        sl=2020.0,
        tp=[2050.0],
        entry_range=None,
    )
    defaults.update(overrides)
    return ParsedSignal(**defaults)


class TestSingleMode:
    """Single mode: 1 signal → 1 order."""

    def setup_method(self):
        self.es = EntryStrategy()

    def test_single_plan(self):
        sig = _make_signal()
        plans = self.es.plan_entries(sig, {"mode": "single"}, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 1
        assert plans[0].level_id == 0
        assert plans[0].label == "initial"

    def test_single_market_entry(self):
        sig = _make_signal(entry=None)
        plans = self.es.plan_entries(sig, {"mode": "single"}, bid=2029, ask=2031, point=0.01)
        assert plans[0].order_kind == OrderKind.MARKET

    def test_default_mode_is_single(self):
        sig = _make_signal()
        plans = self.es.plan_entries(sig, {}, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 1


class TestRangeMode:
    """Range mode: N orders spread across entry_range."""

    def setup_method(self):
        self.es = EntryStrategy()

    def test_buy_range_3_entries(self):
        sig = _make_signal(entry_range=[2020.0, 2030.0])
        config = {"mode": "range", "max_entries": 3}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 3
        # BUY range: descending from high to low
        assert plans[0].level >= plans[-1].level

    def test_sell_range_3_entries(self):
        sig = _make_signal(side=Side.SELL, entry_range=[2020.0, 2030.0])
        config = {"mode": "range", "max_entries": 3}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 3
        # SELL range: ascending from low to high
        assert plans[0].level <= plans[-1].level

    def test_no_entry_range_fallback_single(self):
        sig = _make_signal(entry_range=None)
        config = {"mode": "range", "max_entries": 3}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 1  # fallback to single

    def test_max_entries_1_fallback_single(self):
        sig = _make_signal(entry_range=[2020.0, 2030.0])
        config = {"mode": "range", "max_entries": 1}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 1

    def test_max_hard_cap_10(self):
        sig = _make_signal(entry_range=[2020.0, 2030.0])
        config = {"mode": "range", "max_entries": 20}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) <= 10


class TestScaleInMode:
    """Scale-in mode: stepped re-entries."""

    def setup_method(self):
        self.es = EntryStrategy()

    def test_buy_scale_in(self):
        sig = _make_signal(entry=2030.0)
        config = {"mode": "scale_in", "max_entries": 3, "reentry_step_pips": 20}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 3
        # BUY: re-entries at lower prices
        assert plans[1].level < plans[0].level
        assert plans[2].level < plans[1].level

    def test_sell_scale_in(self):
        sig = _make_signal(side=Side.SELL, entry=2030.0)
        config = {"mode": "scale_in", "max_entries": 3, "reentry_step_pips": 20}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 3
        # SELL: re-entries at higher prices
        assert plans[1].level > plans[0].level

    def test_zero_step_fallback_single(self):
        sig = _make_signal()
        config = {"mode": "scale_in", "max_entries": 3, "reentry_step_pips": 0}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 1

    def test_max_entries_1_fallback_single(self):
        sig = _make_signal()
        config = {"mode": "scale_in", "max_entries": 1, "reentry_step_pips": 20}
        plans = self.es.plan_entries(sig, config, bid=2029, ask=2031, point=0.01)
        assert len(plans) == 1


class TestSplitVolume:
    """Volume allocation across plans."""

    def setup_method(self):
        self.es = EntryStrategy()

    def test_empty_plans(self):
        assert self.es.split_volume(0.10, [], sl=2020.0) == []

    def test_single_plan_full_volume(self):
        plans = [EntryPlan(level=2030, order_kind=OrderKind.MARKET, level_id=0)]
        vols = self.es.split_volume(0.10, plans, sl=2020.0)
        assert vols == [0.10]

    def test_equal_split(self):
        plans = [
            EntryPlan(level=2030, order_kind=OrderKind.MARKET, level_id=i)
            for i in range(3)
        ]
        vols = self.es.split_volume(0.09, plans, sl=2020.0, split_mode="equal")
        assert len(vols) == 3
        assert all(v == 0.03 for v in vols)

    def test_pyramid_split_descending(self):
        plans = [
            EntryPlan(level=2030, order_kind=OrderKind.MARKET, level_id=i)
            for i in range(3)
        ]
        vols = self.es.split_volume(0.10, plans, sl=2020.0, split_mode="pyramid")
        assert vols[0] >= vols[1] >= vols[2]

    def test_risk_based_split(self):
        plans = [
            EntryPlan(level=2030, order_kind=OrderKind.MARKET, level_id=0),
            EntryPlan(level=2025, order_kind=OrderKind.BUY_LIMIT, level_id=1),
        ]
        vols = self.es.split_volume(0.10, plans, sl=2020.0, split_mode="risk_based")
        # 2030 is farther from SL(2020) = 10 | 2025 = 5
        # farther → larger volume
        assert vols[0] > vols[1]

    def test_lot_min_enforced(self):
        plans = [
            EntryPlan(level=2030, order_kind=OrderKind.MARKET, level_id=i)
            for i in range(5)
        ]
        vols = self.es.split_volume(0.01, plans, sl=2020.0, split_mode="equal", lot_min=0.01)
        # Each would be 0.002, but lot_min=0.01
        assert all(v >= 0.01 for v in vols)


class TestDecideOrderKind:
    """Order kind decision for individual entry levels."""

    def setup_method(self):
        self.es = EntryStrategy()

    def test_none_entry_returns_market(self):
        kind = self.es._decide_order_kind(None, Side.BUY, 2029, 2031, 0.01, 5.0)
        assert kind == OrderKind.MARKET

    def test_buy_within_tolerance_market(self):
        kind = self.es._decide_order_kind(2031.02, Side.BUY, 2029, 2031, 0.01, 5.0)
        assert kind == OrderKind.MARKET

    def test_buy_below_ask_limit(self):
        kind = self.es._decide_order_kind(2020, Side.BUY, 2029, 2031, 0.01, 5.0)
        assert kind == OrderKind.BUY_LIMIT

    def test_buy_above_ask_stop(self):
        kind = self.es._decide_order_kind(2040, Side.BUY, 2029, 2031, 0.01, 5.0)
        assert kind == OrderKind.BUY_STOP

    def test_sell_above_bid_limit(self):
        kind = self.es._decide_order_kind(2040, Side.SELL, 2029, 2031, 0.01, 5.0)
        assert kind == OrderKind.SELL_LIMIT

    def test_sell_below_bid_stop(self):
        kind = self.es._decide_order_kind(2020, Side.SELL, 2029, 2031, 0.01, 5.0)
        assert kind == OrderKind.SELL_STOP
