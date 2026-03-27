"""
tests/signal_parser/test_side_detector.py

Unit tests for core/signal_parser/side_detector.py — BUY/SELL detection.
"""

from core.signal_parser.side_detector import detect


class TestSideDetector:
    """Tests for detect() — trade direction detection."""

    def test_detect_buy(self):
        assert detect("BUY XAUUSD 2030") == "BUY"

    def test_detect_sell(self):
        assert detect("SELL EURUSD 1.0500") == "SELL"

    def test_long_alias(self):
        assert detect("LONG GOLD 2030") == "BUY"

    def test_short_alias(self):
        assert detect("SHORT GOLD 2030") == "SELL"

    def test_buy_stop(self):
        assert detect("BUY STOP GOLD 2030") == "BUY"

    def test_buy_limit(self):
        assert detect("BUY LIMIT GOLD 2020") == "BUY"

    def test_sell_stop(self):
        assert detect("SELL STOP GOLD 2020") == "SELL"

    def test_sell_limit(self):
        assert detect("SELL LIMIT GOLD 2030") == "SELL"

    def test_no_side_returns_none(self):
        assert detect("XAUUSD 2030") is None

    def test_empty_text_returns_none(self):
        assert detect("") is None

    def test_first_match_wins(self):
        # BUY appears before SELL
        assert detect("BUY SELL") == "BUY"

    def test_word_boundary(self):
        # BUY should match only as a whole word
        assert detect("XAUUSD BUY 2030") == "BUY"
        # BUYING should NOT match when using \bBUY\b word boundary
        assert detect("BUYING GOLD 2030") is None

    # ── v0.22.2: Typo-tolerant patterns ───────────────────────────

    def test_sel_typo(self):
        """Real case: admin typed 'SEL' instead of 'SELL'."""
        assert detect("SEL GOLD ZONE 4450 - 4452") == "SELL"

    def test_selll_extra_l(self):
        assert detect("SELLL GOLD 2030") == "SELL"

    def test_seel_doubled_e(self):
        assert detect("SEEL GOLD 2030") == "SELL"

    def test_ssel_doubled_s(self):
        assert detect("SSEL GOLD 2030") == "SELL"

    def test_ssell_doubled_s_full(self):
        assert detect("SSELL GOLD 2030") == "SELL"

    def test_seell_double_e_double_l(self):
        assert detect("SEELL GOLD 2030") == "SELL"

    def test_bbuy_doubled_b(self):
        assert detect("BBUY GOLD 2030") == "BUY"

    def test_buuy_doubled_u(self):
        assert detect("BUUY GOLD 2030") == "BUY"

    def test_byu_transposition(self):
        assert detect("BYU GOLD 2030") == "BUY"

    # ── v0.22.2: Intentionally excluded patterns ──────────────────

    def test_by_not_matched(self):
        """BY is a common English word — must NOT match."""
        assert detect("BY GOLD 2030") is None

    def test_bu_not_matched(self):
        """BU is too short — must NOT match."""
        assert detect("BU GOLD 2030") is None
