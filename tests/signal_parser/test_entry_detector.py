"""
tests/signal_parser/test_entry_detector.py

Unit tests for core/signal_parser/entry_detector.py — entry price detection.
"""

from core.signal_parser.entry_detector import detect
from core.models import Side


class TestEntryDetector:
    """Tests for detect() — entry price and range detection."""

    # ── Explicit entry patterns ──────────────────────────────────

    def test_explicit_entry_keyword(self):
        entry, rng, is_market = detect("ENTRY 2030")
        assert entry == 2030.0
        assert rng is None
        assert is_market is False

    def test_entry_with_colon(self):
        entry, _, _ = detect("ENTRY: 2030.50")
        assert entry == 2030.5

    def test_entry_price_keyword(self):
        entry, _, _ = detect("ENTRY PRICE 2030")
        assert entry == 2030.0

    def test_at_symbol(self):
        entry, _, _ = detect("BUY GOLD @ 2030")
        assert entry == 2030.0

    def test_price_keyword(self):
        entry, _, _ = detect("PRICE: 2030")
        assert entry == 2030.0

    def test_enter_at_keyword(self):
        entry, _, _ = detect("ENTER AT 2030")
        assert entry == 2030.0

    # ── Range detection ──────────────────────────────────────────

    def test_range_with_dash(self):
        entry, rng, is_market = detect("ENTRY 2030 - 2035", Side.BUY)
        assert rng == [2030.0, 2035.0]
        assert entry == 2030.0  # BUY picks low
        assert is_market is False

    def test_range_sell_picks_high(self):
        entry, rng, _ = detect("ENTRY 2030 - 2035", Side.SELL)
        assert entry == 2035.0  # SELL picks high
        assert rng == [2030.0, 2035.0]

    def test_range_with_to(self):
        entry, rng, _ = detect("ENTRY 2030 TO 2035", Side.BUY)
        assert rng == [2030.0, 2035.0]

    def test_range_reversed_order(self):
        """Values in wrong order should still be normalized to [low, high]."""
        entry, rng, _ = detect("ENTRY 2035 - 2030", Side.BUY)
        assert rng == [2030.0, 2035.0]

    def test_buy_side_price_range(self):
        entry, rng, _ = detect("BUY GOLD 2030/2035", Side.BUY)
        assert rng == [2030.0, 2035.0]

    # ── Market keywords ──────────────────────────────────────────

    def test_market_now(self):
        entry, rng, is_market = detect("BUY GOLD NOW")
        assert entry is None
        assert is_market is True

    def test_market_cmp(self):
        _, _, is_market = detect("BUY GOLD CMP")
        assert is_market is True

    def test_market_execution_keyword(self):
        _, _, is_market = detect("BUY GOLD MARKET EXECUTION")
        assert is_market is True

    def test_range_takes_priority_over_now(self):
        """Range in text should be detected even if 'NOW' also present."""
        entry, rng, is_market = detect("BUY GOLD ZONE 4963 - 4961 NOW", Side.BUY)
        # Range should be detected first
        assert rng is not None
        assert is_market is False

    # ── Side+price fallback ──────────────────────────────────────

    def test_side_price_fallback(self):
        entry, _, _ = detect("BUY GOLD 2030")
        assert entry == 2030.0

    # ── Edge cases ───────────────────────────────────────────────

    def test_no_entry_no_market(self):
        entry, rng, is_market = detect("BUY GOLD")
        assert entry is None
        assert rng is None
        assert is_market is False

    def test_empty_text(self):
        entry, rng, is_market = detect("")
        assert entry is None
        assert rng is None
        assert is_market is False
