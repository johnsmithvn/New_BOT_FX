"""
tests/signal_parser/test_parser.py

Unit tests for core/signal_parser/parser.py — parser orchestration.
"""

from core.signal_parser.parser import SignalParser, generate_fingerprint
from core.models import ParsedSignal, ParseFailure, Side
from utils.symbol_mapper import SymbolMapper


class TestGenerateFingerprint:
    """Tests for generate_fingerprint() — signal hashing."""

    def test_deterministic(self):
        fp1 = generate_fingerprint("XAUUSD", "BUY", 2030.0, 2020.0, [2050.0], "ch1")
        fp2 = generate_fingerprint("XAUUSD", "BUY", 2030.0, 2020.0, [2050.0], "ch1")
        assert fp1 == fp2

    def test_different_entry_different_hash(self):
        fp1 = generate_fingerprint("XAUUSD", "BUY", 2030.0, 2020.0, [2050.0])
        fp2 = generate_fingerprint("XAUUSD", "BUY", 2035.0, 2020.0, [2050.0])
        assert fp1 != fp2

    def test_none_entry_uses_market_string(self):
        fp = generate_fingerprint("XAUUSD", "BUY", None, 2020.0, [2050.0])
        assert isinstance(fp, str)
        assert len(fp) == 16

    def test_chat_id_affects_hash(self):
        fp1 = generate_fingerprint("XAUUSD", "BUY", 2030.0, 2020.0, [], "chatA")
        fp2 = generate_fingerprint("XAUUSD", "BUY", 2030.0, 2020.0, [], "chatB")
        assert fp1 != fp2

    def test_hash_length_16(self):
        fp = generate_fingerprint("XAUUSD", "BUY", 2030.0, 2020.0, [2050.0])
        assert len(fp) == 16


class TestSignalParser:
    """Tests for SignalParser.parse() — full pipeline orchestration."""

    def setup_method(self):
        self.parser = SignalParser(symbol_mapper=SymbolMapper())

    def test_full_signal_success(self):
        raw = "BUY GOLD 2030\nSL: 2020\nTP: 2050"
        result = self.parser.parse(raw, source_chat_id="ch1", source_message_id="1")
        assert isinstance(result, ParsedSignal)
        assert result.symbol == "XAUUSD"
        assert result.side == Side.BUY
        assert result.entry == 2030.0
        assert result.sl == 2020.0
        assert result.tp == [2050.0]
        assert result.fingerprint

    def test_market_signal(self):
        raw = "BUY GOLD NOW\nSL: 2020"
        result = self.parser.parse(raw)
        assert isinstance(result, ParsedSignal)
        assert result.entry is None
        assert result.side == Side.BUY

    def test_sell_signal(self):
        raw = "SELL XAUUSD 2050\nSL: 2060\nTP1: 2040\nTP2: 2030"
        result = self.parser.parse(raw)
        assert isinstance(result, ParsedSignal)
        assert result.side == Side.SELL
        assert result.entry == 2050.0
        assert len(result.tp) == 2

    def test_missing_symbol_returns_failure(self):
        raw = "BUY 2030\nSL: 2020"
        result = self.parser.parse(raw)
        assert isinstance(result, ParseFailure)
        assert "symbol" in result.reason

    def test_missing_side_returns_failure(self):
        raw = "GOLD 2030\nSL: 2020"
        result = self.parser.parse(raw)
        assert isinstance(result, ParseFailure)
        assert "side" in result.reason

    def test_no_entry_no_market_returns_failure(self):
        raw = "BUY GOLD\nSL: 2020"
        result = self.parser.parse(raw)
        assert isinstance(result, ParseFailure)
        assert "entry" in result.reason

    def test_empty_text_returns_failure(self):
        raw = ""
        result = self.parser.parse(raw)
        assert isinstance(result, ParseFailure)

    def test_oversized_text_returns_failure(self):
        raw = "BUY GOLD " + "X" * 2100
        result = self.parser.parse(raw)
        assert isinstance(result, ParseFailure)

    def test_fingerprint_deterministic(self):
        raw = "BUY GOLD 2030\nSL: 2020"
        r1 = self.parser.parse(raw, source_chat_id="ch1")
        r2 = self.parser.parse(raw, source_chat_id="ch1")
        assert isinstance(r1, ParsedSignal)
        assert isinstance(r2, ParsedSignal)
        assert r1.fingerprint == r2.fingerprint

    def test_fingerprint_includes_chat_id(self):
        raw = "BUY GOLD 2030\nSL: 2020"
        r1 = self.parser.parse(raw, source_chat_id="chatA")
        r2 = self.parser.parse(raw, source_chat_id="chatB")
        assert isinstance(r1, ParsedSignal)
        assert isinstance(r2, ParsedSignal)
        assert r1.fingerprint != r2.fingerprint

    def test_range_detection_in_full_parse(self):
        raw = "BUY GOLD 2030 - 2035\nSL: 2020\nTP: 2050"
        result = self.parser.parse(raw)
        assert isinstance(result, ParsedSignal)
        assert result.entry_range is not None
        assert len(result.entry_range) == 2

    def test_exception_safety(self):
        """Parser should never crash on any input."""
        # We can't easily force internal exception, but garbage input should be safe
        result = self.parser.parse("\x00\x01\x02\x03")
        assert isinstance(result, (ParsedSignal, ParseFailure))
