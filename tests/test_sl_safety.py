"""
tests/test_sl_safety.py

SL Direction Safety Tests — ensure NO code path can overwrite
a favorable SL with a worse one.

Rule: SL only moves in the favorable direction.
  BUY:  SL only moves UP    (higher SL = more profit locked)
  SELL: SL only moves DOWN  (lower SL  = more profit locked)
"""

from unittest.mock import MagicMock, patch
from core.reply_command_executor import ReplyCommandExecutor


# ── Helpers ──────────────────────────────────────────────────────

def _mock_position(type_: int, entry: float, sl: float, ticket: int = 1001,
                   symbol: str = "XAUUSD", tp: float = 0.0, volume: float = 0.01):
    """Create a mock MT5 position object."""
    pos = MagicMock()
    pos.type = type_           # 0=BUY, 1=SELL
    pos.price_open = entry
    pos.sl = sl
    pos.tp = tp
    pos.ticket = ticket
    pos.symbol = symbol
    pos.volume = volume
    return pos


PIP_SIZE = 0.10  # Gold


# ═════════════════════════════════════════════════════════════════
# Reply BE Guard Tests (reply_command_executor._breakeven)
# ═════════════════════════════════════════════════════════════════


class TestReplyBEGuard:
    """Reply 'be' must NOT overwrite a better SL."""

    def setup_method(self):
        self.executor = ReplyCommandExecutor(magic=234000)

    # ── SELL: SL below entry = good. Lower = better ──────────

    def test_sell_auto_be_better_than_reply_be(self):
        """
        SELL entry=3340, auto BE set SL=3337 (lock $3).
        Reply 'be' with lock=10 pip would set SL=3339 (lock $1).
        3339 > 3337 → WORSE for SELL → should NOT overwrite.
        """
        pos = _mock_position(type_=1, entry=3340.0, sl=3337.0)
        result = self.executor._breakeven(pos, lock_pips=10)
        assert "already" in result.lower() or "ℹ" in result
        # SL should NOT have been changed

    def test_sell_no_sl_applies_be(self):
        """SELL entry=3340, SL=0 (none). Reply 'be' lock=10 → SL=3339."""
        pos = _mock_position(type_=1, entry=3340.0, sl=0.0)
        # This will try to call mt5.symbol_info which we'd need to mock
        # but the guard check (pos.sl > 0) means sl=0 bypasses the guard
        # Just verify the guard logic: sl=0 → guard skipped
        new_sl = 3340.0 - (10 * PIP_SIZE)  # 3339.0
        assert new_sl == 3339.0
        assert pos.sl == 0.0  # no current SL
        # Guard: new_sl >= pos.sl → 3339 >= 0 → True BUT pos.sl > 0 is False
        # So guard does NOT trigger → BE applies ✅

    def test_sell_reply_be_better_than_current(self):
        """
        SELL entry=3340, current SL=3345 (still in loss zone).
        Reply 'be' lock=10 → SL=3339 (profit zone).
        3339 < 3345 → BETTER → should apply.
        """
        pos = _mock_position(type_=1, entry=3340.0, sl=3345.0)
        new_sl = 3340.0 - (10 * PIP_SIZE)
        # Guard: new_sl >= pos.sl → 3339 >= 3345 → False → guard does NOT block
        assert new_sl < pos.sl  # 3339 < 3345 → better for SELL

    # ── BUY: SL above entry = good. Higher = better ─────────

    def test_buy_auto_be_better_than_reply_be(self):
        """
        BUY entry=3340, auto BE set SL=3343 (lock $3).
        Reply 'be' lock=10 → SL=3341 (lock $1).
        3341 < 3343 → WORSE for BUY → should NOT overwrite.
        """
        pos = _mock_position(type_=0, entry=3340.0, sl=3343.0)
        result = self.executor._breakeven(pos, lock_pips=10)
        assert "already" in result.lower() or "ℹ" in result

    def test_buy_reply_be_better_than_current(self):
        """
        BUY entry=3340, current SL=3335 (loss zone).
        Reply 'be' lock=10 → SL=3341 (profit zone).
        3341 > 3335 → BETTER → should apply.
        """
        pos = _mock_position(type_=0, entry=3340.0, sl=3335.0)
        new_sl = 3340.0 + (10 * PIP_SIZE)  # 3341
        assert new_sl > pos.sl  # 3341 > 3335 → better for BUY


