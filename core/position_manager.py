"""
core/position_manager.py

Background position manager for open trades.

Runs a poll loop checking open positions against configurable rules:
  - Breakeven: move SL to entry + lock when profit >= trigger
  - Trailing stop: trail SL at fixed pip distance from current price
  - Partial close: close a percentage of volume at TP1
  - P10: Group management — trail/BE/close at GROUP level

All features default to 0 = disabled. Only active in live mode.

P10: PositionManager is now group-aware. Every signal creates an
OrderGroup (group of 1 or N). Positions in a group are managed
collectively (group trailing, selective close, auto BE).
Positions NOT in any group use legacy per-position management.
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from utils.logger import log_event
from utils.symbol_mapper import estimate_pip_size
from core.models import GroupStatus, OrderGroup, Side

if TYPE_CHECKING:
    from core.trade_executor import TradeExecutor
    from config.settings import Settings
    from core.channel_manager import ChannelManager
    from core.storage import Storage
    from core.telegram_alerter import TelegramAlerter


class PositionManager:
    """Monitor and manage open positions for breakeven and trailing stop.

    Runs as a background asyncio task, polling MT5 positions
    every POSITION_MANAGER_POLL_SECONDS.

    Per-channel rules: if a position's ticket is mapped to a channel_id,
    uses channel-specific rules from ChannelManager. Falls back to global
    settings for unknown positions (pre-v0.6.0 or unmapped).

    P10: Group-aware management. Positions in an OrderGroup are managed
    collectively (group trailing, group BE, selective close). Positions
    not in any group use legacy per-position rules.
    """

    def __init__(
        self,
        executor: TradeExecutor,
        settings: Settings,
        channel_manager: ChannelManager | None = None,
        storage: Storage | None = None,
        alerter: TelegramAlerter | None = None,
    ) -> None:
        self._executor = executor
        self._storage = storage
        self._alerter = alerter

        # Global defaults — used as fallback when no channel config exists
        self._breakeven_trigger_pips: float = settings.safety.breakeven_trigger_pips
        self._breakeven_lock_pips: float = settings.safety.breakeven_lock_pips
        self._trailing_stop_pips: float = settings.safety.trailing_stop_pips
        self._partial_close_percent: int = settings.safety.partial_close_percent
        self._poll_seconds: int = settings.safety.position_manager_poll_seconds
        self._magic: int = settings.execution.bot_magic_number

        # Per-channel support
        self._channel_manager = channel_manager
        self._ticket_to_channel: dict[int, str] = {}

        # Track which positions we've already partially closed
        self._partially_closed: set[int] = set()
        # Track which positions we've already moved to breakeven
        self._breakeven_applied: set[int] = set()

        self._poll_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

        # ── P10: Group tracking ──────────────────────────────────
        # All signal order groups, keyed by base fingerprint
        self._groups: dict[str, OrderGroup] = {}
        # Reverse lookup: ticket → fingerprint (for fast routing)
        self._ticket_to_group: dict[int, str] = {}

        # Alert throttle: (ticket, event_type) -> last_alert_epoch
        self._last_alert_time: dict[tuple[int, str], float] = {}
        self._ALERT_COOLDOWN = 60  # seconds per (ticket, event_type)
        self._TRAILING_ALERT_MIN_PIPS = 5.0  # only alert if SL moved >= 5 pips

        # P10g: Restore groups from DB on startup
        # NOTE: Do NOT call _restore_groups_from_db() here — MT5 is not yet
        # initialized at component init time. Call restore_groups() explicitly
        # from Bot.run() AFTER executor.init_mt5().
        self._last_trailing_sl: dict[int, float] = {}  # ticket -> last alerted SL

    def restore_groups(self) -> None:
        """Restore groups from DB. MUST be called after MT5 init."""
        self._restore_groups_from_db()

    def _restore_groups_from_db(self) -> None:
        """Restore active groups from DB after bot restart.

        Reads all active signal groups from storage, reconstructs
        OrderGroup objects, and populates _groups + _ticket_to_group.
        Skips groups where ALL tickets are already closed in MT5.
        """
        if not self._storage:
            return

        try:
            rows = self._storage.get_active_groups()
        except Exception as e:
            log_event("group_restore_error", error=str(e))
            return

        if not rows:
            return

        try:
            import MetaTrader5 as mt5
        except ImportError:
            return

        restored = 0
        stale = 0

        for row in rows:
            fp = row["fingerprint"]
            tickets = row.get("tickets", [])

            # Verify at least one ticket is still open (position or pending order)
            has_open = False
            for ticket in tickets:
                positions = mt5.positions_get(ticket=ticket)
                if positions and len(positions) > 0:
                    has_open = True
                    break
                # Also check pending orders (LIMIT/STOP not yet filled)
                orders = mt5.orders_get(ticket=ticket)
                if orders and len(orders) > 0:
                    has_open = True
                    break

            if not has_open:
                # All tickets closed — mark as completed
                stale += 1
                try:
                    self._storage.complete_group_db(fp)
                except Exception:
                    pass
                continue

            # Reconstruct OrderGroup
            side_str = row.get("side", "BUY").upper()
            side = Side.BUY if side_str == "BUY" else Side.SELL

            group = OrderGroup(
                fingerprint=fp,
                symbol=row["symbol"],
                side=side,
                channel_id=row["channel_id"],
                source_message_id=row.get("source_message_id", ""),
                tickets=tickets,
                entry_prices=row.get("entry_prices", {}),
                zone_low=row.get("zone_low"),
                zone_high=row.get("zone_high"),
                signal_sl=row.get("signal_sl"),
                signal_tp=row.get("signal_tp", []),
                sl_mode=row.get("sl_mode", "signal"),
                sl_max_pips_from_zone=row.get("sl_max_pips_from_zone", 50.0),
                group_trailing_pips=row.get("group_trailing_pips", 0.0),
                group_be_on_partial_close=row.get("group_be_on_partial", False),
                reply_close_strategy=row.get("reply_close_strategy", "all"),
                current_group_sl=row.get("current_group_sl"),
                status=GroupStatus.ACTIVE,
            )

            self._groups[fp] = group
            for ticket in tickets:
                self._ticket_to_group[ticket] = fp
                self.register_ticket(ticket, group.channel_id)

            restored += 1

        if restored > 0 or stale > 0:
            log_event(
                "groups_restored",
                restored=restored,
                stale_completed=stale,
            )

    @property
    def is_enabled(self) -> bool:
        """True if at least one position management feature is configured.

        Checks both global settings AND channel-specific rules so that
        channel overrides (e.g., breakeven_lock_pips) are not silently ignored.
        """
        # Global settings
        if (
            self._breakeven_trigger_pips > 0
            or self._trailing_stop_pips > 0
            or self._partial_close_percent > 0
        ):
            return True

        # Channel-level overrides via ChannelManager
        if self._channel_manager:
            for ch_id in self._channel_manager._channels:
                rules = self._channel_manager.get_rules(ch_id)
                if rules and (
                    rules.get("breakeven_lock_pips", 0) > 0
                    or rules.get("trailing_stop_pips", 0) > 0
                    or rules.get("partial_close_percent", 0) > 0
                ):
                    return True

        return False

    async def start(self) -> None:
        """Start the background poll loop."""
        if not self.is_enabled:
            log_event("position_manager_disabled")
            return

        # Rebuild ticket→channel cache from DB on startup
        self._rebuild_cache()

        self._poll_task = asyncio.create_task(self._poll_loop())
        self._cleanup_task = asyncio.create_task(self._daily_cleanup_loop())
        log_event(
            "position_manager_started",
            breakeven_trigger_pips=self._breakeven_trigger_pips,
            breakeven_lock_pips=self._breakeven_lock_pips,
            trailing_stop_pips=self._trailing_stop_pips,
            partial_close_percent=self._partial_close_percent,
            poll_seconds=self._poll_seconds,
            cached_tickets=len(self._ticket_to_channel),
        )

    async def stop(self) -> None:
        """Stop the background poll loop."""
        for task in (self._poll_task, getattr(self, '_cleanup_task', None)):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._poll_task = None
        self._cleanup_task = None
        log_event("position_manager_stopped")

    async def _poll_loop(self) -> None:
        """Poll MT5 positions and apply management rules."""
        while True:
            try:
                await asyncio.sleep(self._poll_seconds)
                self._check_positions()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("position_manager_error", error=str(exc))

    # ── Cache Management ─────────────────────────────────────────

    def register_ticket(self, ticket: int, channel_id: str) -> None:
        """Register a ticket→channel mapping after order execution.

        Called from the pipeline after successful order execution.
        """
        if ticket and channel_id:
            self._ticket_to_channel[ticket] = channel_id

    def _rebuild_cache(self) -> None:
        """Rebuild ticket→channel cache from DB on startup.

        Ensures positions opened before restart retain their channel context.
        """
        if not self._storage:
            return
        try:
            mapping = self._storage.get_open_tickets()
            self._ticket_to_channel.update(mapping)
            log_event(
                "position_manager_cache_rebuilt",
                tickets=len(mapping),
            )
        except Exception as exc:
            log_event(
                "position_manager_cache_error",
                error=str(exc),
            )

    def _get_rules_for_ticket(self, ticket: int) -> dict:
        """Get position management rules for a specific ticket.

        Looks up channel_id from cache, then gets channel-specific rules.
        Falls back to global defaults if no channel mapping or no ChannelManager.
        """
        defaults = {
            "breakeven_trigger_pips": self._breakeven_trigger_pips,
            "breakeven_lock_pips": self._breakeven_lock_pips,
            "trailing_stop_pips": self._trailing_stop_pips,
            "partial_close_percent": self._partial_close_percent,
        }

        if not self._channel_manager:
            return defaults

        channel_id = self._ticket_to_channel.get(ticket)
        if not channel_id:
            return defaults

        channel_rules = self._channel_manager.get_rules(channel_id)
        # Merge: channel rules override defaults
        merged = dict(defaults)
        for key in defaults:
            if key in channel_rules:
                merged[key] = channel_rules[key]
        return merged

    def _check_positions(self) -> None:
        """Check all open positions and apply management rules.

        P10: Routes positions to group management or individual management.
        Group positions are managed collectively (once per group per cycle).
        Non-group positions use legacy per-position rules.
        """
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return

        positions = mt5.positions_get()
        if positions is None:
            return

        # Only manage positions opened by this bot
        bot_positions = [p for p in positions if p.magic == self._magic]
        open_tickets = {p.ticket for p in bot_positions}


        # ── P10: Process groups first (once per group) ───────────
        processed_groups: set[str] = set()

        for pos in bot_positions:
            fp = self._ticket_to_group.get(pos.ticket)
            if fp and fp not in processed_groups:
                group = self._groups.get(fp)
                if group and group.status == GroupStatus.ACTIVE:
                    self._manage_group(mt5, group, bot_positions)
                    processed_groups.add(fp)

        # ── Individual management for non-group positions ────────
        for pos in bot_positions:
            if pos.ticket in self._ticket_to_group:
                continue  # Managed by group — skip individual
            self._manage_individual(mt5, pos)

        # ── P10: Detect completed groups (all tickets closed) ────
        # Must also check pending orders — tickets may be LIMIT/STOP
        # that haven't filled yet. Only complete group when ticket is
        # in NEITHER positions_get() NOR orders_get().
        pending_orders = mt5.orders_get()
        pending_tickets: set[int] = set()
        if pending_orders:
            pending_tickets = {o.ticket for o in pending_orders if o.magic == self._magic}

        all_known_tickets = open_tickets | pending_tickets

        for fp in list(self._groups):
            group = self._groups[fp]
            if group.status != GroupStatus.ACTIVE:
                continue
            group_alive = [t for t in group.tickets if t in all_known_tickets]
            if not group_alive:
                self._complete_group(group)

        # Cleanup is scheduled daily at 1 AM — see _daily_cleanup_loop()

    # ── Daily Cleanup (memory leak prevention) ────────────────────

    _CLEANUP_HOUR = 1  # 1 AM local time (UTC+7)
    _TZ_LOCAL = timezone(timedelta(hours=7))
    _GROUP_COMPLETED_TTL = 3600  # 1 hour before removing completed groups

    async def _daily_cleanup_loop(self) -> None:
        """Run full cleanup once daily at 1 AM (UTC+7)."""
        while True:
            try:
                now = datetime.now(self._TZ_LOCAL)
                target = now.replace(
                    hour=self._CLEANUP_HOUR, minute=0, second=0, microsecond=0,
                )
                if target <= now:
                    target += timedelta(days=1)
                wait_secs = (target - now).total_seconds()
                log_event(
                    "position_manager_cleanup_scheduled",
                    next_run=target.isoformat(),
                    wait_hours=round(wait_secs / 3600, 1),
                )
                await asyncio.sleep(wait_secs)
                self._run_full_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("position_manager_cleanup_error", error=str(exc))
                await asyncio.sleep(60)  # retry after 1 min on error

    def _run_full_cleanup(self) -> None:
        """Full sweep: prune all tracking dicts + completed groups."""
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return
        positions = mt5.positions_get()
        if positions is None:
            open_tickets: set[int] = set()
        else:
            open_tickets = {p.ticket for p in positions if p.magic == self._magic}
        self._cleanup_closed_tickets(open_tickets)
        log_event(
            "position_manager_cleanup_done",
            open_tickets=len(open_tickets),
            remaining_tracked=len(self._ticket_to_channel),
            remaining_groups=len(self._groups),
        )

    def _cleanup_closed_tickets(self, open_tickets: set[int]) -> None:
        """Remove entries for closed positions from all tracking dicts.

        Called once daily at 1 AM by _daily_cleanup_loop().
        Prevents unbounded memory growth over weeks of operation.
        """
        # Prune ticket-keyed dicts
        for ticket in list(self._ticket_to_channel):
            if ticket not in open_tickets:
                self._ticket_to_channel.pop(ticket, None)

        self._breakeven_applied -= self._breakeven_applied - open_tickets
        self._partially_closed -= self._partially_closed - open_tickets

        for ticket in list(self._last_trailing_sl):
            if ticket not in open_tickets:
                self._last_trailing_sl.pop(ticket, None)

        # Prune alert throttle: remove entries for closed tickets
        for key in list(self._last_alert_time):
            ticket, _ = key
            if ticket not in open_tickets:
                self._last_alert_time.pop(key, None)

        # Prune completed groups after TTL
        now = _time.time()
        for fp in list(self._groups):
            group = self._groups[fp]
            if group.status == GroupStatus.COMPLETED:
                # Use a simple heuristic: if no tickets are open, remove after TTL
                age = now - self._last_alert_time.get(
                    (group.tickets[0] if group.tickets else 0, "group_completed"), 0.0,
                )
                if age > self._GROUP_COMPLETED_TTL:
                    self._groups.pop(fp, None)

    def _manage_individual(self, mt5, pos) -> None:
        """Legacy per-position management: breakeven, trailing, partial close.

        Used for positions NOT in any group (e.g., pre-P10 orders,
        or channels with mode=single and group_trailing_pips=0).
        """
        symbol_info = mt5.symbol_info(pos.symbol)
        if not symbol_info or symbol_info.point <= 0:
            return

        point = symbol_info.point
        digits = symbol_info.digits
        pip_size = estimate_pip_size(pos.symbol)

        # Current profit in pips
        if pos.type == 0:  # BUY
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                return
            current_price = tick.bid
            profit_pips = (current_price - pos.price_open) / pip_size
        elif pos.type == 1:  # SELL
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                return
            current_price = tick.ask
            profit_pips = (pos.price_open - current_price) / pip_size
        else:
            return

        # Get per-channel rules for this position
        rules = self._get_rules_for_ticket(pos.ticket)


        # Breakeven
        be_trigger = rules["breakeven_trigger_pips"]
        be_lock = rules["breakeven_lock_pips"]
        if be_trigger > 0:
            self._apply_breakeven(
                mt5, pos, profit_pips, pip_size, point, digits,
                trigger_pips=be_trigger, lock_pips=be_lock,
            )

        # Trailing stop
        trail_pips = rules["trailing_stop_pips"]
        if trail_pips > 0:
            self._apply_trailing_stop(
                mt5, pos, current_price, profit_pips, pip_size, point, digits,
                trail_pips=trail_pips,
            )

        # Partial close
        pc_percent = rules["partial_close_percent"]
        if pc_percent > 0:
            self._apply_partial_close(
                mt5, pos, profit_pips, symbol_info,
                close_percent=pc_percent,
            )

    def _apply_breakeven(
        self, mt5, pos, profit_pips: float,
        pip_size: float, point: float, digits: int,
        trigger_pips: float = 0, lock_pips: float = 0,
    ) -> None:
        """Move SL to entry + lock pips when profit reaches trigger."""
        if pos.ticket in self._breakeven_applied:
            return

        if profit_pips < trigger_pips:
            return

        # Calculate breakeven SL
        lock_distance = lock_pips * pip_size

        if pos.type == 0:  # BUY
            new_sl = pos.price_open + lock_distance
            # Only move if new SL is better than current
            if pos.sl > 0 and new_sl <= pos.sl:
                return
        else:  # SELL
            new_sl = pos.price_open - lock_distance
            if pos.sl > 0 and new_sl >= pos.sl:
                return

        new_sl = round(new_sl, digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": pos.tp,
        }

        result = mt5.order_send(request)
        if result and result.retcode in (10008, 10009):
            self._breakeven_applied.add(pos.ticket)
            log_event(
                "breakeven_applied",
                ticket=pos.ticket,
                symbol=pos.symbol,
                new_sl=new_sl,
                profit_pips=round(profit_pips, 1),
            )
            self._send_position_alert(
                pos.ticket, "breakeven_alert", pos.symbol,
                f"🔒 **Breakeven** on `{pos.symbol}` #{pos.ticket}\n"
                f"SL moved to {new_sl} (+{lock_pips}p lock)",
            )
        else:
            retcode = result.retcode if result else -1
            log_event(
                "breakeven_failed",
                ticket=pos.ticket,
                symbol=pos.symbol,
                retcode=retcode,
            )

    def _apply_trailing_stop(
        self, mt5, pos, current_price: float,
        profit_pips: float, pip_size: float, point: float, digits: int,
        trail_pips: float = 0,
    ) -> None:
        """Trail SL at fixed pip distance from current price."""
        # Only trail when in profit
        if profit_pips <= 0:
            return

        trail_distance = trail_pips * pip_size

        if pos.type == 0:  # BUY
            new_sl = current_price - trail_distance
            # Only move SL up, never down
            if pos.sl > 0 and new_sl <= pos.sl:
                return
            # Don't trail below entry
            if new_sl < pos.price_open:
                return
        else:  # SELL
            new_sl = current_price + trail_distance
            # Only move SL down, never up
            if pos.sl > 0 and new_sl >= pos.sl:
                return
            # Don't trail above entry
            if new_sl > pos.price_open:
                return

        new_sl = round(new_sl, digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": pos.tp,
        }

        result = mt5.order_send(request)
        if result and result.retcode in (10008, 10009):
            log_event(
                "trailing_stop_moved",
                ticket=pos.ticket,
                symbol=pos.symbol,
                new_sl=new_sl,
                profit_pips=round(profit_pips, 1),
            )
            # Only alert if SL moved significantly
            pip_size = estimate_pip_size(pos.symbol)
            last_sl = self._last_trailing_sl.get(pos.ticket)
            if last_sl is None or abs(new_sl - last_sl) / pip_size >= self._TRAILING_ALERT_MIN_PIPS:
                self._last_trailing_sl[pos.ticket] = new_sl
                self._send_position_alert(
                    pos.ticket, "trailing_alert", pos.symbol,
                    f"📐 **Trailing SL** on `{pos.symbol}` #{pos.ticket}\n"
                    f"SL → {new_sl} (profit: {round(profit_pips, 1)}p)",
                )

    def _apply_partial_close(
        self, mt5, pos, profit_pips: float, symbol_info,
        close_percent: int = 0,
    ) -> None:
        """Close a percentage of volume when first TP is reached."""
        if pos.ticket in self._partially_closed:
            return

        # Only partial close when position has a TP set and is in profit
        if pos.tp <= 0 or profit_pips <= 0:
            return

        # Check if price has reached TP zone (within 1 pip)
        tp_distance_pips = abs(pos.tp - (mt5.symbol_info_tick(pos.symbol).bid
                              if pos.type == 0 else
                              mt5.symbol_info_tick(pos.symbol).ask))
        pip_size = estimate_pip_size(pos.symbol)
        if tp_distance_pips / pip_size > 1.0:
            # Not near TP yet
            return

        # Calculate partial volume
        close_volume = pos.volume * (close_percent / 100.0)
        close_volume = max(symbol_info.volume_min, close_volume)
        close_volume = round(
            close_volume / symbol_info.volume_step
        ) * symbol_info.volume_step
        close_volume = round(close_volume, 2)

        if close_volume <= 0:
            return

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": close_volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "deviation": 20,
            "magic": self._magic,
            "comment": f"partial_close:{pos.ticket}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        tick = mt5.symbol_info_tick(pos.symbol)
        if tick:
            request["price"] = tick.bid if pos.type == 0 else tick.ask

        result = mt5.order_send(request)
        if result and result.retcode in (10008, 10009, 10010):
            self._partially_closed.add(pos.ticket)
            log_event(
                "partial_close_executed",
                ticket=pos.ticket,
                symbol=pos.symbol,
                closed_volume=close_volume,
                remaining_volume=round(pos.volume - close_volume, 2),
                percent=close_percent,
            )
            self._send_position_alert(
                pos.ticket, "partial_close_alert", pos.symbol,
                f"✂️ **Partial Close** on `{pos.symbol}` #{pos.ticket}\n"
                f"Closed {close_volume} lots ({close_percent}%)",
            )
        else:
            retcode = result.retcode if result else -1
            log_event(
                "partial_close_failed",
                ticket=pos.ticket,
                symbol=pos.symbol,
                retcode=retcode,
            )

    # ── P10: Group Management ─────────────────────────────────────

    def register_group(
        self,
        fingerprint: str,
        symbol: str,
        side: Side,
        channel_id: str,
        source_message_id: str,
        tickets: list[int],
        entry_prices: dict[int, float],
        zone_low: float | None = None,
        zone_high: float | None = None,
        signal_sl: float | None = None,
        signal_tp: list[float] | None = None,
        rules: dict | None = None,
    ) -> None:
        """Register an order group after pipeline execution.

        Called by pipeline for EVERY signal (single mode = group of 1).
        Config is snapshot from channel rules at registration time.

        Args:
            fingerprint: Base fingerprint from parser.
            symbol: Trading symbol (e.g. "XAUUSD").
            side: BUY or SELL.
            channel_id: Telegram chat_id string.
            source_message_id: Telegram message_id for reply lookup.
            tickets: List of successfully executed MT5 ticket IDs.
            entry_prices: Mapping of ticket → entry price.
            zone_low: Lowest entry in zone (None if single).
            zone_high: Highest entry in zone (None if single).
            signal_sl: Original SL from signal text.
            signal_tp: TP levels from signal text.
            rules: Channel rules dict (from channel_manager.get_rules).
        """
        if not tickets:
            return

        if fingerprint in self._groups:
            log_event(
                "group_already_registered",
                fingerprint=fingerprint,
            )
            return

        rules = rules or {}

        group = OrderGroup(
            fingerprint=fingerprint,
            symbol=symbol,
            side=side,
            channel_id=channel_id,
            source_message_id=source_message_id,
            zone_low=zone_low,
            zone_high=zone_high,
            signal_sl=signal_sl,
            signal_tp=signal_tp or [],
            tickets=list(tickets),
            entry_prices=dict(entry_prices),
            # Config snapshot
            sl_mode=rules.get("sl_mode", "signal"),
            sl_max_pips_from_zone=float(rules.get("sl_max_pips_from_zone", 50.0)),
            group_trailing_pips=float(rules.get("group_trailing_pips", 0.0)),
            group_be_on_partial_close=bool(rules.get("group_be_on_partial_close", False)),
            reply_close_strategy=rules.get("reply_close_strategy", "all"),
        )

        self._groups[fingerprint] = group
        for ticket in tickets:
            self._ticket_to_group[ticket] = fingerprint
            # Also register ticket→channel for per-position fallback
            self.register_ticket(ticket, channel_id)

        log_event(
            "group_registered",
            fingerprint=fingerprint,
            symbol=symbol,
            side=side.value if isinstance(side, Side) else side,
            tickets=tickets,
            group_size=len(tickets),
            sl_mode=group.sl_mode,
            group_trailing_pips=group.group_trailing_pips,
            reply_close_strategy=group.reply_close_strategy,
        )

        # P10g: Persist group to DB for restart recovery
        if self._storage:
            try:
                self._storage.store_group(
                    fingerprint=fingerprint,
                    symbol=symbol,
                    side=side.value if isinstance(side, Side) else side,
                    channel_id=channel_id,
                    source_message_id=source_message_id,
                    tickets=tickets,
                    entry_prices=entry_prices,
                    zone_low=zone_low,
                    zone_high=zone_high,
                    signal_sl=signal_sl,
                    signal_tp=signal_tp,
                    sl_mode=group.sl_mode,
                    sl_max_pips_from_zone=group.sl_max_pips_from_zone,
                    group_trailing_pips=group.group_trailing_pips,
                    group_be_on_partial=group.group_be_on_partial_close,
                    reply_close_strategy=group.reply_close_strategy,
                )
            except Exception as e:
                log_event("group_db_store_error", fingerprint=fingerprint, error=str(e))

    def add_order_to_group(
        self, fingerprint: str, ticket: int, entry_price: float,
    ) -> None:
        """Add a re-entry order to an existing group.

        Called by RangeMonitor when a deferred entry plan fills.
        """
        group = self._groups.get(fingerprint)
        if not group:
            log_event(
                "group_add_order_not_found",
                fingerprint=fingerprint,
                ticket=ticket,
            )
            return

        if ticket in group.tickets:
            return  # Already in group

        group.tickets.append(ticket)
        group.entry_prices[ticket] = entry_price
        self._ticket_to_group[ticket] = fingerprint
        self.register_ticket(ticket, group.channel_id)

        # Resurrect group if it was completed (e.g. L0 pending expired, but L1 triggered later)
        if group.status == GroupStatus.COMPLETED:
            group.status = GroupStatus.ACTIVE
            if self._storage:
                try:
                    self._storage.reactivate_group_db(fingerprint)
                except Exception as e:
                    log_event("group_db_reactivate_error", fingerprint=fingerprint, error=str(e))
            log_event(
                "group_resurrected",
                fingerprint=fingerprint,
                ticket=ticket,
            )

        log_event(
            "group_order_added",
            fingerprint=fingerprint,
            ticket=ticket,
            entry_price=entry_price,
            group_size=len(group.tickets),
        )

        # P10g: Update DB with new ticket
        if self._storage:
            try:
                self._storage.update_group_tickets(
                    fingerprint, group.tickets, group.entry_prices,
                )
            except Exception as e:
                log_event("group_db_update_error", fingerprint=fingerprint, error=str(e))

    def _manage_group(self, mt5, group: OrderGroup, bot_positions) -> None:
        """Manage an active group: group trailing SL, zone SL.

        Calculates a unified SL for the entire group, then applies
        it to all open tickets. SL only moves favorably (up for BUY,
        down for SELL).

        If group_trailing_pips=0, falls back to individual per-position
        management (BE/trailing/partial close per ticket).
        """
        # If no group-level features enabled, use individual management
        if group.group_trailing_pips <= 0:
            for pos in bot_positions:
                if pos.ticket in group.tickets:
                    self._manage_individual(mt5, pos)
            return

        # ── Get symbol info ──────────────────────────────────────
        symbol_info = mt5.symbol_info(group.symbol)
        if not symbol_info or symbol_info.point <= 0:
            return

        point = symbol_info.point
        digits = symbol_info.digits
        pip_size = estimate_pip_size(group.symbol)

        # ── Get current price ────────────────────────────────────
        tick = mt5.symbol_info_tick(group.symbol)
        if not tick:
            return

        is_buy = group.side == Side.BUY or (
            isinstance(group.side, str) and group.side.upper() == "BUY"
        )
        current_price = tick.bid if is_buy else tick.ask

        # ── Calculate new group SL ───────────────────────────────
        new_sl = self._calculate_group_sl(group, current_price, pip_size, is_buy)
        if new_sl is None:
            return

        new_sl = round(new_sl, digits)

        # ── Only move SL if favorable ────────────────────────────
        current_sl = group.current_group_sl
        if current_sl is not None:
            if is_buy and new_sl <= current_sl:
                return  # BUY: don't move SL down
            if not is_buy and new_sl >= current_sl:
                return  # SELL: don't move SL up

        # ── Apply SL to all open tickets in group ────────────────
        group_tickets_open = [
            pos for pos in bot_positions if pos.ticket in group.tickets
        ]
        if not group_tickets_open:
            return

        self._modify_group_sl(mt5, group, new_sl, group_tickets_open, digits)

    def _calculate_group_sl(
        self,
        group: OrderGroup,
        current_price: float,
        pip_size: float,
        is_buy: bool,
    ) -> float | None:
        """Calculate the best SL for the group.

        Considers:
        1. Zone SL: zone_low - N pips (BUY) or zone_high + N pips (SELL)
        2. Trail SL: current_price - trail_pips (BUY) or + trail_pips (SELL)
        3. Current SL: don't move backwards

        Returns the BEST SL (most favorable for trader):
        - BUY: max(zone_sl, trail_sl, current_sl) — higher is better
        - SELL: min(zone_sl, trail_sl, current_sl) — lower is better

        Returns None if no valid SL can be calculated.
        """
        candidates: list[float] = []

        # 1. Zone SL (base protection)
        if group.sl_mode == "zone" and group.zone_low is not None and group.zone_high is not None:
            sl_distance = group.sl_max_pips_from_zone * pip_size
            if is_buy:
                zone_sl = group.zone_low - sl_distance
            else:
                zone_sl = group.zone_high + sl_distance
            candidates.append(zone_sl)

        # 2. Signal SL (fallback if sl_mode=signal)
        if group.sl_mode == "signal" and group.signal_sl is not None:
            candidates.append(group.signal_sl)

        # 3. Fixed mode: lowest entry - N pips
        if group.sl_mode == "fixed" and group.entry_prices:
            entries = list(group.entry_prices.values())
            if is_buy:
                fixed_sl = min(entries) - group.sl_max_pips_from_zone * pip_size
            else:
                fixed_sl = max(entries) + group.sl_max_pips_from_zone * pip_size
            candidates.append(fixed_sl)

        # 4. Trail SL (dynamic, moves with price)
        if group.group_trailing_pips > 0:
            trail_distance = group.group_trailing_pips * pip_size
            if is_buy:
                trail_sl = current_price - trail_distance
            else:
                trail_sl = current_price + trail_distance
            candidates.append(trail_sl)

        # 5. Current SL (never go backwards)
        if group.current_group_sl is not None:
            candidates.append(group.current_group_sl)

        if not candidates:
            return None

        # Pick best: BUY = max (tightest protection), SELL = min
        if is_buy:
            return max(candidates)
        else:
            return min(candidates)

    def _modify_group_sl(
        self,
        mt5,
        group: OrderGroup,
        new_sl: float,
        open_positions: list,
        digits: int,
    ) -> None:
        """Apply a new SL to ALL open tickets in a group.

        Sends MT5 TRADE_ACTION_SLTP for each position.
        Updates group.current_group_sl on success.
        """
        success_count = 0
        for pos in open_positions:
            # Skip if position already has this SL (within 1 point tolerance)
            if abs(pos.sl - new_sl) < mt5.symbol_info(pos.symbol).point:
                success_count += 1
                continue

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "sl": new_sl,
                "tp": pos.tp,
            }

            result = mt5.order_send(request)
            if result and result.retcode in (10008, 10009):
                success_count += 1
                log_event(
                    "group_sl_modified",
                    fingerprint=group.fingerprint,
                    ticket=pos.ticket,
                    new_sl=new_sl,
                )
            else:
                retcode = result.retcode if result else -1
                log_event(
                    "group_sl_modify_failed",
                    fingerprint=group.fingerprint,
                    ticket=pos.ticket,
                    new_sl=new_sl,
                    retcode=retcode,
                )

        if success_count > 0:
            old_sl = group.current_group_sl
            group.current_group_sl = new_sl

            # P10g: Persist SL to DB
            if self._storage:
                try:
                    self._storage.update_group_sl(group.fingerprint, new_sl)
                except Exception:
                    pass  # Non-critical, in-memory state is authoritative

            # Alert on significant SL movement
            pip_size = estimate_pip_size(group.symbol)
            if old_sl is None or abs(new_sl - old_sl) / pip_size >= self._TRAILING_ALERT_MIN_PIPS:
                self._send_group_alert(
                    group,
                    "group_sl_moved",
                    f"📐 **Group SL** `{group.symbol}` "
                    f"({success_count}/{len(open_positions)} orders)\n"
                    f"SL → {new_sl}",
                )

    def _complete_group(self, group: OrderGroup) -> None:
        """Mark a group as completed when all tickets are closed.

        Logs final state and cleans up reverse lookups.
        Does NOT remove from _groups dict (kept for reply/query until restart).
        """
        group.status = GroupStatus.COMPLETED

        log_event(
            "group_completed",
            fingerprint=group.fingerprint,
            symbol=group.symbol,
            side=group.side.value if isinstance(group.side, Side) else group.side,
            total_orders=len(group.tickets),
        )

        # Clean up reverse lookup
        for ticket in group.tickets:
            self._ticket_to_group.pop(ticket, None)

        # Send completion alert
        self._send_group_alert(
            group,
            "group_completed",
            f"📊 **Group completed** `{group.symbol}`\n"
            f"Orders: {len(group.tickets)} | "
            f"FP: {group.fingerprint[:8]}",
        )

        # P10g: Mark completed in DB
        if self._storage:
            try:
                self._storage.complete_group_db(group.fingerprint)
            except Exception as e:
                log_event("group_db_complete_error", fingerprint=group.fingerprint, error=str(e))

    # ── P10f: Reply Group Actions ────────────────────────────────

    def close_selective_entry(
        self, fingerprint: str, reply_executor=None, dry_run: bool = False,
    ) -> dict | None:
        """Close ONE order from a group based on reply_close_strategy.

        Strategies:
        - "highest_entry": BUY=close highest entry, SELL=close lowest
        - "lowest_entry":  BUY=close lowest entry, SELL=close highest
        - "oldest":        close first (oldest) ticket

        After closing, optionally applies group BE if configured.

        Returns dict with close result info, or None if no group found.
        """
        group = self._groups.get(fingerprint)
        if not group or group.status != GroupStatus.ACTIVE:
            return None

        if not reply_executor:
            return None

        # Find open tickets in this group
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        open_tickets = []
        for ticket in group.tickets:
            positions = mt5.positions_get(ticket=ticket)
            if positions and len(positions) > 0:
                open_tickets.append(ticket)

        if not open_tickets:
            return {"status": "no_open_orders", "group_fp": fingerprint}

        # Pick which ticket to close
        strategy = group.reply_close_strategy
        is_buy = group.side == Side.BUY or (
            isinstance(group.side, str) and group.side.upper() == "BUY"
        )

        if strategy == "highest_entry":
            # BUY: close highest entry. SELL: close lowest entry
            if is_buy:
                target_ticket = max(open_tickets, key=lambda t: group.entry_prices.get(t, 0))
            else:
                target_ticket = min(open_tickets, key=lambda t: group.entry_prices.get(t, float("inf")))
        elif strategy == "lowest_entry":
            if is_buy:
                target_ticket = min(open_tickets, key=lambda t: group.entry_prices.get(t, float("inf")))
            else:
                target_ticket = max(open_tickets, key=lambda t: group.entry_prices.get(t, 0))
        elif strategy == "oldest":
            target_ticket = open_tickets[0]
        else:
            # "all" — should not reach here, handled by caller
            return None

        # Close the selected ticket
        from core.reply_action_parser import ReplyAction, ReplyActionType

        close_action = ReplyAction(action=ReplyActionType.CLOSE)
        summary = reply_executor.execute(
            target_ticket, close_action, dry_run=dry_run,
        )

        entry_price = group.entry_prices.get(target_ticket, 0)
        remaining = [t for t in open_tickets if t != target_ticket]

        result = {
            "status": "closed",
            "ticket": target_ticket,
            "entry_price": entry_price,
            "summary": summary,
            "remaining_count": len(remaining),
            "total_count": len(open_tickets),
            "group_fp": fingerprint,
            "symbol": group.symbol,
        }

        log_event(
            "group_selective_close",
            fingerprint=fingerprint,
            ticket=target_ticket,
            entry_price=entry_price,
            strategy=strategy,
            remaining=len(remaining),
        )

        # Apply group BE if configured and there are remaining orders
        if group.group_be_on_partial_close and remaining:
            self.apply_group_be(fingerprint)

        return result

    def apply_group_be(self, fingerprint: str) -> None:
        """Set SL to best remaining entry price after partial close.

        BUY: SL = min(remaining entries) — worst case breakeven
        SELL: SL = max(remaining entries)

        Only applies if the new BE level is MORE favorable than current SL.
        """
        group = self._groups.get(fingerprint)
        if not group or group.status != GroupStatus.ACTIVE:
            return

        try:
            import MetaTrader5 as mt5
        except ImportError:
            return

        # Find still-open tickets and their entries
        open_entries: dict[int, float] = {}
        for ticket in group.tickets:
            positions = mt5.positions_get(ticket=ticket)
            if positions and len(positions) > 0:
                open_entries[ticket] = group.entry_prices.get(ticket, positions[0].price_open)

        if not open_entries:
            return

        is_buy = group.side == Side.BUY or (
            isinstance(group.side, str) and group.side.upper() == "BUY"
        )

        # Calculate BE target
        if is_buy:
            be_target = min(open_entries.values())
        else:
            be_target = max(open_entries.values())

        # Only apply if more favorable than current SL
        current_sl = group.current_group_sl
        if current_sl is not None:
            if is_buy and be_target <= current_sl:
                log_event(
                    "group_be_skipped",
                    fingerprint=fingerprint,
                    reason="current_sl_better",
                    be_target=be_target,
                    current_sl=current_sl,
                )
                return
            if not is_buy and be_target >= current_sl:
                log_event(
                    "group_be_skipped",
                    fingerprint=fingerprint,
                    reason="current_sl_better",
                    be_target=be_target,
                    current_sl=current_sl,
                )
                return

        # Apply BE SL to all remaining positions
        symbol_info = mt5.symbol_info(group.symbol)
        if not symbol_info:
            return

        digits = symbol_info.digits
        be_target = round(be_target, digits)

        open_positions = []
        for ticket in open_entries:
            positions = mt5.positions_get(ticket=ticket)
            if positions:
                open_positions.append(positions[0])

        if open_positions:
            self._modify_group_sl(mt5, group, be_target, open_positions, digits)
            log_event(
                "group_be_applied",
                fingerprint=fingerprint,
                be_target=be_target,
                remaining_orders=len(open_positions),
            )

    # ── G4: Secure Profit Group Action ────────────────────────────

    def secure_profit_group(
        self,
        fingerprint: str,
        reply_executor=None,
        dry_run: bool = False,
    ) -> dict | None:
        """Secure profit across a group when admin replies +pip (G4).

        Logic:
        - If >1 open order: close WORST entry, set BE on remaining.
            SELL: worst = lowest entry (least profit).
            BUY:  worst = highest entry (least profit).
        - If 1 open order: just set BE on that order.
        - If 0 open orders: return no_open_orders.

        Returns dict with action result info.
        """
        group = self._groups.get(fingerprint)
        if not group or group.status != GroupStatus.ACTIVE:
            return {"status": "no_group", "group_fp": fingerprint}

        if not reply_executor:
            return None

        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        # Find open tickets
        open_tickets: list[int] = []
        for ticket in group.tickets:
            positions = mt5.positions_get(ticket=ticket)
            if positions and len(positions) > 0:
                open_tickets.append(ticket)

        if not open_tickets:
            return {"status": "no_open_orders", "group_fp": fingerprint}

        is_buy = group.side == Side.BUY or (
            isinstance(group.side, str) and group.side.upper() == "BUY"
        )

        closed_ticket = None
        be_tickets: list[int] = []

        if len(open_tickets) > 1:
            # Close WORST entry (least profitable)
            if is_buy:
                # BUY: worst = highest entry (bought expensive)
                worst_ticket = max(
                    open_tickets,
                    key=lambda t: group.entry_prices.get(t, 0),
                )
            else:
                # SELL: worst = lowest entry (sold cheap)
                worst_ticket = min(
                    open_tickets,
                    key=lambda t: group.entry_prices.get(t, float("inf")),
                )

            # Close worst
            from core.reply_action_parser import ReplyAction, ReplyActionType
            close_action = ReplyAction(action=ReplyActionType.CLOSE)
            summary = reply_executor.execute(
                worst_ticket, close_action, dry_run=dry_run,
            )
            closed_ticket = worst_ticket
            worst_entry = group.entry_prices.get(closed_ticket, 0)
            remaining = [t for t in open_tickets if t != worst_ticket]

            # Set BE on remaining: use CLOSED entry as floor + lock
            # SELL: SL = closed_entry - lock (below worst entry = profit zone)
            # BUY:  SL = closed_entry + lock (above worst entry = profit zone)
            symbol_info = mt5.symbol_info(group.symbol)
            pip_size = estimate_pip_size(group.symbol)
            digits = symbol_info.digits if symbol_info else 5
            lock_pips = getattr(reply_executor, '_reply_be_lock_pips', 1.0)
            lock_distance = lock_pips * pip_size

            if is_buy:
                floor_sl = worst_entry + lock_distance
            else:
                floor_sl = worst_entry - lock_distance
            floor_sl = round(floor_sl, digits)

            for ticket in remaining:
                positions = mt5.positions_get(ticket=ticket)
                if not positions:
                    continue
                pos = positions[0]
                # Guard: only move SL if favorable
                if is_buy and pos.sl > 0 and floor_sl <= pos.sl:
                    continue  # BUY: don't move SL down
                if not is_buy and pos.sl > 0 and floor_sl >= pos.sl:
                    continue  # SELL: don't move SL up
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "symbol": pos.symbol,
                    "sl": floor_sl,
                    "tp": pos.tp,
                }
                result = mt5.order_send(request)
                if result and result.retcode in (10008, 10009):
                    be_tickets.append(ticket)

            log_event(
                "secure_profit_multi",
                fingerprint=fingerprint,
                closed_ticket=closed_ticket,
                closed_entry=worst_entry,
                floor_sl=floor_sl,
                be_tickets=be_tickets,
            )

        else:
            # Only 1 order: just set BE
            ticket = open_tickets[0]
            from core.reply_action_parser import ReplyAction, ReplyActionType
            be_action = ReplyAction(action=ReplyActionType.BREAKEVEN)
            reply_executor.execute(ticket, be_action, dry_run=dry_run)
            be_tickets.append(ticket)

            log_event(
                "secure_profit_single",
                fingerprint=fingerprint,
                be_ticket=ticket,
            )

        return {
            "status": "secured",
            "closed_ticket": closed_ticket,
            "closed_entry": group.entry_prices.get(closed_ticket) if closed_ticket else None,
            "be_tickets": be_tickets,
            "remaining_count": len(be_tickets),
            "total_count": len(open_tickets),
            "group_fp": fingerprint,
            "symbol": group.symbol,
        }

    # ── P10.1: Edit/Delete Group Support ──────────────────────────

    def cancel_group_pending_orders(
        self,
        fingerprint: str,
        executor=None,
    ) -> dict:
        """Cancel all PENDING orders in a group. Leave filled positions.

        Used when signal is edited or deleted — cancel unfilled orders
        only, keep filled (running) positions untouched.

        Args:
            fingerprint: Group fingerprint
            executor: TradeExecutor instance for cancel_order()

        Returns:
            {
                "found": bool,
                "cancelled": [ticket, ...],
                "filled_kept": [ticket, ...],
                "group_completed": bool,
            }
        """
        result: dict = {
            "found": False,
            "cancelled": [],
            "filled_kept": [],
            "group_completed": False,
        }

        group = self._groups.get(fingerprint)
        if not group or group.status != GroupStatus.ACTIVE:
            return result

        result["found"] = True

        try:
            import MetaTrader5 as mt5
        except ImportError:
            return result

        for ticket in list(group.tickets):
            # Check if ticket is a pending order (not yet filled)
            orders = mt5.orders_get(ticket=ticket)
            if orders and len(orders) > 0:
                # Pending order — cancel it
                if executor:
                    executor.cancel_order(
                        ticket=ticket,
                        fingerprint=fingerprint,
                    )
                result["cancelled"].append(ticket)

                # Remove from group tracking
                group.tickets.remove(ticket)
                group.entry_prices.pop(ticket, None)
                self._ticket_to_group.pop(ticket, None)
            else:
                # Check if it's a filled position (still open)
                positions = mt5.positions_get(ticket=ticket)
                if positions and len(positions) > 0:
                    result["filled_kept"].append(ticket)
                else:
                    # Already closed — remove from tracking
                    group.tickets.remove(ticket)
                    group.entry_prices.pop(ticket, None)
                    self._ticket_to_group.pop(ticket, None)

        # If no tickets remain, complete the group
        if not group.tickets:
            self._complete_group(group)
            result["group_completed"] = True

        # Update DB
        if self._storage and group.tickets:
            try:
                self._storage.update_group_tickets(
                    fingerprint,
                    group.tickets,
                    group.entry_prices,
                )
            except Exception:
                pass

        log_event(
            "group_pending_cancelled",
            fingerprint=fingerprint,
            cancelled=result["cancelled"],
            filled_kept=result["filled_kept"],
            group_completed=result["group_completed"],
        )

        return result

    # ── P10: Group Query Methods ─────────────────────────────────

    def get_group(self, fingerprint: str) -> OrderGroup | None:
        """Get a group by base fingerprint."""
        return self._groups.get(fingerprint)

    def get_group_by_ticket(self, ticket: int) -> OrderGroup | None:
        """Get a group for a specific ticket (reverse lookup)."""
        fp = self._ticket_to_group.get(ticket)
        if fp:
            return self._groups.get(fp)
        return None

    def get_group_status(self, fingerprint: str) -> dict | None:
        """Get group status summary for Telegram response.

        Returns None if group not found.
        """
        group = self._groups.get(fingerprint)
        if not group:
            return None

        return {
            "fingerprint": group.fingerprint,
            "symbol": group.symbol,
            "side": group.side.value if isinstance(group.side, Side) else group.side,
            "total_orders": len(group.tickets),
            "status": group.status.value,
            "tickets": group.tickets,
            "entry_prices": group.entry_prices,
            "current_sl": group.current_group_sl,
            "reply_close_strategy": group.reply_close_strategy,
        }

    def _send_group_alert(
        self, group: OrderGroup, alert_type: str, message: str,
    ) -> None:
        """Send throttled alert for a group event."""
        if not self._alerter:
            return

        # Use first ticket for throttle key (one alert per group event)
        first_ticket = group.tickets[0] if group.tickets else 0
        if not self._should_alert(first_ticket, alert_type):
            return

        if self._channel_manager:
            ch_name = self._channel_manager.get_channel_name(group.channel_id)
            message = f"[{ch_name}] {message}"

        self._alerter.send_alert_sync(alert_type, message)

    # ── Alert helpers ─────────────────────────────────────────────

    def _should_alert(self, ticket: int, event_type: str) -> bool:
        """Check per-ticket cooldown for alert throttling."""
        key = (ticket, event_type)
        now = _time.time()
        last = self._last_alert_time.get(key, 0.0)
        if (now - last) < self._ALERT_COOLDOWN:
            return False
        self._last_alert_time[key] = now
        return True

    def _send_position_alert(
        self, ticket: int, alert_type: str, symbol: str, message: str,
    ) -> None:
        """Send throttled alert with channel context."""
        if not self._alerter or not self._should_alert(ticket, alert_type):
            return

        # Add channel context if available
        channel_id = self._ticket_to_channel.get(ticket)
        if channel_id and self._channel_manager:
            ch_name = self._channel_manager.get_channel_name(channel_id)
            message = f"[{ch_name}] {message}"

        self._alerter.send_alert_sync(alert_type, message)
