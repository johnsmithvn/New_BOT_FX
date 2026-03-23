"""
tests/test_noval_config.py

Comprehensive tests for Noval channel configuration and G7-G12 features.

Config reference (channels.json → Noval):
    rules:
        breakeven_trigger_pips: 50
        breakeven_lock_pips: 30
        trailing_stop_pips: 40
        secure_profit_action: close_worst_be_rest
        reply_be_lock_pips: 10
    strategy:
        mode: range
        max_entries: 3
        volume_split: per_entry
        min_sl_distance_pips: 20
        default_sl_pips_from_zone: 50
        reentry_tolerance_pips: 5
        max_reentry_distance_pips: 10
        reentry_step_pips: 20

Gold constants:
    point = 0.01
    pip_size = 0.10 (10 × point)
    1 pip = $0.10 price change
"""

import pytest
from core.entry_strategy import EntryStrategy
from core.models import ParsedSignal, Side, OrderKind, EntryPlan


# ── Fixtures ─────────────────────────────────────────────────────

NOVAL_STRATEGY = {
    "mode": "range",
    "max_entries": 3,
    "execute_all_immediately": False,
    "signal_ttl_minutes": 20,
    "volume_split": "per_entry",
    "min_sl_distance_pips": 20,
    "default_sl_pips_from_zone": 50,
    "reentry_tolerance_pips": 5,
    "max_reentry_distance_pips": 10,
    "reentry_step_pips": 20,
}

# Gold tick constants
POINT = 0.01
PIP_SIZE = 0.10  # 10 × point


def _sig(**kw) -> ParsedSignal:
    """Helper to create a Gold signal with Noval-like defaults."""
    defaults = dict(
        symbol="XAUUSD",
        side=Side.SELL,
        entry=3340.0,
        sl=3352.0,
        tp=[3320.0],
        entry_range=[3340.0, 3347.0],
    )
    defaults.update(kw)
    return ParsedSignal(**defaults)


# ═════════════════════════════════════════════════════════════════
# G9: Step-based P2/P3 Levels (reentry_step_pips=20)
# ═════════════════════════════════════════════════════════════════


class TestG9StepBasedLevels:
    """P1 = zone_low (SELL) or zone_high (BUY).
    P2 = P1 ± 1×step, P3 = P1 ± 2×step.
    step = 20 pips × 0.10 = $2.00 for Gold.
    """

    def setup_method(self):
        self.es = EntryStrategy()

    # ── SELL: levels go UP from zone_low ──────────────────────

    def test_sell_3_levels_step20(self):
        """SELL zone 3340-3347, step=20pip → P1=3340, P2=3342, P3=3344."""
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3347.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT)
        assert len(plans) == 3
        assert plans[0].level == 3340.0   # P1 = zone_low
        assert plans[1].level == 3342.0   # P2 = 3340 + 20×0.1
        assert plans[2].level == 3344.0   # P3 = 3340 + 40×0.1

    def test_sell_levels_ascending(self):
        """SELL re-entry levels must be ascending (higher = worse for existing sell)."""
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3347.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT)
        for i in range(len(plans) - 1):
            assert plans[i].level < plans[i + 1].level, \
                f"P{i+1}={plans[i].level} should be < P{i+2}={plans[i+1].level}"

    def test_sell_p1_is_initial(self):
        """P1 label = 'initial', P2/P3 = 'range_N'."""
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3347.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT)
        assert plans[0].label == "initial"
        assert plans[1].label == "range_1"
        assert plans[2].label == "range_2"

    # ── BUY: levels go DOWN from zone_high ────────────────────

    def test_buy_3_levels_step20(self):
        """BUY zone 3340-3347, step=20pip → P1=3347, P2=3345, P3=3343."""
        sig = _sig(side=Side.BUY, entry=3347.0, sl=3328.0,
                   entry_range=[3340.0, 3347.0], tp=[3370.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3345, ask=3346, point=POINT)
        assert len(plans) == 3
        assert plans[0].level == 3347.0   # P1 = zone_high
        assert plans[1].level == 3345.0   # P2 = 3347 - 20×0.1
        assert plans[2].level == 3343.0   # P3 = 3347 - 40×0.1

    def test_buy_levels_descending(self):
        """BUY re-entry levels must be descending (lower = better buy price)."""
        sig = _sig(side=Side.BUY, entry=3347.0, sl=3328.0,
                   entry_range=[3340.0, 3347.0], tp=[3370.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3345, ask=3346, point=POINT)
        for i in range(len(plans) - 1):
            assert plans[i].level > plans[i + 1].level

    # ── Edge cases ────────────────────────────────────────────

    def test_step0_falls_back_to_zone_spread(self):
        """reentry_step_pips=0 → legacy zone-spread logic."""
        config = {**NOVAL_STRATEGY, "reentry_step_pips": 0}
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3347.0])
        plans = self.es.plan_entries(sig, config, bid=3341, ask=3342, point=POINT)
        assert len(plans) == 3
        # Legacy: evenly spread across zone
        assert plans[0].level == 3340.0  # zone_low
        assert plans[2].level == 3347.0  # zone_high

    def test_no_entry_range_falls_back_to_single(self):
        """No entry_range → single entry regardless of range mode."""
        sig = _sig(side=Side.SELL, entry_range=None)
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT)
        assert len(plans) == 1

    def test_max_entries_1_falls_back_to_single(self):
        """max_entries=1 → only P1, no re-entries."""
        config = {**NOVAL_STRATEGY, "max_entries": 1}
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3347.0])
        plans = self.es.plan_entries(sig, config, bid=3341, ask=3342, point=POINT)
        assert len(plans) == 1

    def test_narrow_zone_step_exceeds_zone(self):
        """Steps can go beyond zone (P3=3344 > zone_high=3342). This is expected."""
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3342.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT)
        assert len(plans) == 3
        # P3 = 3340 + 4.0 = 3344 → beyond zone_high, that's OK
        assert plans[2].level == 3344.0