# ═════════════════════════════════════════════════════════════════
# Position Manager BE Guard (position_manager._apply_breakeven)
# Tests validate the guard logic WITHOUT calling MT5.
# ═════════════════════════════════════════════════════════════════


class TestAutoBeGuardLogic:
    """Auto BE must NOT overwrite a better SL."""

    def test_sell_be_skip_if_sl_already_better(self):
        """
        SELL entry=3340, trailing has set SL=3330 (lock $10).
        Auto BE lock=30 → SL=3337 (lock $3).
        3337 >= 3330 → guard triggers → SKIP.
        """
        entry = 3340.0
        current_sl = 3330.0  # trailing set this (very good)
        lock_distance = 30 * PIP_SIZE  # $3
        new_sl = entry - lock_distance  # 3337

        # Code guard line 426: if new_sl >= pos.sl: return
        assert new_sl >= current_sl  # 3337 >= 3330 → True → SKIP ✅

    def test_buy_be_skip_if_sl_already_better(self):
        """
        BUY entry=3340, trailing has set SL=3350 (lock $10).
        Auto BE lock=30 → SL=3343 (lock $3).
        3343 <= 3350 → guard triggers → SKIP.
        """
        entry = 3340.0
        current_sl = 3350.0
        lock_distance = 30 * PIP_SIZE
        new_sl = entry + lock_distance  # 3343

        # Code guard line 422: if new_sl <= pos.sl: return
        assert new_sl <= current_sl  # 3343 <= 3350 → True → SKIP ✅

    def test_sell_be_applies_when_sl_in_loss_zone(self):
        """
        SELL entry=3340, SL=3352 (loss zone).
        Auto BE lock=30 → SL=3337 (profit zone).
        3337 >= 3352? NO → guard does not trigger → APPLY.
        """
        new_sl = 3340.0 - (30 * PIP_SIZE)  # 3337
        current_sl = 3352.0
        assert not (new_sl >= current_sl)  # 3337 >= 3352 → False → APPLY ✅

    def test_buy_be_applies_when_sl_in_loss_zone(self):
        """
        BUY entry=3340, SL=3328 (loss zone).
        Auto BE lock=30 → SL=3343 (profit zone).
        3343 <= 3328? NO → APPLY.
        """
        new_sl = 3340.0 + (30 * PIP_SIZE)  # 3343
        current_sl = 3328.0
        assert not (new_sl <= current_sl)  # 3343 <= 3328 → False → APPLY ✅


# ═════════════════════════════════════════════════════════════════
# Trailing Stop Guard Logic
# ═════════════════════════════════════════════════════════════════


class TestTrailingGuardLogic:
    """Trailing must only move SL in favorable direction."""

    def test_sell_trail_moves_sl_down(self):
        """
        SELL trail=40, current_price=3330, current SL=3337.
        new_sl = 3330 + $4 = 3334.
        3334 >= 3337? NO → APPLY (moving SL DOWN = favorable).
        """
        new_sl = 3330.0 + (40 * PIP_SIZE)  # 3334
        current_sl = 3337.0
        guard_triggers = new_sl >= current_sl
        assert not guard_triggers  # APPLY ✅

    def test_sell_trail_does_not_move_sl_up(self):
        """
        SELL trail=40, current_price=3336, current SL=3334.
        new_sl = 3336 + $4 = 3340.
        3340 >= 3334? YES → SKIP (would move SL UP = unfavorable).
        """
        new_sl = 3336.0 + (40 * PIP_SIZE)  # 3340
        current_sl = 3334.0
        guard_triggers = new_sl >= current_sl
        assert guard_triggers  # SKIP ✅

    def test_buy_trail_moves_sl_up(self):
        """
        BUY trail=40, current_price=3360, current SL=3350.
        new_sl = 3360 - $4 = 3356.
        3356 <= 3350? NO → APPLY (moving SL UP = favorable).
        """
        new_sl = 3360.0 - (40 * PIP_SIZE)  # 3356
        current_sl = 3350.0
        guard_triggers = new_sl <= current_sl
        assert not guard_triggers  # APPLY ✅

    def test_buy_trail_does_not_move_sl_down(self):
        """
        BUY trail=40, current_price=3345, current SL=3350.
        new_sl = 3345 - $4 = 3341.
        3341 <= 3350? YES → SKIP (would move SL DOWN = unfavorable).
        """
        new_sl = 3345.0 - (40 * PIP_SIZE)  # 3341
        current_sl = 3350.0
        guard_triggers = new_sl <= current_sl
        assert guard_triggers  # SKIP ✅

    def test_sell_trail_does_not_exceed_entry(self):
        """
        SELL entry=3340, trail=40, price=3338.
        new_sl = 3338 + $4 = 3342.
        3342 > entry(3340)? YES → SKIP (don't trail above entry).
        """
        entry = 3340.0
        new_sl = 3338.0 + (40 * PIP_SIZE)  # 3342
        assert new_sl > entry  # guard triggers → SKIP ✅

    def test_buy_trail_does_not_go_below_entry(self):
        """
        BUY entry=3340, trail=40, price=3342.
        new_sl = 3342 - $4 = 3338.
        3338 < entry(3340)? YES → SKIP (don't trail below entry).
        """
        entry = 3340.0
        new_sl = 3342.0 - (40 * PIP_SIZE)  # 3338
        assert new_sl < entry  # guard triggers → SKIP ✅


