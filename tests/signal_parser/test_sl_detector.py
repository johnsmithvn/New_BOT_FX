"""
tests/signal_parser/test_sl_detector.py

Unit tests for core/signal_parser/sl_detector.py — SL detection.
"""

from core.signal_parser.sl_detector import detect


class TestSlDetector:
    """Tests for detect() — Stop Loss detection."""

    def test_sl_with_colon(self):
        assert detect("SL: 2020") == 2020.0

    def test_sl_without_colon(self):
        assert detect("SL 2020") == 2020.0

    def test_stop_loss_keyword(self):
        assert detect("STOP LOSS 2020") == 2020.0

    def test_stoploss_combined(self):
        assert detect("STOPLOSS 2020.50") == 2020.5

    def test_sl_slash_format(self):
        assert detect("S/L: 2020") == 2020.0

    def test_decimal_sl(self):
        assert detect("SL 2019.75") == 2019.75

    def test_no_sl_returns_none(self):
        assert detect("BUY GOLD 2030") is None

    def test_sl_zero_rejected(self):
        assert detect("SL: 0") is None

    def test_empty_text_returns_none(self):
        assert detect("") is None

    def test_sl_in_full_signal(self):
        text = "BUY GOLD 2030\nSL: 2020\nTP: 2050"
        assert detect(text) == 2020.0
