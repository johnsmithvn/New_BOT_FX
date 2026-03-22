"""
tests/test_exposure_guard.py

Unit tests for core/exposure_guard.py — symbol concentration limits.
"""

from unittest.mock import MagicMock

from core.exposure_guard import ExposureGuard


def _make_guard(
    positions: list[str],
    max_same: int = 0,
    max_correlated: int = 0,
    groups: list[list[str]] | None = None,
) -> ExposureGuard:
    """Create ExposureGuard with a mocked TradeExecutor."""
    executor = MagicMock()
    executor.get_position_symbols.return_value = positions
    return ExposureGuard(
        executor=executor,
        max_same_symbol_trades=max_same,
        max_correlated_trades=max_correlated,
        correlation_groups=groups,
    )


class TestNoLimits:
    """All limits disabled (default 0)."""

    def test_always_allowed(self):
        guard = _make_guard(["XAUUSD", "XAUUSD", "XAUUSD"])
        allowed, reason = guard.is_allowed("XAUUSD")
        assert allowed is True
        assert reason == ""


class TestSameSymbolLimit:
    """Max same-symbol trades."""

    def test_at_limit_blocked(self):
        guard = _make_guard(["XAUUSD", "XAUUSD"], max_same=2)
        allowed, reason = guard.is_allowed("XAUUSD")
        assert allowed is False
        assert "same-symbol" in reason

    def test_under_limit_allowed(self):
        guard = _make_guard(["XAUUSD"], max_same=2)
        allowed, _ = guard.is_allowed("XAUUSD")
        assert allowed is True

    def test_different_symbol_not_counted(self):
        guard = _make_guard(["EURUSD", "EURUSD"], max_same=2)
        allowed, _ = guard.is_allowed("XAUUSD")
        assert allowed is True


class TestCorrelatedLimit:
    """Max correlated group trades."""

    def test_correlated_blocked(self):
        groups = [["XAUUSD", "XAGUSD"]]
        guard = _make_guard(["XAUUSD", "XAGUSD"], max_correlated=2, groups=groups)
        allowed, reason = guard.is_allowed("XAUUSD")
        assert allowed is False
        assert "correlated" in reason

    def test_correlated_under_limit(self):
        groups = [["XAUUSD", "XAGUSD"]]
        guard = _make_guard(["XAUUSD"], max_correlated=2, groups=groups)
        allowed, _ = guard.is_allowed("XAGUSD")
        assert allowed is True

    def test_no_group_match_allowed(self):
        groups = [["EURUSD", "GBPUSD"]]
        guard = _make_guard(["EURUSD", "GBPUSD"], max_correlated=2, groups=groups)
        # XAUUSD not in any group
        allowed, _ = guard.is_allowed("XAUUSD")
        assert allowed is True