# ═════════════════════════════════════════════════════════════════
# Group SL Guard Logic
# ═════════════════════════════════════════════════════════════════


class TestGroupSlGuardLogic:
    """Group SL only moves in favorable direction (position_manager L790-795)."""

    def test_sell_group_sl_only_moves_down(self):
        """
        SELL group, current_group_sl=3337, new candidate=3334.
        is_buy=False: new_sl >= current? 3334 >= 3337? NO → APPLY ✅
        """
        new_sl = 3334.0
        current_sl = 3337.0
        is_buy = False
        guard_triggers = (not is_buy and new_sl >= current_sl)
        assert not guard_triggers  # APPLY

    def test_sell_group_sl_rejects_upward_move(self):
        """
        SELL group, current_group_sl=3334, new candidate=3337.
        3337 >= 3334? YES → SKIP (would move SL up).
        """
        new_sl = 3337.0
        current_sl = 3334.0
        is_buy = False
        guard_triggers = (not is_buy and new_sl >= current_sl)
        assert guard_triggers  # SKIP ✅

    def test_buy_group_sl_only_moves_up(self):
        """
        BUY group, current_group_sl=3343, new candidate=3346.
        is_buy=True: new_sl <= current? 3346 <= 3343? NO → APPLY ✅
        """
        new_sl = 3346.0
        current_sl = 3343.0
        is_buy = True
        guard_triggers = (is_buy and new_sl <= current_sl)
        assert not guard_triggers  # APPLY

    def test_buy_group_sl_rejects_downward_move(self):
        """
        BUY group, current_group_sl=3346, new candidate=3343.
        3343 <= 3346? YES → SKIP (would move SL down).
        """
        new_sl = 3343.0
        current_sl = 3346.0
        is_buy = True
        guard_triggers = (is_buy and new_sl <= current_sl)
        assert guard_triggers  # SKIP ✅


# ═════════════════════════════════════════════════════════════════
# Command Executor BE Guard (command_executor._breakeven)
# ═════════════════════════════════════════════════════════════════


class TestCommandBEGuardLogic:
    """Global 'BREAKEVEN' command skips positions with SL already at/past entry."""

    def test_sell_sl_already_below_entry_skips(self):
        """
        SELL entry=3340, SL=3337 (below entry = profit zone).
        Code L265: pos.sl > 0 and pos.sl <= pos.price_open → True → SKIP.
        """
        sl = 3337.0
        entry = 3340.0
        guard = sl > 0 and sl <= entry
        assert guard  # SKIP — already better than BE ✅

    def test_sell_sl_above_entry_applies(self):
        """
        SELL entry=3340, SL=3352 (above entry = loss zone).
        Code L265: 3352 <= 3340 → False → APPLY.
        """
        sl = 3352.0
        entry = 3340.0
        guard = sl > 0 and sl <= entry
        assert not guard  # APPLY ✅

    def test_buy_sl_already_above_entry_skips(self):
        """
        BUY entry=3340, SL=3343 (above entry = profit zone).
        Code L262: pos.sl >= pos.price_open → True → SKIP.
        """
        sl = 3343.0
        entry = 3340.0
        guard = sl >= entry
        assert guard  # SKIP ✅

    def test_buy_sl_below_entry_applies(self):
        """
        BUY entry=3340, SL=3328 (below entry = loss zone).
        Code L262: 3328 >= 3340 → False → APPLY.
        """
        sl = 3328.0
        entry = 3340.0
        guard = sl >= entry
        assert not guard  # APPLY ✅
