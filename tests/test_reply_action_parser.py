"""
tests/test_reply_action_parser.py

Unit tests for core/reply_action_parser.py — reply action parsing.
"""

from core.reply_action_parser import ReplyActionParser, ReplyActionType


class TestReplyActionParser:
    """Tests for ReplyActionParser.parse()."""

    def setup_method(self):
        self.parser = ReplyActionParser()

    # ── CLOSE ────────────────────────────────────────────────────

    def test_close(self):
        r = self.parser.parse("close")
        assert r is not None
        assert r.action == ReplyActionType.CLOSE

    def test_exit(self):
        r = self.parser.parse("exit")
        assert r.action == ReplyActionType.CLOSE

    def test_out(self):
        r = self.parser.parse("out")
        assert r.action == ReplyActionType.CLOSE

    def test_vietnamese_dong(self):
        r = self.parser.parse("đóng")
        assert r.action == ReplyActionType.CLOSE

    def test_close_trade(self):
        r = self.parser.parse("close trade")
        assert r.action == ReplyActionType.CLOSE

    # ── CLOSE PARTIAL ────────────────────────────────────────────

    def test_close_partial_30(self):
        r = self.parser.parse("close 30%")
        assert r.action == ReplyActionType.CLOSE_PARTIAL
        assert r.percent == 30

    def test_close_partial_50(self):
        r = self.parser.parse("close 50%")
        assert r.action == ReplyActionType.CLOSE_PARTIAL
        assert r.percent == 50

    def test_close_partial_100(self):
        r = self.parser.parse("close 100%")
        assert r.action == ReplyActionType.CLOSE_PARTIAL
        assert r.percent == 100

    def test_close_0_percent_rejected(self):
        assert self.parser.parse("close 0%") is None

    # ── MOVE SL ──────────────────────────────────────────────────

    def test_sl_price(self):
        r = self.parser.parse("SL 2035")
        assert r.action == ReplyActionType.MOVE_SL
        assert r.price == 2035.0

    def test_move_sl_decimal(self):
        r = self.parser.parse("move sl 2035.50")
        assert r.action == ReplyActionType.MOVE_SL
        assert r.price == 2035.5

    def test_stoploss_keyword(self):
        r = self.parser.parse("stoploss 2035")
        assert r.action == ReplyActionType.MOVE_SL

    def test_stop_loss_keyword(self):
        r = self.parser.parse("stop loss 2035")
        assert r.action == ReplyActionType.MOVE_SL

    def test_sl_zero_rejected(self):
        assert self.parser.parse("SL 0") is None

    # ── MOVE TP ──────────────────────────────────────────────────

    def test_tp_price(self):
        r = self.parser.parse("TP 2050")
        assert r.action == ReplyActionType.MOVE_TP
        assert r.price == 2050.0

    def test_move_tp(self):
        r = self.parser.parse("move tp 2050.50")
        assert r.action == ReplyActionType.MOVE_TP
        assert r.price == 2050.5

    def test_take_profit_keyword(self):
        r = self.parser.parse("take profit 2050")
        assert r.action == ReplyActionType.MOVE_TP

    # ── BREAKEVEN ────────────────────────────────────────────────

    def test_be(self):
        r = self.parser.parse("BE")
        assert r.action == ReplyActionType.BREAKEVEN

    def test_breakeven(self):
        r = self.parser.parse("breakeven")
        assert r.action == ReplyActionType.BREAKEVEN

    def test_break_even(self):
        r = self.parser.parse("break even")
        assert r.action == ReplyActionType.BREAKEVEN

    def test_sl_entry(self):
        r = self.parser.parse("sl entry")
        assert r.action == ReplyActionType.BREAKEVEN

    # ── Not actionable ───────────────────────────────────────────

    def test_comment_returns_none(self):
        assert self.parser.parse("nice trade!") is None

    def test_empty_returns_none(self):
        assert self.parser.parse("") is None

    def test_whitespace_returns_none(self):
        assert self.parser.parse("   ") is None

    def test_raw_text_preserved(self):
        r = self.parser.parse("  SL 2035  ")
        assert r.raw_text == "SL 2035"

    # ── SECURE_PROFIT ─────────────────────────────────────────────

    def test_secure_profit_basic(self):
        r = self.parser.parse("+30")
        assert r is not None
        assert r.action == ReplyActionType.SECURE_PROFIT
        assert r.pips == 30

    def test_secure_profit_with_pips_word(self):
        r = self.parser.parse("+ 45 pips")
        assert r is not None
        assert r.action == ReplyActionType.SECURE_PROFIT
        assert r.pips == 45

    def test_secure_profit_with_emoji(self):
        """Bug fix: trailing emojis should not prevent parsing."""
        r = self.parser.parse("+60pips🔼🔼🔼")
        assert r is not None
        assert r.action == ReplyActionType.SECURE_PROFIT
        assert r.pips == 60

    def test_secure_profit_with_trailing_text(self):
        """Bug fix: trailing text like 'close all' should not prevent parsing."""
        r = self.parser.parse("+300pips close all🔼🔼🔼")
        assert r is not None
        assert r.action == ReplyActionType.SECURE_PROFIT
        assert r.pips == 300

    def test_secure_profit_emoji_no_pips_word(self):
        """Bug fix: +100pips💫💫💫 should parse."""
        r = self.parser.parse("+100pips💫💫💫")
        assert r is not None
        assert r.action == ReplyActionType.SECURE_PROFIT
        assert r.pips == 100

    # ── CANCEL ────────────────────────────────────────────────────

    def test_cancel_exact(self):
        r = self.parser.parse("cancel")
        assert r is not None
        assert r.action == ReplyActionType.CANCEL

    def test_cancel_uppercase(self):
        r = self.parser.parse("CANCEL")
        assert r is not None
        assert r.action == ReplyActionType.CANCEL

    def test_cancel_with_trailing_text(self):
        """v0.22.2: 'Cancel wait😍😍' was not parsed — regex used $ anchor."""
        r = self.parser.parse("Cancel wait")
        assert r is not None
        assert r.action == ReplyActionType.CANCEL

    def test_cancel_all(self):
        r = self.parser.parse("cancel all")
        assert r is not None
        assert r.action == ReplyActionType.CANCEL

    def test_miss_as_cancel(self):
        r = self.parser.parse("miss")
        assert r is not None
        assert r.action == ReplyActionType.CANCEL

    def test_skip_as_cancel(self):
        r = self.parser.parse("skip")
        assert r is not None
        assert r.action == ReplyActionType.CANCEL

    def test_cancell_double_l(self):
        r = self.parser.parse("cancell")
        assert r is not None
        assert r.action == ReplyActionType.CANCEL

    def test_cancelled_not_matched(self):
        """'cancelled' should NOT match — word boundary after 'cancel' excludes it."""
        r = self.parser.parse("cancelled the order")
        assert r is None

