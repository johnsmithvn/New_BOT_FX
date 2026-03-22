"""
tests/test_circuit_breaker.py

Unit tests for core/circuit_breaker.py — trade execution safety.
"""

import time
from unittest.mock import patch

from core.circuit_breaker import CircuitBreaker, BreakerState


class TestInitialState:
    """Initial state is CLOSED with trading allowed."""

    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == BreakerState.CLOSED

    def test_trading_allowed_initially(self):
        cb = CircuitBreaker()
        assert cb.is_trading_allowed is True


class TestStateTransitions:
    """State machine transitions: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def test_failures_below_threshold_stays_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == BreakerState.CLOSED

    def test_failures_at_threshold_opens(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == BreakerState.OPEN

    def test_open_blocks_trading(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.is_trading_allowed is False

    @patch("time.time")
    def test_cooldown_transitions_to_half_open(self, mock_time):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10)
        mock_time.return_value = 1000.0
        cb.record_failure()
        assert cb._state == BreakerState.OPEN

        # Simulate time passing beyond cooldown
        mock_time.return_value = 1011.0
        assert cb.state == BreakerState.HALF_OPEN

    def test_half_open_allows_trading(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0)
        cb.record_failure()
        # cooldown_seconds=0 → immediately transitions on state read
        assert cb.is_trading_allowed is True  # HALF_OPEN allows trading

    def test_success_in_half_open_closes(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0)
        cb.record_failure()
        # Now in HALF_OPEN (cooldown=0)
        _ = cb.state  # triggers auto-transition to HALF_OPEN
        cb.record_success()
        assert cb.state == BreakerState.CLOSED

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0)
        cb.record_failure()
        _ = cb.state  # triggers OPEN → HALF_OPEN
        cb.record_failure()
        assert cb._state == BreakerState.OPEN

    def test_success_resets_counter(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # resets counter
        cb.record_failure()
        # Only 1 failure after reset, not 3
        assert cb.state == BreakerState.CLOSED


class TestCallbacks:
    """State change callbacks."""

    def test_callback_on_state_change(self):
        cb = CircuitBreaker(failure_threshold=1)
        calls = []
        cb.on_state_change(lambda old, new: calls.append((old, new)))
        cb.record_failure()
        assert len(calls) == 1
        assert calls[0] == (BreakerState.CLOSED, BreakerState.OPEN)

    def test_callback_exception_does_not_crash(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.on_state_change(lambda old, new: 1 / 0)  # ZeroDivisionError
        # Should not raise
        cb.record_failure()
        assert cb._state == BreakerState.OPEN
