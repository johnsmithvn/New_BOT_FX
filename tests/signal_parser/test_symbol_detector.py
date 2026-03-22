"""
tests/signal_parser/test_symbol_detector.py

Unit tests for core/signal_parser/symbol_detector.py — symbol detection.
"""

from core.signal_parser.symbol_detector import detect
from utils.symbol_mapper import SymbolMapper


class TestSymbolDetector:
    """Tests for detect() — trading symbol detection."""

    def setup_method(self):
        self.mapper = SymbolMapper()

    def test_direct_symbol(self):
        assert detect("BUY XAUUSD 2030", self.mapper) == "XAUUSD"

    def test_gold_alias(self):
        assert detect("BUY GOLD 2030", self.mapper) == "XAUUSD"

    def test_silver_alias(self):
        assert detect("SELL SILVER 25.00", self.mapper) == "XAGUSD"

    def test_slash_separated_pair(self):
        assert detect("BUY XAU/USD 2030", self.mapper) == "XAUUSD"

    def test_forex_pair(self):
        assert detect("SELL EURUSD 1.0500", self.mapper) == "EURUSD"

    def test_no_symbol_returns_none(self):
        assert detect("BUY AT 2030", self.mapper) is None

    def test_empty_text_returns_none(self):
        assert detect("", self.mapper) is None

    def test_first_known_symbol_wins(self):
        result = detect("BUY EURUSD SL GBPUSD", self.mapper)
        assert result == "EURUSD"

    def test_unknown_token_skipped(self):
        assert detect("BUY ZZZYYY 2030", self.mapper) is None

    def test_index_symbol_via_alias(self):
        # NAS100 has digits → won't match [A-Z]{3,10} pattern
        # Use NASDAQ alias instead
        assert detect("BUY NASDAQ 15000", self.mapper) == "NAS100"

    def test_nasdaq_alias(self):
        assert detect("BUY NASDAQ 15000", self.mapper) == "NAS100"

    def test_crypto(self):
        assert detect("BUY BTCUSD 40000", self.mapper) == "BTCUSD"

    def test_oil_alias(self):
        assert detect("SELL WTI 75.00", self.mapper) == "USOIL"
