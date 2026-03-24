"""
core/entry_strategy.py

Generate entry plans from signal + strategy config + live tick.

RESPONSIBILITIES (strict):
- Read signal + strategy config + live tick
- Output list[EntryPlan]
- NOTHING ELSE — no execution, no state, no side effects

NOT responsible for:
- Executing orders
- Tracking state
- Monitoring price

P9: Channel-Driven Strategy Architecture
"""

from __future__ import annotations

import math
from typing import Any

from core.models import (
    EntryPlan,
    OrderKind,
    ParsedSignal,
    Side,
)
from utils.logger import log_event
from utils.symbol_mapper import estimate_pip_size as _estimate_pip_size_by_symbol


class EntryStrategy:
    """Generate entry plans from a parsed signal.

    Strategy modes:
        single   — 1 signal → 1 order (current behavior, default)
        range    — 1 signal → N orders spread across entry_range
        scale_in — 1 initial + N-1 re-entry at stepped levels

    Volume split modes:
        equal      — total_volume / max_entries
        pyramid    — 50% / 30% / 20% (weighted toward first entry)
        risk_based — weighted by SL distance per entry level
    """

    def plan_entries(
        self,
        signal: ParsedSignal,
        strategy_config: dict[str, Any],
        bid: float,
        ask: float,
        point: float,
        tolerance_points: float = 5.0,
    ) -> list[EntryPlan]:
        """Generate entry plans based on strategy mode.

        Args:
            signal: Parsed signal with entry, entry_range, side, SL, TP.
            strategy_config: Channel strategy config from ChannelManager.
            bid: Current bid price.
            ask: Current ask price.
            point: Symbol point size (e.g. 0.01 for XAUUSD).
            tolerance_points: Market tolerance in points for MARKET detection.

        Returns:
            List of EntryPlan. Always at least 1 plan.
            For 'single' mode: exactly 1 plan.
        """
        mode = strategy_config.get("mode", "single")

        if mode == "range":
            plans = self._plan_range(signal, strategy_config, bid, ask, point, tolerance_points)
        elif mode == "scale_in":
            plans = self._plan_scale_in(signal, strategy_config, bid, ask, point, tolerance_points)
        else:
            plans = self._plan_single(signal, bid, ask, point, tolerance_points)

        log_event(
            "entry_strategy_planned",
            mode=mode,
            symbol=signal.symbol,
            plans_count=len(plans),
            levels=[p.level for p in plans],
        )
        return plans

    def split_volume(
        self,
        total_volume: float,
        plans: list[EntryPlan],
        sl: float | None,
        split_mode: str = "equal",
        lot_step: float = 0.01,
        lot_min: float = 0.01,
    ) -> list[float]:
        """Allocate volume across entry plans.

        Args:
            total_volume: Total volume (from RiskManager).
            plans: Entry plans to split volume across.
            sl: Stop loss price (needed for risk_based mode).
            split_mode: "equal", "pyramid", or "risk_based".
            lot_step: Broker lot step for rounding.
            lot_min: Broker minimum lot size.

        Returns:
            List of volumes, one per plan. Sum ≤ total_volume.
        """
        n = len(plans)
        if n == 0:
            return []
        if n == 1:
            return [total_volume]

        if split_mode == "per_entry":
            # Each plan gets the full calculated volume (no splitting)
            # Use case: FIXED_LOT=0.01, max_entries=3 → each gets 0.01
            volumes = [total_volume] * n
        elif split_mode == "pyramid":
            volumes = self._split_pyramid(total_volume, n)
        elif split_mode == "risk_based" and sl is not None:
            volumes = self._split_risk_based(total_volume, plans, sl)
        else:
            volumes = self._split_equal(total_volume, n)

        # Round to lot_step and enforce lot_min
        result = []
        for v in volumes:
            # round before floor to avoid IEEE 754 truncation
            # e.g. 0.02/0.01 = 1.9999... → round → 2.0 → floor → 2
            rounded = math.floor(round(v / lot_step, 10)) * lot_step
            rounded = max(lot_min, rounded)
            decimals = len(str(lot_step).rstrip("0").split(".")[-1])
            rounded = round(rounded, decimals)
            result.append(rounded)

        return result

    # ── Single mode ──────────────────────────────────────────────

    def _plan_single(
        self,
        signal: ParsedSignal,
        bid: float,
        ask: float,
        point: float,
        tolerance_points: float,
    ) -> list[EntryPlan]:
        """Single mode: 1 signal → 1 order.

        Identical to current system behavior.
        """
        entry = signal.entry
        order_kind = self._decide_order_kind(
            entry, signal.side, bid, ask, point, tolerance_points,
        )
        return [
            EntryPlan(
                level=entry if entry is not None else (ask if signal.side == Side.BUY else bid),
                order_kind=order_kind,
                level_id=0,
                label="initial",
            ),
        ]

    # ── Range mode ───────────────────────────────────────────────

    def _plan_range(
        self,
        signal: ParsedSignal,
        config: dict[str, Any],
        bid: float,
        ask: float,
        point: float,
        tolerance_points: float,
    ) -> list[EntryPlan]:
        """Range mode: spread N orders across entry_range.

        When reentry_step_pips > 0 (G9):
            P1 = zone edge (SELL: zone_low, BUY: zone_high)
            P2 = P1 ± 1×step, P3 = P1 ± 2×step, etc.

        When reentry_step_pips == 0 (legacy):
            Spread levels evenly across zone.

        Falls back to single mode if no entry_range available.
        """
        max_entries = config.get("max_entries", 1)

        if not signal.entry_range or len(signal.entry_range) < 2:
            # No range data — fall back to single
            return self._plan_single(signal, bid, ask, point, tolerance_points)

        low, high = signal.entry_range[0], signal.entry_range[1]
        max_entries = min(max_entries, 10)  # Hard cap: never more than 10

        if max_entries <= 1:
            return self._plan_single(signal, bid, ask, point, tolerance_points)

        # G9: Check if step_pips mode is active
        step_pips = config.get("reentry_step_pips", 0)
        if step_pips > 0:
            pip_size = _estimate_pip_size_by_symbol(signal.symbol)
            step_price = step_pips * pip_size

            if signal.side == Side.BUY:
                p1 = high  # BUY: start at zone_high (near market)
                levels = [p1 - i * step_price for i in range(max_entries)]
            else:
                p1 = low   # SELL: start at zone_low (near market)
                levels = [p1 + i * step_price for i in range(max_entries)]
        else:
            # Legacy: spread evenly across zone
            if max_entries == 2:
                levels = [high, low] if signal.side == Side.BUY else [low, high]
            else:
                step = (high - low) / (max_entries - 1) if max_entries > 1 else 0
                if signal.side == Side.BUY:
                    levels = [high - i * step for i in range(max_entries)]
                else:
                    levels = [low + i * step for i in range(max_entries)]

        # Build plans
        plans = []
        for idx, level in enumerate(levels):
            order_kind = self._decide_order_kind(
                level, signal.side, bid, ask, point, tolerance_points,
            )
            plans.append(EntryPlan(
                level=round(level, 5),
                order_kind=order_kind,
                level_id=idx,
                label="initial" if idx == 0 else f"range_{idx}",
            ))

        return plans

    # ── Scale-In mode ────────────────────────────────────────────

    def _plan_scale_in(
        self,
        signal: ParsedSignal,
        config: dict[str, Any],
        bid: float,
        ask: float,
        point: float,
        tolerance_points: float,
    ) -> list[EntryPlan]:
        """Scale-in mode: 1 initial + N-1 re-entries at stepped levels.

        BUY: initial at signal.entry, re-entries at lower prices
             (stepping deeper into buy zone).
        SELL: initial at signal.entry, re-entries at higher prices
              (stepping deeper into sell zone).

        Step size is controlled by reentry_step_pips.
        Falls back to single if step=0.
        """
        max_entries = min(config.get("max_entries", 1), 10)
        step_pips = config.get("reentry_step_pips", 0)

        if max_entries <= 1 or step_pips <= 0:
            return self._plan_single(signal, bid, ask, point, tolerance_points)

        pip_size = _estimate_pip_size_by_symbol(signal.symbol)
        step_price = step_pips * pip_size

        entry = signal.entry
        if entry is None:
            entry = ask if signal.side == Side.BUY else bid

        plans = []
        for idx in range(max_entries):
            if signal.side == Side.BUY:
                level = entry - (idx * step_price)
            else:
                level = entry + (idx * step_price)

            order_kind = self._decide_order_kind(
                level, signal.side, bid, ask, point, tolerance_points,
            )
            plans.append(EntryPlan(
                level=round(level, 5),
                order_kind=order_kind,
                level_id=idx,
                label="initial" if idx == 0 else f"reentry_{idx}",
            ))

        return plans

    # ── Volume split helpers ─────────────────────────────────────

    def _split_equal(self, total: float, n: int) -> list[float]:
        """Equal split: total / n."""
        return [total / n] * n

    def _split_pyramid(self, total: float, n: int) -> list[float]:
        """Pyramid split: weighted toward first entries.

        Weights: n, n-1, n-2, ..., 1
        Example n=3: weights [3, 2, 1] → 50%, 33%, 17%
        """
        weights = list(range(n, 0, -1))
        total_weight = sum(weights)
        return [(w / total_weight) * total for w in weights]

    def _split_risk_based(
        self,
        total: float,
        plans: list[EntryPlan],
        sl: float,
    ) -> list[float]:
        """Risk-based split: volume weighted by SL distance.

        Further from SL → larger volume (lower risk per pip).
        Closer to SL → smaller volume (higher risk per pip).

        Formula per entry:
            distance_i = |level_i - SL|
            weight_i = distance_i / sum(all distances)
            volume_i = total * weight_i
        """
        distances = [abs(p.level - sl) for p in plans]
        total_distance = sum(distances)
        if total_distance == 0:
            return self._split_equal(total, len(plans))
        return [(d / total_distance) * total for d in distances]

    # ── Order kind decision ──────────────────────────────────────

    def _decide_order_kind(
        self,
        entry: float | None,
        side: Side,
        bid: float,
        ask: float,
        point: float,
        tolerance_points: float,
    ) -> OrderKind:
        """Decide order kind for a single entry level.

        Same logic as OrderBuilder.decide_order_type() but returns
        only the OrderKind enum (no TradeDecision wrapping).
        """
        if entry is None:
            return OrderKind.MARKET

        tolerance = tolerance_points * point

        if side == Side.BUY:
            ref = ask
            if abs(entry - ref) <= tolerance:
                return OrderKind.MARKET
            if entry < ref:
                return OrderKind.BUY_LIMIT
            return OrderKind.BUY_STOP
        else:
            ref = bid
            if abs(entry - ref) <= tolerance:
                return OrderKind.MARKET
            if entry > ref:
                return OrderKind.SELL_LIMIT
            return OrderKind.SELL_STOP

