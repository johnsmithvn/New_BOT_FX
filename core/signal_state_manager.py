"""
core/signal_state_manager.py

Track active signal lifecycle and entry plan status (P9).

RESPONSIBILITIES (strict):
- Maintain in-memory registry of active signals (range/scale_in mode)
- Persist to DB for restart recovery
- Transition state machine (PENDING → PARTIAL → COMPLETED → EXPIRED)
- Answer queries about pending re-entries

NOT responsible for:
- Executing orders
- Monitoring price
- Making strategy decisions
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from core.models import (
    EntryPlan,
    OrderKind,
    Side,
    SignalLifecycle,
    SignalState,
)
from utils.logger import log_event

if TYPE_CHECKING:
    from core.storage import Storage


class SignalStateManager:
    """Track active signals that may produce multiple orders over time.

    State machine transitions:
        PENDING → PARTIAL   (first entry plan executed)
        PARTIAL → COMPLETED (all plans executed or cancelled)
        PENDING → EXPIRED   (TTL exceeded)
        PARTIAL → EXPIRED   (TTL exceeded, cancel remaining)

    In-memory registry backed by DB persistence for restart recovery.
    Only tracks signals in range/scale_in mode — single mode signals
    are fire-and-forget and never enter this manager.
    """

    def __init__(self, storage: Storage) -> None:
        self._active: dict[str, SignalState] = {}  # base_fp → state
        self._storage = storage

    @property
    def active_count(self) -> int:
        """Number of currently tracked signals."""
        return len(self._active)

    # ── Registration ─────────────────────────────────────────────

    def register(self, state: SignalState) -> None:
        """Register a new active signal for tracking.

        State must have status=PENDING and at least one entry plan.
        Persists to DB immediately for restart recovery.
        """
        if state.fingerprint in self._active:
            log_event(
                "signal_state_already_registered",
                fingerprint=state.fingerprint,
            )
            return

        state.status = SignalLifecycle.PENDING
        self._active[state.fingerprint] = state
        self._persist(state)
        log_event(
            "signal_state_registered",
            fingerprint=state.fingerprint,
            symbol=state.symbol,
            plans_count=len(state.entry_plans),
            expires_at=state.expires_at.isoformat(),
        )

    # ── Level tracking ───────────────────────────────────────────

    def mark_level_executed(self, base_fp: str, level_id: int) -> None:
        """Mark an entry plan level as executed.

        Transitions:
            PENDING → PARTIAL (first execution)
            PARTIAL stays PARTIAL (more pending)
            PARTIAL → COMPLETED (all done)
        """
        state = self._active.get(base_fp)
        if not state:
            return

        # Find and update the specific plan
        for plan in state.entry_plans:
            if plan.level_id == level_id:
                plan.status = "executed"
                break

        # Compute new state
        self._update_lifecycle(state)
        self._persist_plans(state)
        log_event(
            "signal_state_level_executed",
            fingerprint=base_fp,
            level_id=level_id,
            status=state.status.value,
        )

    def mark_level_cancelled(self, base_fp: str, level_id: int) -> None:
        """Mark an entry plan level as cancelled (e.g. risk guard rejected).

        May transition to COMPLETED if no pending plans remain.
        """
        state = self._active.get(base_fp)
        if not state:
            return

        for plan in state.entry_plans:
            if plan.level_id == level_id:
                plan.status = "cancelled"
                break

        self._update_lifecycle(state)
        self._persist_plans(state)
        log_event(
            "signal_state_level_cancelled",
            fingerprint=base_fp,
            level_id=level_id,
            status=state.status.value,
        )

    # ── Queries ──────────────────────────────────────────────────

    def get_pending_reentries(
        self,
    ) -> list[tuple[SignalState, EntryPlan]]:
        """Get (signal, plan) pairs where plan is still pending.

        Only returns from signals in PENDING or PARTIAL state.
        Skips expired signals (handled by expire_old).
        """
        result: list[tuple[SignalState, EntryPlan]] = []
        now = datetime.now(timezone.utc)

        for state in self._active.values():
            if state.status not in (
                SignalLifecycle.PENDING,
                SignalLifecycle.PARTIAL,
            ):
                continue
            if now > state.expires_at:
                continue  # Will be cleaned by expire_old

            for plan in state.entry_plans:
                if plan.status == "pending":
                    result.append((state, plan))

        return result

    def get_state(self, base_fp: str) -> SignalState | None:
        """Lookup signal state by base fingerprint."""
        return self._active.get(base_fp)

    # ── Expiry ───────────────────────────────────────────────────

    def expire_old(self) -> int:
        """Transition expired signals to EXPIRED status.

        Returns count of newly expired signals.
        """
        now = datetime.now(timezone.utc)
        expired_count = 0
        to_remove: list[str] = []

        for fp, state in self._active.items():
            if state.status in (
                SignalLifecycle.COMPLETED,
                SignalLifecycle.EXPIRED,
            ):
                to_remove.append(fp)
                continue

            if now > state.expires_at:
                # Cancel remaining pending plans
                for plan in state.entry_plans:
                    if plan.status == "pending":
                        plan.status = "cancelled"
                state.status = SignalLifecycle.EXPIRED
                self._persist_status(state)
                expired_count += 1
                to_remove.append(fp)
                log_event(
                    "signal_state_expired",
                    fingerprint=fp,
                    symbol=state.symbol,
                )

        # Remove completed/expired from active registry
        for fp in to_remove:
            self._active.pop(fp, None)

        return expired_count

    def cancel_all_pending(self, base_fp: str) -> int:
        """Cancel all pending plans for a signal (G6).

        Called when admin replies with close/secure_profit to stop
        RangeMonitor from placing more orders.

        Returns count of cancelled plans.
        """
        state = self._active.get(base_fp)
        if not state:
            return 0

        cancelled = 0
        for plan in state.entry_plans:
            if plan.status == "pending":
                plan.status = "cancelled"
                cancelled += 1

        if cancelled > 0:
            self._update_lifecycle(state)
            self._persist_plans(state)
            log_event(
                "signal_state_plans_cancelled",
                fingerprint=base_fp,
                cancelled_count=cancelled,
                reason="reply_action",
            )

        return cancelled

    def remove(self, base_fp: str) -> None:
        """Remove signal from tracking explicitly."""
        self._active.pop(base_fp, None)
        self._storage.delete_active_signal(base_fp)

    # ── Restart recovery ─────────────────────────────────────────

    def rebuild_from_db(self) -> int:
        """Rebuild in-memory registry from DB on startup.

        Loads signals with status IN ('pending', 'partial').
        Returns count of restored signals.
        """
        rows = self._storage.get_active_signals()
        count = 0
        for row in rows:
            try:
                state = self._deserialize_row(row)
                if state:
                    self._active[state.fingerprint] = state
                    count += 1
            except Exception as exc:
                log_event(
                    "signal_state_rebuild_error",
                    fingerprint=row.get("fingerprint", "?"),
                    error=str(exc),
                )

        if count > 0:
            log_event(
                "signal_state_rebuilt",
                restored_count=count,
            )
        return count

    # ── Internal helpers ─────────────────────────────────────────

    def _update_lifecycle(self, state: SignalState) -> None:
        """Recompute lifecycle status based on entry plan statuses."""
        pending = [p for p in state.entry_plans if p.status == "pending"]
        executed = [p for p in state.entry_plans if p.status == "executed"]

        if not pending:
            # All plans either executed or cancelled
            state.status = SignalLifecycle.COMPLETED
        elif executed:
            # At least one executed, some still pending
            state.status = SignalLifecycle.PARTIAL
        # else: still PENDING (no executions yet, some pending)

    def _persist(self, state: SignalState) -> None:
        """Full persist to DB."""
        self._storage.store_active_signal(
            fingerprint=state.fingerprint,
            symbol=state.symbol,
            side=state.side.value,
            entry_range=state.entry_range,
            sl=state.sl,
            tp=state.tp,
            source_chat_id=state.source_chat_id,
            source_message_id=state.source_message_id,
            channel_id=state.channel_id,
            entry_plans_json=self._serialize_plans(state.entry_plans),
            total_volume=state.total_volume,
            expires_at=state.expires_at.isoformat(),
        )

    def _persist_plans(self, state: SignalState) -> None:
        """Update only entry plans + status in DB."""
        self._storage.update_active_signal_plans(
            state.fingerprint,
            self._serialize_plans(state.entry_plans),
        )
        self._persist_status(state)

    def _persist_status(self, state: SignalState) -> None:
        """Update only status in DB."""
        self._storage.update_active_signal_status(
            state.fingerprint,
            state.status.value,
        )

    @staticmethod
    def _serialize_plans(plans: list[EntryPlan]) -> str:
        """Serialize entry plans to JSON."""
        return json.dumps([
            {
                "level": p.level,
                "order_kind": p.order_kind.value,
                "level_id": p.level_id,
                "label": p.label,
                "status": p.status,
            }
            for p in plans
        ])

    @staticmethod
    def _deserialize_row(row: dict) -> SignalState | None:
        """Deserialize a DB row into SignalState."""
        fp = row.get("fingerprint", "")
        if not fp:
            return None

        # Parse entry_plans JSON
        plans_raw = json.loads(row.get("entry_plans", "[]") or "[]")
        plans = [
            EntryPlan(
                level=p["level"],
                order_kind=OrderKind(p["order_kind"]),
                level_id=p["level_id"],
                label=p.get("label", ""),
                status=p.get("status", "pending"),
            )
            for p in plans_raw
        ]

        # Parse entry_range
        entry_range_raw = row.get("entry_range")
        entry_range = json.loads(entry_range_raw) if entry_range_raw else None

        # Parse tp
        tp_raw = row.get("tp", "[]") or "[]"
        tp = json.loads(tp_raw)

        # Parse expires_at
        expires_str = row.get("expires_at", "")
        try:
            expires_at = datetime.fromisoformat(expires_str)
        except (ValueError, TypeError):
            expires_at = datetime.now(timezone.utc)

        # Parse status
        status_str = row.get("status", "pending")
        try:
            status = SignalLifecycle(status_str)
        except ValueError:
            status = SignalLifecycle.PENDING

        return SignalState(
            fingerprint=fp,
            symbol=row.get("symbol", ""),
            side=Side(row.get("side", "BUY")),
            entry_range=entry_range,
            sl=row.get("sl"),
            tp=tp,
            source_chat_id=row.get("source_chat_id", ""),
            source_message_id=row.get("source_message_id", ""),
            channel_id=row.get("channel_id", ""),
            entry_plans=plans,
            total_volume=row.get("total_volume", 0.0),
            created_at=datetime.now(timezone.utc),  # approximation
            expires_at=expires_at,
            status=status,
        )
