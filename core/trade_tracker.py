"""
core/trade_tracker.py

Background worker that polls MT5 deal history to track trade outcomes.

Responsibilities:
- Poll mt5.history_deals_get() for closing deals (DEAL_ENTRY_OUT).
- Map deals to bot orders via ticket/position_ticket.
- Persist trade outcomes in the `trades` table.
- Detect pending order fills (DEAL_ENTRY_IN) and update position_ticket.
- Dispatch PnL reply messages via TelegramAlerter.
- Persist last_poll_time in tracker_state for restart recovery.

All features are opt-in via TRADE_TRACKER_POLL_SECONDS > 0.
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from utils.logger import log_event

if TYPE_CHECKING:
    from core.storage import Storage
    from core.telegram_alerter import TelegramAlerter


class TradeTracker:
    """Track trade outcomes by polling MT5 deal history.

    Runs as a background asyncio task, similar to DailyRiskGuard.
    """

    _STATE_KEY = "last_deal_poll_time"

    def __init__(
        self,
        storage: Storage,
        alerter: TelegramAlerter,
        magic_number: int,
        poll_seconds: int = 30,
    ) -> None:
        self._storage = storage
        self._alerter = alerter
        self._magic = magic_number
        self._poll_seconds = poll_seconds
        self._poll_task: asyncio.Task | None = None
        # Throttle partial close replies: {position_id: last_reply_epoch}
        self._partial_reply_times: dict[int, float] = {}
        self._PARTIAL_REPLY_COOLDOWN = 60  # seconds
        # Reply-closed tickets: suppress PnL reply for 5 minutes
        self._reply_closed: dict[int, float] = {}  # ticket → epoch
        self._REPLY_CLOSED_TTL = 300  # 5 minutes

    @property
    def is_enabled(self) -> bool:
        return self._poll_seconds > 0

    def mark_reply_closed(self, ticket: int) -> None:
        """Mark a ticket as closed via reply command.

        TradeTracker will suppress PnL reply for this ticket
        for up to _REPLY_CLOSED_TTL seconds.
        """
        self._reply_closed[ticket] = _time.time()

    def _is_reply_closed(self, ticket: int) -> bool:
        """Check if ticket was recently closed via reply.

        Returns True and removes entry if within TTL.
        Also cleans up expired entries.
        """
        ts = self._reply_closed.get(ticket)
        if ts is None:
            return False
        if (_time.time() - ts) < self._REPLY_CLOSED_TTL:
            del self._reply_closed[ticket]
            return True
        # Expired — cleanup
        del self._reply_closed[ticket]
        return False

    async def start(self) -> None:
        """Start the background poll loop."""
        if not self.is_enabled:
            log_event("trade_tracker_disabled")
            return

        self._poll_task = asyncio.create_task(self._poll_loop())
        log_event(
            "trade_tracker_started",
            poll_seconds=self._poll_seconds,
            magic=self._magic,
        )

    async def stop(self) -> None:
        """Stop the background poll loop."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        log_event("trade_tracker_stopped")

    async def _poll_loop(self) -> None:
        """Main poll loop — runs until cancelled."""
        while True:
            try:
                await asyncio.sleep(self._poll_seconds)
                await self._poll_deals()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log_event("trade_tracker_error", error=str(exc))

    async def _poll_deals(self) -> None:
        """Poll MT5 for new deals and process them."""
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return

        # Determine time window
        from_time = self._get_poll_start_time()
        to_time = datetime.now(timezone.utc)

        # Fetch deals in time range
        deals = mt5.history_deals_get(from_time, to_time)
        if deals is None or len(deals) == 0:
            # Update poll time even if no deals
            self._save_poll_time(to_time)
            return

        # Filter for bot's magic number
        bot_deals = [d for d in deals if d.magic == self._magic]

        processed = 0
        for deal in bot_deals:
            try:
                if deal.entry == mt5.DEAL_ENTRY_OUT:
                    # Closing deal — track PnL
                    await self._process_closing_deal(deal)
                    processed += 1
                elif deal.entry == mt5.DEAL_ENTRY_IN:
                    # Opening deal — detect pending fill
                    self._process_opening_deal(deal)
            except Exception as exc:
                log_event(
                    "trade_tracker_deal_error",
                    deal_ticket=deal.ticket,
                    error=str(exc),
                )

        if processed > 0:
            log_event(
                "trade_tracker_poll_complete",
                deals_found=len(bot_deals),
                trades_processed=processed,
            )

        # Save last poll time
        self._save_poll_time(to_time)

    async def _process_closing_deal(self, deal) -> None:
        """Process a DEAL_ENTRY_OUT deal — record trade outcome and reply."""

        # Resolve deal.position_id → order in DB
        order = self._resolve_order(deal.position_id)
        if not order:
            log_event(
                "trade_tracker_orphan_deal",
                deal_ticket=deal.ticket,
                position_id=deal.position_id,
            )
            return

        fingerprint = order.get("fingerprint", "")
        channel_id = order.get("channel_id", "")

        # Get reply info from signals table
        reply_info = self._storage.get_signal_reply_info(fingerprint)
        source_chat_id = ""
        source_message_id = ""
        if reply_info:
            source_chat_id, source_message_id = reply_info

        # Format close time
        close_time = datetime.fromtimestamp(
            deal.time, tz=timezone.utc
        ).isoformat()

        # Determine close reason
        close_reason = self._infer_close_reason(deal)

        # Store trade in DB (deal_ticket UNIQUE prevents double-processing)
        row_id = self._storage.store_trade(
            ticket=deal.position_id,
            deal_ticket=deal.ticket,
            fingerprint=fingerprint,
            channel_id=channel_id,
            close_volume=deal.volume,
            close_price=deal.price,
            close_time=close_time,
            pnl=deal.profit,
            commission=deal.commission,
            swap=deal.swap,
            close_reason=close_reason,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )

        if row_id is None:
            # Already processed (UNIQUE constraint)
            return

        log_event(
            "trade_tracked",
            deal_ticket=deal.ticket,
            ticket=deal.position_id,
            symbol=deal.symbol,
            pnl=deal.profit,
            volume=deal.volume,
            channel_id=channel_id,
        )

        # Suppress PnL reply if ticket was closed via reply command
        if self._is_reply_closed(deal.position_id):
            log_event(
                "trade_tracker_reply_suppressed",
                deal_ticket=deal.ticket,
                position_id=deal.position_id,
            )
            return

        # Dispatch PnL reply (with partial close throttle)
        if close_reason == "PARTIAL_CLOSE":
            last_reply = self._partial_reply_times.get(deal.position_id, 0.0)
            now = _time.time()
            if (now - last_reply) < self._PARTIAL_REPLY_COOLDOWN:
                log_event(
                    "trade_tracker_partial_throttled",
                    deal_ticket=deal.ticket,
                    position_id=deal.position_id,
                    cooldown_remaining=int(self._PARTIAL_REPLY_COOLDOWN - (now - last_reply)),
                )
                return
            self._partial_reply_times[deal.position_id] = now

        await self._send_pnl_reply(
            deal=deal,
            close_reason=close_reason,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )

    def _process_opening_deal(self, deal) -> None:
        """Process a DEAL_ENTRY_IN deal — update position_ticket for pending fills."""

        # deal.order is the order ticket, deal.position_id is the new position ticket
        if deal.order and deal.position_id:
            # Check if this order ticket exists in our DB
            order = self._storage.get_order_by_ticket(deal.order)
            if order and not order.get("position_ticket"):
                self._storage.update_position_ticket(
                    order_ticket=deal.order,
                    position_ticket=deal.position_id,
                )
                log_event(
                    "pending_fill_detected",
                    order_ticket=deal.order,
                    position_ticket=deal.position_id,
                    symbol=deal.symbol,
                )

    def _resolve_order(self, position_id: int) -> dict | None:
        """Resolve MT5 position_id to a DB order.

        Two-step lookup:
        1. Direct match: orders.ticket == position_id (MARKET orders)
        2. Position ticket match: orders.position_ticket == position_id (filled pending)
        """
        order = self._storage.get_order_by_ticket(position_id)
        if order:
            return order

        order = self._storage.get_order_by_position_ticket(position_id)
        return order

    def _infer_close_reason(self, deal) -> str:
        """Infer why this deal was executed."""
        comment = deal.comment if hasattr(deal, "comment") else ""

        if "tp" in comment.lower():
            return "TP"
        elif "sl" in comment.lower():
            return "SL"
        elif "partial_close" in comment.lower():
            return "PARTIAL_CLOSE"
        elif comment:
            return comment[:50]
        return "MANUAL"

    async def _send_pnl_reply(
        self,
        deal,
        close_reason: str,
        source_chat_id: str,
        source_message_id: str,
    ) -> None:
        """Send PnL result as a reply to the original signal message."""
        if not source_chat_id or not source_message_id:
            return

        # Determine side
        try:
            import MetaTrader5 as mt5
            side = "SELL" if deal.type == mt5.DEAL_TYPE_SELL else "BUY"
        except ImportError:
            side = "?"

        total_pnl = deal.profit + deal.commission + deal.swap
        emoji = "🟢" if total_pnl >= 0 else "🔴"

        message = (
            f"{emoji} **Trade Closed**\n"
            f"Symbol: `{deal.symbol}`\n"
            f"Side: {side}\n"
            f"Volume: {deal.volume}\n"
            f"Close Price: {deal.price}\n"
            f"PnL: {'+'if deal.profit >= 0 else ''}{deal.profit:.2f}\n"
            f"Commission: {deal.commission:.2f}\n"
            f"Swap: {deal.swap:.2f}\n"
            f"**Net: {'+'if total_pnl >= 0 else ''}{total_pnl:.2f}**\n"
            f"Reason: {close_reason}"
        )

        try:
            msg_id = int(source_message_id) if source_message_id else None
            if msg_id:
                await self._alerter.reply_to_message(
                    source_chat_id, msg_id, message,
                )
            else:
                await self._alerter.send_debug(message)
        except Exception as exc:
            log_event(
                "trade_tracker_reply_failed",
                deal_ticket=deal.ticket,
                error=str(exc),
            )

    # ── Time management ──────────────────────────────────────────

    def _get_poll_start_time(self) -> datetime:
        """Get the start time for deal polling.

        Reads from tracker_state; defaults to 24 hours ago on first run.
        """
        stored = self._storage.get_tracker_state(self._STATE_KEY)
        if stored:
            try:
                return datetime.fromisoformat(stored)
            except ValueError:
                pass

        # Default: 24 hours ago
        return datetime.now(timezone.utc) - timedelta(hours=24)

    def _save_poll_time(self, dt: datetime) -> None:
        """Persist the last poll time for restart recovery."""
        self._storage.set_tracker_state(
            self._STATE_KEY, dt.isoformat(),
        )
