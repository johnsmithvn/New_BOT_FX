"""
core/circuit_breaker.py

Circuit breaker pattern for trade execution safety.
Pauses trading after consecutive failures.

States:
    CLOSED  → normal, trades execute
    OPEN    → trading paused, cooldown active
    HALF_OPEN → probe: allow one trade to test recovery
"""

from __future__ import annotations

import enum
import time

from utils.logger import log_event


class BreakerState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Circuit breaker for trade execution.

    Opens after `failure_threshold` consecutive failures.
    Auto-resets after `cooldown_seconds`.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: int = 300,
    ) -> None:
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float = 0.0
        self._on_state_change: list = []

    @property
    def state(self) -> BreakerState:
        """Current breaker state, auto-transition OPEN→HALF_OPEN on cooldown."""
        if self._state == BreakerState.OPEN:
            elapsed = time.time() - self._opened_at
            if elapsed >= self._cooldown:
                self._transition(BreakerState.HALF_OPEN)
        return self._state

    @property
    def is_trading_allowed(self) -> bool:
        """True if trades can be executed."""
        return self.state in (BreakerState.CLOSED, BreakerState.HALF_OPEN)

    def on_state_change(self, callback) -> None:
        """Register a callback for state transitions.

        Callback receives (old_state, new_state).
        """
        self._on_state_change.append(callback)

    def record_success(self) -> None:
        """Record a successful execution."""
        if self._state == BreakerState.HALF_OPEN:
            self._transition(BreakerState.CLOSED)

        self._consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed execution."""
        self._consecutive_failures += 1

        if self._state == BreakerState.HALF_OPEN:
            # Probe failed, re-open immediately
            self._transition(BreakerState.OPEN)
            return

        if self._consecutive_failures >= self._threshold:
            self._transition(BreakerState.OPEN)

    def _transition(self, new_state: BreakerState) -> None:
        """Transition to a new state."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state

        if new_state == BreakerState.OPEN:
            self._opened_at = time.time()

        if new_state == BreakerState.CLOSED:
            self._consecutive_failures = 0

        log_event(
            "circuit_breaker_state_change",
            old_state=old_state.value,
            new_state=new_state.value,
            consecutive_failures=self._consecutive_failures,
            cooldown_seconds=self._cooldown,
        )

        for cb in self._on_state_change:
            try:
                cb(old_state, new_state)
            except Exception as exc:
                log_event(
                    "circuit_breaker_callback_error",
                    error=str(exc),
                )