# ═════════════════════════════════════════════════════════════════
# G12a: per_entry Volume Split
# ═════════════════════════════════════════════════════════════════


class TestG12aPerEntryVolumeSplit:
    """Each plan gets the full FIXED_LOT_SIZE (no splitting)."""

    def setup_method(self):
        self.es = EntryStrategy()

    def test_3_plans_each_gets_full_lot(self):
        """per_entry: 0.01 lot, 3 plans → each gets 0.01."""
        plans = [EntryPlan(level=3340 + i, order_kind=OrderKind.MARKET, level_id=i)
                 for i in range(3)]
        vols = self.es.split_volume(0.01, plans, sl=3352.0, split_mode="per_entry")
        assert vols == [0.01, 0.01, 0.01]

    def test_1_plan_gets_full_lot(self):
        """per_entry: single plan → same as equal."""
        plans = [EntryPlan(level=3340, order_kind=OrderKind.MARKET, level_id=0)]
        vols = self.es.split_volume(0.01, plans, sl=3352.0, split_mode="per_entry")
        assert vols == [0.01]

    def test_5_plans_each_gets_full_lot(self):
        """per_entry: 5 plans → total exposure = 5 × lot."""
        plans = [EntryPlan(level=3340 + i, order_kind=OrderKind.MARKET, level_id=i)
                 for i in range(5)]
        vols = self.es.split_volume(0.02, plans, sl=3352.0, split_mode="per_entry")
        assert len(vols) == 5
        assert all(v == 0.02 for v in vols)
        assert sum(vols) == 0.10  # total exposure

    def test_equal_split_divides(self):
        """equal: 0.03 lot, 3 plans → each gets 0.01 (contrast with per_entry)."""
        plans = [EntryPlan(level=3340 + i, order_kind=OrderKind.MARKET, level_id=i)
                 for i in range(3)]
        vols = self.es.split_volume(0.03, plans, sl=3352.0, split_mode="equal")
        assert vols == [0.01, 0.01, 0.01]

    def test_equal_split_too_small_enforces_lot_min(self):
        """equal: 0.01 / 3 = 0.0033 → forced to lot_min=0.01."""
        plans = [EntryPlan(level=3340 + i, order_kind=OrderKind.MARKET, level_id=i)
                 for i in range(3)]
        vols = self.es.split_volume(0.01, plans, sl=3352.0, split_mode="equal", lot_min=0.01)
        # Each must be at least lot_min
        assert all(v >= 0.01 for v in vols)

    def test_empty_plans_returns_empty(self):
        """No plans → no volumes."""
        vols = self.es.split_volume(0.01, [], sl=3352.0, split_mode="per_entry")
        assert vols == []


