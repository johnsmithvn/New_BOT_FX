"""
tests/signal_parser/test_cleaner.py

Unit tests for core/signal_parser/cleaner.py — text normalization.
"""

from core.signal_parser.cleaner import clean


class TestClean:
    """Tests for clean() — raw text normalization."""

    def test_empty_string_returns_none(self):
        assert clean("") is None

    def test_whitespace_only_returns_none(self):
        assert clean("   ") is None

    def test_exceeds_max_length_returns_none(self):
        assert clean("A" * 2001) is None

    def test_custom_max_length(self):
        assert clean("A" * 50, max_length=40) is None
        assert clean("A" * 30, max_length=40) is not None

    def test_uppercase_normalization(self):
        result = clean("buy gold 2030")
        assert result == "BUY GOLD 2030"

    def test_strip_emoji(self):
        result = clean("BUY GOLD 🚀🔥")
        assert "🚀" not in result
        assert "🔥" not in result
        assert "BUY GOLD" in result

    def test_emoji_replaced_with_space_not_deleted(self):
        """v0.22.2: Emoji between words must become space, not empty.
        Otherwise 'Now🔼BUY' becomes 'NowBUY' and side detector fails."""
        result = clean("Now🔼BUY GOLD")
        assert "NOW BUY GOLD" == result  # space between NOW and BUY

    def test_emoji_between_words_preserves_separation(self):
        """Multiple emojis between words should still produce single space."""
        result = clean("SELL🔽🔽GOLD")
        # After emoji→space + collapse whitespace: "SELL GOLD"
        assert "SELL GOLD" in result
        assert "SELLGOLD" not in result

    def test_collapse_multiple_spaces(self):
        result = clean("BUY   GOLD   2030")
        assert result == "BUY GOLD 2030"

    def test_strip_blank_lines(self):
        result = clean("BUY\n\n\nGOLD")
        assert result == "BUY\nGOLD"

    def test_tab_replaced_with_space(self):
        result = clean("BUY\tGOLD")
        assert "BUY GOLD" in result

    def test_strip_non_printable_chars(self):
        result = clean("BUY\x00GOLD")
        assert "\x00" not in result
        assert "BUYGOLD" in result

    def test_preserve_newlines(self):
        result = clean("LINE1\nLINE2")
        assert "\n" in result

    def test_normal_signal(self):
        raw = "Buy GOLD 2030\nSL: 2020\nTP: 2050"
        result = clean(raw)
        assert "BUY GOLD 2030" in result
        assert "SL: 2020" in result
        assert "TP: 2050" in result
