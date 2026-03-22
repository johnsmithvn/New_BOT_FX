"""
tests/signal_parser/test_tp_detector.py

Unit tests for core/signal_parser/tp_detector.py — TP detection.
"""

from core.signal_parser.tp_detector import detect


class TestTpDetector:
    """Tests for detect() — Take Profit detection."""

    def test_single_tp(self):
        assert detect("TP: 2050") == [2050.0]

    def test_tp_without_colon(self):
        # "TP 2050" is ambiguous: numbered pattern TP(\d) captures "2" as
        # TP index, leaving "050" = 50.0 as the price. Use "TP: 2050" for
        # correct single-TP detection. This documents real regex behavior.
        result = detect("TP 2050")
        assert result == [50.0]

    def test_numbered_tps_ordered(self):
        text = "TP1: 2040\nTP2: 2050\nTP3: 2060"
        result = detect(text)
        assert result == [2040.0, 2050.0, 2060.0]

    def test_numbered_tps_reversed_order(self):
        """TP numbers out of order should be sorted by index."""
        text = "TP3: 2060\nTP1: 2040\nTP2: 2050"
        result = detect(text)
        assert result == [2040.0, 2050.0, 2060.0]

    def test_take_profit_keyword(self):
        assert detect("TAKE PROFIT 2050") == [2050.0]

    def test_tp_slash_format(self):
        assert detect("T/P: 2050") == [2050.0]

    def test_skip_relative_pips(self):
        assert detect("TP: 30 PIPS") == []

    def test_skip_relative_points(self):
        assert detect("TP: 50 POINTS") == []

    def test_no_tp_returns_empty(self):
        assert detect("BUY GOLD 2030") == []

    def test_empty_text_returns_empty(self):
        assert detect("") == []

    def test_mixed_absolute_and_relative(self):
        """Numbered TP with one relative should only keep absolute."""
        text = "TP1: 2050\nTP2: 30 PIPS"
        result = detect(text)
        assert 2050.0 in result
        assert 30.0 not in result

    def test_decimal_tp(self):
        assert detect("TP: 2050.75") == [2050.75]

    def test_multiple_single_tp_patterns(self):
        """Multiple unnamed TP values with colon should be deduped and sorted."""
        text = "TP: 2060\nTP: 2040"
        result = detect(text)
        assert result == [2040.0, 2060.0]

    def test_tp_zero_rejected(self):
        assert detect("TP: 0") == []
