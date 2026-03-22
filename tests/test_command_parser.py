"""
tests/test_command_parser.py

Unit tests for core/command_parser.py — management commands.
"""

from core.command_parser import CommandParser, CommandType


class TestCommandParser:
    """Tests for CommandParser.parse()."""

    def setup_method(self):
        self.parser = CommandParser()

    # ── CLOSE ALL ────────────────────────────────────────────────

    def test_close_all(self):
        cmd = self.parser.parse("CLOSE ALL")
        assert cmd is not None
        assert cmd.command_type == CommandType.CLOSE_ALL

    def test_close_all_trades(self):
        cmd = self.parser.parse("CLOSE ALL TRADES")
        assert cmd.command_type == CommandType.CLOSE_ALL

    def test_close_everything(self):
        cmd = self.parser.parse("CLOSE EVERYTHING")
        assert cmd.command_type == CommandType.CLOSE_ALL

    # ── CLOSE HALF ───────────────────────────────────────────────

    def test_close_half(self):
        cmd = self.parser.parse("CLOSE HALF")
        assert cmd.command_type == CommandType.CLOSE_HALF

    def test_close_50_percent(self):
        cmd = self.parser.parse("CLOSE 50%")
        assert cmd.command_type == CommandType.CLOSE_HALF

    # ── CLOSE SYMBOL ─────────────────────────────────────────────

    def test_close_symbol(self):
        cmd = self.parser.parse("CLOSE XAUUSD")
        assert cmd.command_type == CommandType.CLOSE_SYMBOL
        assert cmd.symbol == "XAUUSD"

    def test_close_eurusd(self):
        cmd = self.parser.parse("CLOSE EURUSD")
        assert cmd.command_type == CommandType.CLOSE_SYMBOL
        assert cmd.symbol == "EURUSD"

    # ── BREAKEVEN ────────────────────────────────────────────────

    def test_breakeven(self):
        cmd = self.parser.parse("BREAKEVEN")
        assert cmd.command_type == CommandType.BREAKEVEN

    def test_be_alias(self):
        cmd = self.parser.parse("BE")
        assert cmd.command_type == CommandType.BREAKEVEN

    def test_break_even(self):
        cmd = self.parser.parse("BREAK EVEN")
        assert cmd.command_type == CommandType.BREAKEVEN

    # ── MOVE SL ──────────────────────────────────────────────────

    def test_move_sl(self):
        cmd = self.parser.parse("MOVE SL 2035")
        assert cmd.command_type == CommandType.MOVE_SL
        assert cmd.price == 2035.0

    def test_move_sl_decimal(self):
        cmd = self.parser.parse("MOVE SL 2035.50")
        assert cmd.command_type == CommandType.MOVE_SL
        assert cmd.price == 2035.5

    # ── Not a command ────────────────────────────────────────────

    def test_signal_is_not_command(self):
        assert self.parser.parse("BUY GOLD 2030") is None

    def test_empty_text(self):
        assert self.parser.parse("") is None

    def test_none_text(self):
        assert self.parser.parse(None) is None

    def test_case_insensitive(self):
        cmd = self.parser.parse("close all")
        assert cmd.command_type == CommandType.CLOSE_ALL

    def test_raw_text_preserved(self):
        cmd = self.parser.parse("Close All")
        assert cmd.raw_text == "Close All"
