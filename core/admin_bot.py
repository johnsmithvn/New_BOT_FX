"""
core/admin_bot.py

Telegram Bot API admin control panel.
Sends alerts/debug/PnL via Bot API and provides inline keyboard
for order management (list, cancel pending, close all).

Security: Only TELEGRAM_BOT_ADMIN_ID can interact.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from utils.logger import log_event

if TYPE_CHECKING:
    from core.command_executor import CommandExecutor


# ── Order type labels ────────────────────────────────────────────
_ORDER_TYPE_NAMES = {
    0: "BUY",
    1: "SELL",
    2: "BUY_LIMIT",
    3: "SELL_LIMIT",
    4: "BUY_STOP",
    5: "SELL_STOP",
    6: "BUY_STOP_LIMIT",
    7: "SELL_STOP_LIMIT",
}


class AdminBot:
    """Telegram Bot API admin panel.

    Responsibilities:
    - Send messages (alerts, debug, PnL) to admin via Bot API
    - Handle /start → inline keyboard menu
    - Handle button callbacks for order management
    - Confirmation step for destructive actions
    """

    def __init__(
        self,
        token: str,
        admin_id: int,
        magic: int = 234000,
        command_executor: CommandExecutor | None = None,
    ) -> None:
        self._token = token
        self._admin_id = admin_id
        self._magic = magic
        self._command_executor = command_executor
        self._app: Application | None = None
        self._started = False

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Build and start the bot application (non-blocking polling)."""
        if not self._token:
            log_event("admin_bot_skip", reason="no bot token configured")
            return

        self._app = (
            Application.builder()
            .token(self._token)
            .build()
        )

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("menu", self._cmd_start))
        self._app.add_handler(CallbackQueryHandler(self._on_callback))

        # Set bot commands for menu
        await self._app.bot.set_my_commands([
            BotCommand("start", "Show admin panel"),
            BotCommand("menu", "Show admin panel"),
        ])

        # Initialize and start polling in background
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        self._started = True
        log_event("admin_bot_started", admin_id=self._admin_id)

    async def stop(self) -> None:
        """Graceful shutdown."""
        if self._app and self._started:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
                self._started = False
                log_event("admin_bot_stopped")
            except Exception as exc:
                log_event("admin_bot_stop_error", error=str(exc))

    # ── Public API: send messages ────────────────────────────────

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> None:
        """Send a message to the admin chat.

        Falls back to plain text if Markdown parsing fails.
        """
        if not self._app or not self._started:
            return
        try:
            await self._app.bot.send_message(
                chat_id=self._admin_id,
                text=text,
                parse_mode=parse_mode,
            )
        except Exception:
            # Fallback: send without parse_mode (Markdown special chars in text)
            try:
                await self._app.bot.send_message(
                    chat_id=self._admin_id,
                    text=text,
                )
            except Exception as exc:
                log_event("admin_bot_send_failed", error=str(exc))

    # ── Security guard ───────────────────────────────────────────

    def _is_admin(self, update: Update) -> bool:
        """Check if the user is the authorized admin."""
        user = update.effective_user
        if not user:
            return False
        return user.id == self._admin_id

    # ── /start command ───────────────────────────────────────────

    async def _cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not self._is_admin(update):
            return

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Open Orders", callback_data="list_open")],
            [InlineKeyboardButton("⏳ Pending Orders", callback_data="list_pending")],
            [InlineKeyboardButton("❌ Cancel All Pending", callback_data="confirm_cancel")],
            [InlineKeyboardButton("🔴 Close All Orders", callback_data="confirm_close")],
        ])

        await update.message.reply_text(
            "🤖 *Admin Panel*\n\nSelect an action:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    # ── Callback router ──────────────────────────────────────────

    async def _on_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        query = update.callback_query
        if not query:
            return
        if not self._is_admin(update):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return

        await query.answer()

        handlers = {
            "list_open": self._handle_list_open,
            "list_pending": self._handle_list_pending,
            "confirm_cancel": self._handle_confirm_cancel,
            "confirm_close": self._handle_confirm_close,
            "exec_cancel": self._handle_exec_cancel,
            "exec_close": self._handle_exec_close,
            "abort": self._handle_abort,
            "back_menu": self._handle_back_menu,
        }

        handler = handlers.get(query.data)
        if handler:
            await handler(query)
        else:
            await query.edit_message_text("❌ Unknown action")

    # ── List open positions ──────────────────────────────────────

    async def _handle_list_open(self, query) -> None:
        try:
            import MetaTrader5 as mt5
            positions = mt5.positions_get()
        except Exception as exc:
            await query.edit_message_text(f"❌ MT5 error: {exc}")
            return

        if not positions:
            await query.edit_message_text(
                "📋 *Open Orders*\n\nNo open positions.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self._back_keyboard(),
            )
            return

        bot_positions = [p for p in positions if p.magic == self._magic]
        if not bot_positions:
            await query.edit_message_text(
                "📋 *Open Orders*\n\nNo bot positions (other positions may exist).",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self._back_keyboard(),
            )
            return

        lines = ["📋 *Open Orders*\n"]
        total_pnl = 0.0
        for p in bot_positions:
            side = "BUY" if p.type == 0 else "SELL"
            pnl_emoji = "🟢" if p.profit >= 0 else "🔴"
            total_pnl += p.profit
            lines.append(
                f"{pnl_emoji} `{p.symbol}` {side} {p.volume} lot\n"
                f"   Entry: {p.price_open} | SL: {p.sl} | TP: {p.tp}\n"
                f"   PnL: ${p.profit:+.2f} | #{p.ticket}"
            )

        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        lines.append(f"\n{pnl_emoji} *Total PnL: ${total_pnl:+.2f}*")
        lines.append(f"📊 {len(bot_positions)} position(s)")

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self._back_keyboard(),
        )

    # ── List pending orders ──────────────────────────────────────

    async def _handle_list_pending(self, query) -> None:
        try:
            import MetaTrader5 as mt5
            orders = mt5.orders_get()
        except Exception as exc:
            await query.edit_message_text(f"❌ MT5 error: {exc}")
            return

        if not orders:
            await query.edit_message_text(
                "⏳ *Pending Orders*\n\nNo pending orders.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self._back_keyboard(),
            )
            return

        bot_orders = [o for o in orders if o.magic == self._magic]
        if not bot_orders:
            await query.edit_message_text(
                "⏳ *Pending Orders*\n\nNo bot pending orders.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self._back_keyboard(),
            )
            return

        lines = ["⏳ *Pending Orders*\n"]
        for o in bot_orders:
            order_type = _ORDER_TYPE_NAMES.get(o.type, f"TYPE_{o.type}")
            age_s = max(0, int(time.time()) - o.time_setup)
            age_m = age_s // 60
            lines.append(
                f"📌 `{o.symbol}` {order_type} {o.volume_current} lot\n"
                f"   Price: {o.price_open} | SL: {o.sl} | TP: {o.tp}\n"
                f"   Age: {age_m}min | #{o.ticket}"
            )

        lines.append(f"\n📊 {len(bot_orders)} pending order(s)")

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self._back_keyboard(),
        )

    # ── Confirm cancel all pending ───────────────────────────────

    async def _handle_confirm_cancel(self, query) -> None:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Confirm Cancel", callback_data="exec_cancel"),
                InlineKeyboardButton("↩️ Abort", callback_data="abort"),
            ],
        ])
        await query.edit_message_text(
            "⚠️ *Cancel ALL pending orders?*\n\n"
            "This will remove all BUY\\_LIMIT, SELL\\_LIMIT, BUY\\_STOP, SELL\\_STOP orders.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    # ── Confirm close all ────────────────────────────────────────

    async def _handle_confirm_close(self, query) -> None:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Confirm Close All", callback_data="exec_close"),
                InlineKeyboardButton("↩️ Abort", callback_data="abort"),
            ],
        ])
        await query.edit_message_text(
            "🔴 *Close ALL open positions?*\n\n"
            "This will close every position opened by this bot.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    # ── Execute cancel ───────────────────────────────────────────

    async def _handle_exec_cancel(self, query) -> None:
        if not self._command_executor:
            await query.edit_message_text("❌ Command executor not available")
            return

        from core.command_parser import CommandType, ManagementCommand
        cmd = ManagementCommand(command_type=CommandType.CANCEL_ALL)
        result = self._command_executor.execute(cmd)

        log_event("admin_bot_cancel_all", result=result)
        await query.edit_message_text(
            f"❌ *Cancel All Pending*\n\n{result}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self._back_keyboard(),
        )

    # ── Execute close all ────────────────────────────────────────

    async def _handle_exec_close(self, query) -> None:
        if not self._command_executor:
            await query.edit_message_text("❌ Command executor not available")
            return

        from core.command_parser import CommandType, ManagementCommand
        cmd = ManagementCommand(command_type=CommandType.CLOSE_ALL)
        result = self._command_executor.execute(cmd)

        log_event("admin_bot_close_all", result=result)
        await query.edit_message_text(
            f"🔴 *Close All Orders*\n\n{result}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self._back_keyboard(),
        )

    # ── Abort / Back ─────────────────────────────────────────────

    async def _handle_abort(self, query) -> None:
        await query.edit_message_text(
            "↩️ Action cancelled.",
            reply_markup=self._back_keyboard(),
        )

    async def _handle_back_menu(self, query) -> None:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Open Orders", callback_data="list_open")],
            [InlineKeyboardButton("⏳ Pending Orders", callback_data="list_pending")],
            [InlineKeyboardButton("❌ Cancel All Pending", callback_data="confirm_cancel")],
            [InlineKeyboardButton("🔴 Close All Orders", callback_data="confirm_close")],
        ])
        await query.edit_message_text(
            "🤖 *Admin Panel*\n\nSelect an action:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _back_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_menu")],
        ])
