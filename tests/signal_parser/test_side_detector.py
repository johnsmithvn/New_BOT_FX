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