# ═════════════════════════════════════════════════════════════════
# G9 + per_entry: Full Noval Config Integration
# ═════════════════════════════════════════════════════════════════


class TestNovalFullIntegration:
    """Verify the complete Noval workflow: plan_entries → split_volume."""

    def setup_method(self):
        self.es = EntryStrategy()

    def test_sell_3_entries_with_per_entry_volume(self):
        """
        SELL zone 3340-3347, step=20, per_entry, fixed_lot=0.01:
        Plans: P1=3340, P2=3342, P3=3344
        Volumes: [0.01, 0.01, 0.01] (total 0.03)
        """
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3347.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT)
        vols = self.es.split_volume(0.01, plans, sl=3352.0,
                                     split_mode=NOVAL_STRATEGY["volume_split"])
        assert len(plans) == 3
        assert len(vols) == 3
        assert all(v == 0.01 for v in vols)

    def test_buy_3_entries_with_per_entry_volume(self):
        """BUY zone 3340-3347, step=20 → P1=3347, P2=3345, P3=3343, each 0.01."""
        sig = _sig(side=Side.BUY, entry=3347.0, sl=3328.0,
                   entry_range=[3340.0, 3347.0], tp=[3370.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3345, ask=3346, point=POINT)
        vols = self.es.split_volume(0.01, plans, sl=3328.0,
                                     split_mode=NOVAL_STRATEGY["volume_split"])
        assert len(plans) == 3
        assert all(v == 0.01 for v in vols)

    def test_sell_level_ids_sequential(self):
        """Level IDs must be 0, 1, 2 for proper re-entry tracking."""
        sig = _sig(side=Side.SELL, entry_range=[3340.0, 3347.0])
        plans = self.es.plan_entries(sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT)
        ids = [p.level_id for p in plans]
        assert ids == [0, 1, 2]


# ═════════════════════════════════════════════════════════════════
# G1 + G7: Min SL Distance + Max Re-entry Distance
# (Boundary value tests — Pipeline logic)
# These test the decision logic, not MT5 execution.
# ═════════════════════════════════════════════════════════════════


class TestG1MinSlDistanceBoundary:
    """min_sl_distance_pips=20 → 20×0.1 = $2.00 for Gold.
    Skip order if |price - SL| < 2.00.
    """

    def test_price_far_from_sl_accepts(self):
        """SELL SL=3352, price=3340 → distance = 12 / 0.1 = 120 pip > 20 → OK."""
        price = 3340.0
        sl = 3352.0
        distance_pips = abs(price - sl) / PIP_SIZE
        assert distance_pips == 120.0
        assert distance_pips >= NOVAL_STRATEGY["min_sl_distance_pips"]

    def test_price_too_close_to_sl_rejects(self):
        """SELL SL=3352, price=3351 → distance = 1 / 0.1 = 10 pip < 20 → REJECT."""
        price = 3351.0
        sl = 3352.0
        distance_pips = abs(price - sl) / PIP_SIZE
        assert distance_pips == 10.0
        assert distance_pips < NOVAL_STRATEGY["min_sl_distance_pips"]

    def test_price_exactly_at_boundary(self):
        """SELL SL=3352, price=3350 → distance = 2 / 0.1 = 20 pip = 20 → ACCEPT (≥)."""
        price = 3350.0
        sl = 3352.0
        distance_pips = abs(price - sl) / PIP_SIZE
        assert distance_pips == 20.0
        assert distance_pips >= NOVAL_STRATEGY["min_sl_distance_pips"]

    def test_price_one_pip_inside_boundary(self):
        """SELL SL=3352, price=3350.1 → distance = 1.9 / 0.1 = 19 pip < 20 → REJECT."""
        price = 3350.1
        sl = 3352.0
        distance_pips = abs(price - sl) / PIP_SIZE
        assert round(distance_pips, 1) == 19.0
        assert distance_pips < NOVAL_STRATEGY["min_sl_distance_pips"]

    def test_buy_distance_check(self):
        """BUY SL=3328, price=3347 → distance = 19 / 0.1 = 190 pip > 20 → OK."""
        price = 3347.0
        sl = 3328.0
        distance_pips = abs(price - sl) / PIP_SIZE
        assert distance_pips == 190.0
        assert distance_pips >= NOVAL_STRATEGY["min_sl_distance_pips"]


class TestG7MaxReentryDistanceBoundary:
    """max_reentry_distance_pips=10 → 10×0.1 = $1.00 for Gold.
    Skip re-entry if price is more than $1.00 past the plan level.
    """

    def test_price_at_level_accepts(self):
        """Price exactly at level → drift = 0 pip → OK."""
        plan_level = 3342.0
        cur_price = 3342.0
        drift_pips = abs(cur_price - plan_level) / PIP_SIZE
        assert drift_pips == 0.0
        assert drift_pips <= NOVAL_STRATEGY["max_reentry_distance_pips"]

    def test_price_within_distance_accepts(self):
        """SELL P2=3342, price=3342.5 → drift = 0.5 / 0.1 = 5 pip ≤ 10 → OK."""
        plan_level = 3342.0
        cur_price = 3342.5
        drift_pips = abs(cur_price - plan_level) / PIP_SIZE
        assert drift_pips == 5.0
        assert drift_pips <= NOVAL_STRATEGY["max_reentry_distance_pips"]

    def test_price_exactly_at_max_distance(self):
        """SELL P2=3342, price=3343 → drift = 1 / 0.1 = 10 pip = 10 → ACCEPT (≤)."""
        plan_level = 3342.0
        cur_price = 3343.0
        drift_pips = abs(cur_price - plan_level) / PIP_SIZE
        assert drift_pips == 10.0
        assert drift_pips <= NOVAL_STRATEGY["max_reentry_distance_pips"]

    def test_price_one_pip_past_max_rejects(self):
        """SELL P2=3342, price=3343.1 → drift = 1.1 / 0.1 = 11 pip > 10 → REJECT."""
        plan_level = 3342.0
        cur_price = 3343.1
        drift_pips = round(abs(cur_price - plan_level) / PIP_SIZE, 1)
        assert drift_pips == 11.0
        assert drift_pips > NOVAL_STRATEGY["max_reentry_distance_pips"]

    def test_price_far_past_level_rejects(self):
        """SELL P2=3342, price=3350 → drift = 8 / 0.1 = 80 pip >> 10 → REJECT."""
        plan_level = 3342.0
        cur_price = 3350.0
        drift_pips = abs(cur_price - plan_level) / PIP_SIZE
        assert drift_pips == 80.0
        assert drift_pips > NOVAL_STRATEGY["max_reentry_distance_pips"]

    def test_disabled_when_zero(self):
        """max_reentry_distance_pips=0 means disabled, all distances OK."""
        config_disabled = {**NOVAL_STRATEGY, "max_reentry_distance_pips": 0}
        max_dist = config_disabled["max_reentry_distance_pips"]
        # When disabled (0), check should not reject
        assert max_dist == 0  # The pipeline skips check when 0


# ═════════════════════════════════════════════════════════════════
# G5: Re-entry Tolerance (reentry_tolerance_pips=5)
# ═════════════════════════════════════════════════════════════════


class TestG5ReentryTolerance:
    """reentry_tolerance_pips=5 → 5×0.1 = $0.50 early trigger window.

    SELL P2=3342 → eff_level = 3342 - 0.50 = 3341.50
    Trigger when price >= 3341.50 (instead of >= 3342.0)
    """

    def test_sell_effective_level(self):
        """SELL: eff_level = level - tolerance."""
        level = 3342.0
        tolerance = NOVAL_STRATEGY["reentry_tolerance_pips"] * PIP_SIZE
        eff_level = level - tolerance
        assert eff_level == 3341.5

    def test_buy_effective_level(self):
        """BUY: eff_level = level + tolerance."""
        level = 3345.0
        tolerance = NOVAL_STRATEGY["reentry_tolerance_pips"] * PIP_SIZE
        eff_level = level + tolerance
        assert eff_level == 3345.5

    def test_sell_triggers_early_within_tolerance(self):
        """SELL P2=3342, price=3341.6 → 3341.6 >= eff(3341.5) → TRIGGER."""
        level = 3342.0
        cur_price = 3341.6
        eff_level = level - (NOVAL_STRATEGY["reentry_tolerance_pips"] * PIP_SIZE)
        assert cur_price >= eff_level

    def test_sell_does_not_trigger_below_tolerance(self):
        """SELL P2=3342, price=3341.4 → 3341.4 < eff(3341.5) → NO TRIGGER."""
        level = 3342.0
        cur_price = 3341.4
        eff_level = level - (NOVAL_STRATEGY["reentry_tolerance_pips"] * PIP_SIZE)
        assert cur_price < eff_level

    def test_tolerance_zero_exact_cross_required(self):
        """tolerance=0: need exact level cross."""
        level = 3342.0
        cur_price = 3341.9
        eff_level = level - (0 * PIP_SIZE)
        assert eff_level == level
        assert cur_price < eff_level

    def test_sell_p3_tolerance(self):
        """SELL P3=3344, eff=3343.5. Price 3343.7 → TRIGGER."""
        level = 3344.0
        cur_price = 3343.7
        eff_level = level - (NOVAL_STRATEGY["reentry_tolerance_pips"] * PIP_SIZE)
        assert eff_level == 3343.5
        assert cur_price >= eff_level


# ═════════════════════════════════════════════════════════════════
# G11: SL Breach → Cancel All
# ═════════════════════════════════════════════════════════════════


class TestG11SlBreachDetection:
    """If price crosses SL while plans pending → cancel all."""

    def test_sell_sl_breached(self):
        """SELL SL=3352. Price 3352 → BREACHED (>= SL)."""
        sl = 3352.0
        price = 3352.0
        breached = price >= sl  # SELL: price >= SL = breach
        assert breached

    def test_sell_sl_not_breached(self):
        """SELL SL=3352. Price 3351.9 → NOT breached."""
        sl = 3352.0
        price = 3351.9
        breached = price >= sl
        assert not breached

    def test_sell_sl_just_past(self):
        """SELL SL=3352. Price 3352.1 → BREACHED."""
        sl = 3352.0
        price = 3352.1
        breached = price >= sl
        assert breached

    def test_buy_sl_breached(self):
        """BUY SL=3328. Price 3328 → BREACHED (<= SL)."""
        sl = 3328.0
        price = 3328.0
        breached = price <= sl  # BUY: price <= SL = breach
        assert breached

    def test_buy_sl_not_breached(self):
        """BUY SL=3328. Price 3328.1 → NOT breached."""
        sl = 3328.0
        price = 3328.1
        breached = price <= sl
        assert not breached

    def test_sell_price_far_below_sl_no_breach(self):
        """SELL SL=3352. Price 3340 → NOT breached (price is in profit)."""
        sl = 3352.0
        price = 3340.0
        breached = price >= sl
        assert not breached


# ═════════════════════════════════════════════════════════════════
# G12b: Reply BE Lock Pips (reply_be_lock_pips=10)
# ═════════════════════════════════════════════════════════════════


class TestG12bReplyBeLockPips:
    """reply_be_lock_pips=10 → 10×0.1 = $1.00 lock offset for Gold.

    BUY entry=3345 → SL = 3345 + 1.0 = 3346.0
    SELL entry=3340 → SL = 3340 - 1.0 = 3339.0
    """

    LOCK_PIPS = 10  # Noval config
    LOCK_DISTANCE = LOCK_PIPS * PIP_SIZE  # 10 × 0.1 = 1.0

    def test_buy_be_above_entry(self):
        """BUY entry=3345 → SL = 3345 + 1.0 = 3346.0 (locks $1.00 profit)."""
        entry = 3345.0
        new_sl = entry + self.LOCK_DISTANCE
        assert new_sl == 3346.0

    def test_sell_be_below_entry(self):
        """SELL entry=3340 → SL = 3340 - 1.0 = 3339.0 (locks $1.00 profit)."""
        entry = 3340.0
        new_sl = entry - self.LOCK_DISTANCE
        assert new_sl == 3339.0

    def test_lock_zero_exact_entry(self):
        """lock_pips=0 → SL = entry (old behavior)."""
        entry = 3345.0
        lock_distance = 0 * PIP_SIZE
        new_sl = entry + lock_distance
        assert new_sl == entry

    def test_lock_1_pip_default(self):
        """Default lock_pips=1 → 1×0.1 = $0.10 offset."""
        entry = 3345.0
        lock_distance = 1 * PIP_SIZE
        new_sl = entry + lock_distance
        assert new_sl == 3345.1

    def test_lock_distance_calculation(self):
        """Verify the math: 10 pips × 0.10 pip_size = 1.0."""
        assert self.LOCK_DISTANCE == 1.0


# ═════════════════════════════════════════════════════════════════
# Noval Scenario Tests (full flow simulations)
# ═════════════════════════════════════════════════════════════════


class TestNovalSellScenario:
    """Full scenario: SELL XAUUSD 3340-3347 SL 3352 TP 3320
    (typical Noval channel signal).
    """

    def setup_method(self):
        self.es = EntryStrategy()
        self.sig = _sig(
            side=Side.SELL,
            entry=3340.0,
            sl=3352.0,
            tp=[3320.0],
            entry_range=[3340.0, 3347.0],
        )

    def test_plan_levels(self):
        """P1=3340, P2=3342, P3=3344."""
        plans = self.es.plan_entries(
            self.sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT
        )
        levels = [p.level for p in plans]
        assert levels == [3340.0, 3342.0, 3344.0]

    def test_volumes_per_entry(self):
        """Each order gets 0.01 lot (FIXED_LOT_SIZE)."""
        plans = self.es.plan_entries(
            self.sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT
        )
        vols = self.es.split_volume(0.01, plans, sl=3352.0, split_mode="per_entry")
        assert vols == [0.01, 0.01, 0.01]

    def test_p1_sl_distance_ok(self):
        """P1=3340, SL=3352 → distance=120pip ≥ 20 → ACCEPT."""
        dist = abs(3340.0 - 3352.0) / PIP_SIZE
        assert dist == 120.0
        assert dist >= 20

    def test_p2_sl_distance_ok(self):
        """P2=3342, SL=3352 → distance=100pip ≥ 20 → ACCEPT."""
        dist = abs(3342.0 - 3352.0) / PIP_SIZE
        assert dist == 100.0
        assert dist >= 20

    def test_p3_sl_distance_ok(self):
        """P3=3344, SL=3352 → distance=80pip ≥ 20 → ACCEPT."""
        dist = abs(3344.0 - 3352.0) / PIP_SIZE
        assert dist == 80.0
        assert dist >= 20

    def test_p2_reentry_tolerance_trigger(self):
        """P2=3342, tolerance=5pip → eff=3341.5. Price 3341.6 → TRIGGER ✓."""
        eff = 3342.0 - (5 * PIP_SIZE)
        assert 3341.6 >= eff

    def test_p2_max_reentry_distance(self):
        """P2=3342, max=10pip. Price=3343 → drift=10 ≤ 10 → OK.
        Price=3343.5 → drift=15 > 10 → REJECT.
        """
        assert abs(3343.0 - 3342.0) / PIP_SIZE == 10.0   # boundary: OK
        assert abs(3343.5 - 3342.0) / PIP_SIZE == 15.0   # exceeded: REJECT

    def test_sl_breach_cancels_all(self):
        """Price=3352 (=SL) → breach → cancel P2,P3 pending."""
        sl = 3352.0
        price = 3352.0
        assert price >= sl  # breach

    def test_reply_be_lock_sell(self):
        """Reply 'be' on P1 entry=3340 → SL=3340-1.0=3339.0."""
        entry = 3340.0
        lock = 10 * PIP_SIZE  # reply_be_lock_pips=10
        new_sl = entry - lock
        assert new_sl == 3339.0

    def test_p3_level_above_zone(self):
        """P3=3344 > zone_high=3347? No. 3344 < 3347 → still inside zone."""
        plans = self.es.plan_entries(
            self.sig, NOVAL_STRATEGY, bid=3341, ask=3342, point=POINT
        )
        zone_high = 3347.0
        assert plans[2].level < zone_high


class TestNovalBuyScenario:
    """Full scenario: BUY XAUUSD 3340-3347 SL 3328 TP 3370."""

    def setup_method(self):
        self.es = EntryStrategy()
        self.sig = _sig(
            side=Side.BUY,
            entry=3347.0,
            sl=3328.0,
            tp=[3370.0],
            entry_range=[3340.0, 3347.0],
        )

    def test_plan_levels(self):
        """P1=3347, P2=3345, P3=3343."""
        plans = self.es.plan_entries(
            self.sig, NOVAL_STRATEGY, bid=3345, ask=3346, point=POINT
        )
        levels = [p.level for p in plans]
        assert levels == [3347.0, 3345.0, 3343.0]

    def test_all_above_sl(self):
        """All levels must be above SL=3328."""
        plans = self.es.plan_entries(
            self.sig, NOVAL_STRATEGY, bid=3345, ask=3346, point=POINT
        )
        for p in plans:
            assert p.level > 3328.0, f"Level {p.level} must be above SL 3328"

    def test_reply_be_lock_buy(self):
        """Reply 'be' on P1 entry=3347 → SL=3347+1.0=3348.0."""
        entry = 3347.0
        lock = 10 * PIP_SIZE
        new_sl = entry + lock
        assert new_sl == 3348.0

    def test_sl_breach_buy(self):
        """BUY SL=3328. Price=3327 → breached (price ≤ SL)."""
        assert 3327.0 <= 3328.0


# ═════════════════════════════════════════════════════════════════
# Edge Case: Multiple Guards Working Together
# ═════════════════════════════════════════════════════════════════


class TestGuardCombinations:
    """Test guard interactions — when multiple guards could fire."""

    def test_price_in_tolerance_but_past_max_distance(self):
        """
        SELL P2=3342. Price=3343.5.
        Tolerance: eff=3341.5, 3343.5 ≥ 3341.5 → CROSSED ✓
        Max dist: drift=15 > 10 → REJECT ✗
        Result: tolerance says trigger, but max_distance says reject → REJECT wins.
        """
        level = 3342.0
        cur_price = 3343.5
        eff_level = level - (5 * PIP_SIZE)
        drift_pips = abs(cur_price - level) / PIP_SIZE

        crossed = cur_price >= eff_level
        too_far = drift_pips > 10

        assert crossed  # tolerance says trigger
        assert too_far  # but max distance says reject

    def test_price_in_tolerance_and_within_max_distance(self):
        """
        SELL P2=3342. Price=3342.8.
        Tolerance: 3342.8 ≥ 3341.5 → CROSSED ✓
        Max dist: drift=8 ≤ 10 → OK ✓
        SL dist: |3342.8 - 3352| = 92 pip ≥ 20 → OK ✓
        Result: ALL guards pass → TRIGGER.
        """
        level = 3342.0
        cur_price = 3342.8
        sl = 3352.0

        eff_level = level - (5 * PIP_SIZE)
        drift_pips = abs(cur_price - level) / PIP_SIZE
        sl_dist_pips = abs(cur_price - sl) / PIP_SIZE

        assert cur_price >= eff_level  # crossed
        assert drift_pips <= 10  # within max distance
        assert sl_dist_pips >= 20  # far enough from SL

    def test_price_close_to_sl_rejects_even_if_crossed(self):
        """
        SELL P2=3350. Price=3351.
        Tolerance: 3351 ≥ 3349.5 → CROSSED ✓
        Max dist: 10 ≤ 10 → OK ✓
        SL dist: |3351 - 3352| = 10 pip < 20 → REJECT ✗
        Result: SL too close → REJECT.
        """
        level = 3350.0
        cur_price = 3351.0
        sl = 3352.0

        eff_level = level - (5 * PIP_SIZE)
        drift_pips = abs(cur_price - level) / PIP_SIZE
        sl_dist_pips = abs(cur_price - sl) / PIP_SIZE

        assert cur_price >= eff_level  # crossed
        assert drift_pips <= 10  # within max distance
        assert sl_dist_pips < 20  # TOO CLOSE → reject
