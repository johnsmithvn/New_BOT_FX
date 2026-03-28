"""
tests/test_admin_bot.py

Unit tests for core/admin_bot.py and core/telegram_alerter.py (v0.23.0).
"""

import asyncio
import time
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Fixtures ────────────────────────────────────────────────────

@dataclass
class FakePosition:
    symbol: str
    type: int        # 0=BUY, 1=SELL
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    ticket: int
    magic: int


@dataclass
class FakeOrder:
    symbol: str
    type: int
    volume_current: float
    price_open: float
    sl: float
    tp: float
    ticket: int
    magic: int
    time_setup: int


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeUpdate:
    def __init__(self, user_id: int, has_message: bool = True, has_query: bool = False):
        self.effective_user = FakeUser(user_id)
        self.message = AsyncMock() if has_message else None
        if has_query:
            self.callback_query = AsyncMock()
            self.callback_query.data = "list_open"
        else:
            self.callback_query = None


# ─── AdminBot Tests ──────────────────────────────────────────────

class TestAdminBotSecurity:
    """Test that _is_admin correctly guards access."""

    def test_admin_user_allowed(self):
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        update = FakeUpdate(user_id=12345)
        assert bot._is_admin(update) is True

    def test_non_admin_rejected(self):
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        update = FakeUpdate(user_id=99999)
        assert bot._is_admin(update) is False

    def test_no_user_rejected(self):
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        update = FakeUpdate(user_id=0)
        update.effective_user = None
        assert bot._is_admin(update) is False


class TestAdminBotSendMessage:
    """Test send_message with markdown fallback."""

    @pytest.mark.asyncio
    async def test_send_when_not_started(self):
        """Should silently return when bot not started."""
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        # _started=False, _app=None → should not raise
        await bot.send_message("test")

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Normal send should use Markdown parse_mode."""
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        bot._started = True
        bot._app = MagicMock()
        bot._app.bot.send_message = AsyncMock()

        await bot.send_message("hello *world*")

        bot._app.bot.send_message.assert_called_once_with(
            chat_id=12345,
            text="hello *world*",
            parse_mode="Markdown",
        )

    @pytest.mark.asyncio
    async def test_send_markdown_fallback(self):
        """If Markdown fails, should retry without parse_mode."""
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        bot._started = True
        bot._app = MagicMock()

        # First call raises (bad markdown), second succeeds
        bot._app.bot.send_message = AsyncMock(
            side_effect=[Exception("Bad Markdown"), None]
        )

        await bot.send_message("bad_markdown_text")

        assert bot._app.bot.send_message.call_count == 2
        # Second call should NOT pass parse_mode
        second_call = bot._app.bot.send_message.call_args_list[1]
        assert "parse_mode" not in second_call.kwargs


class TestAdminBotCallbackRouter:
    """Test callback routing and null-guard."""

    @pytest.mark.asyncio
    async def test_null_callback_query(self):
        """Should return early if callback_query is None."""
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        update = FakeUpdate(user_id=12345, has_query=False)
        context = MagicMock()
        # Should not raise
        await bot._on_callback(update, context)

    @pytest.mark.asyncio
    async def test_unauthorized_callback(self):
        """Non-admin should get '⛔ Unauthorized' answer."""
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        update = FakeUpdate(user_id=99999, has_query=True)
        context = MagicMock()

        await bot._on_callback(update, context)

        update.callback_query.answer.assert_called_once_with(
            "⛔ Unauthorized", show_alert=True,
        )

    @pytest.mark.asyncio
    async def test_unknown_callback_data(self):
        """Unknown action should show error message."""
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345)
        update = FakeUpdate(user_id=12345, has_query=True)
        update.callback_query.data = "unknown_action"
        context = MagicMock()

        await bot._on_callback(update, context)

        update.callback_query.edit_message_text.assert_called_once_with(
            "❌ Unknown action"
        )


class TestAdminBotListOpen:
    """Test _handle_list_open with mocked MT5."""

    @pytest.mark.asyncio
    async def test_no_positions(self):
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345, magic=234000)
        query = AsyncMock()

        with patch("core.admin_bot.mt5", create=True) as mock_mt5:
            # Need to mock the import inside the function
            import sys
            fake_mt5 = MagicMock()
            fake_mt5.positions_get.return_value = None
            sys.modules["MetaTrader5"] = fake_mt5

            await bot._handle_list_open(query)

            query.edit_message_text.assert_called_once()
            call_text = query.edit_message_text.call_args.args[0]
            assert "No open positions" in call_text

            del sys.modules["MetaTrader5"]

    @pytest.mark.asyncio
    async def test_positions_with_pnl(self):
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345, magic=234000)
        query = AsyncMock()

        positions = [
            FakePosition("XAUUSD", 0, 0.01, 2650.0, 2640.0, 2670.0, 15.50, 111, 234000),
            FakePosition("EURUSD", 1, 0.02, 1.0800, 1.0850, 1.0750, -3.20, 222, 234000),
            FakePosition("GBPUSD", 0, 0.05, 1.2700, 1.2650, 1.2800, 0.0, 333, 999999),  # different magic
        ]

        import sys
        fake_mt5 = MagicMock()
        fake_mt5.positions_get.return_value = positions
        sys.modules["MetaTrader5"] = fake_mt5

        await bot._handle_list_open(query)

        call_text = query.edit_message_text.call_args.args[0]
        assert "XAUUSD" in call_text
        assert "EURUSD" in call_text
        assert "GBPUSD" not in call_text  # magic 999999 filtered out
        assert "$+12.30" in call_text  # total PnL = 15.50 - 3.20
        assert "2 position(s)" in call_text

        del sys.modules["MetaTrader5"]


class TestAdminBotListPending:
    """Test _handle_list_pending with clamped age."""

    @pytest.mark.asyncio
    async def test_negative_age_clamped(self):
        """If time_setup is in the future (clock skew), age should be 0."""
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345, magic=234000)
        query = AsyncMock()

        future_ts = int(time.time()) + 3600  # 1 hour in the future
        orders = [
            FakeOrder("XAUUSD", 2, 0.01, 2650.0, 2640.0, 2670.0, 111, 234000, future_ts),
        ]

        import sys
        fake_mt5 = MagicMock()
        fake_mt5.orders_get.return_value = orders
        sys.modules["MetaTrader5"] = fake_mt5

        await bot._handle_list_pending(query)

        call_text = query.edit_message_text.call_args.args[0]
        assert "0min" in call_text  # clamped to 0, not negative
        assert "BUY_LIMIT" in call_text

        del sys.modules["MetaTrader5"]


class TestAdminBotExecCancel:
    """Test destructive actions route through CommandExecutor."""

    @pytest.mark.asyncio
    async def test_cancel_without_executor(self):
        from core.admin_bot import AdminBot
        bot = AdminBot(token="fake", admin_id=12345, command_executor=None)
        query = AsyncMock()

        await bot._handle_exec_cancel(query)

        query.edit_message_text.assert_called_once_with(
            "❌ Command executor not available"
        )

    @pytest.mark.asyncio
    async def test_cancel_with_executor(self):
        from core.admin_bot import AdminBot
        executor = MagicMock()
        executor.execute.return_value = "Cancelled 3 pending orders"
        bot = AdminBot(token="fake", admin_id=12345, command_executor=executor)
        query = AsyncMock()

        await bot._handle_exec_cancel(query)

        assert executor.execute.called
        call_text = query.edit_message_text.call_args.args[0]
        assert "Cancelled 3 pending orders" in call_text

    @pytest.mark.asyncio
    async def test_close_with_executor(self):
        from core.admin_bot import AdminBot
        executor = MagicMock()
        executor.execute.return_value = "Closed 5 positions"
        bot = AdminBot(token="fake", admin_id=12345, command_executor=executor)
        query = AsyncMock()

        await bot._handle_exec_close(query)

        assert executor.execute.called
        call_text = query.edit_message_text.call_args.args[0]
        assert "Closed 5 positions" in call_text


# ─── TelegramAlerter Tests ──────────────────────────────────────

class TestTelegramAlerter:
    """Test alerter rate limiting and routing."""

    @pytest.mark.asyncio
    async def test_alert_without_bot(self):
        """Alert should be skipped gracefully when no bot configured."""
        from core.telegram_alerter import TelegramAlerter
        alerter = TelegramAlerter(admin_bot=None)
        # Should not raise
        await alerter.send_alert("test", "hello")

    @pytest.mark.asyncio
    async def test_alert_rate_limiting(self):
        """Same alert_type within cooldown should be suppressed."""
        from core.telegram_alerter import TelegramAlerter
        mock_bot = AsyncMock()
        alerter = TelegramAlerter(admin_bot=mock_bot, cooldown_seconds=300)

        await alerter.send_alert("test_type", "first")
        await alerter.send_alert("test_type", "second — should be rate-limited")

        # Only first call should reach the bot
        assert mock_bot.send_message.call_count == 1
        mock_bot.send_message.assert_called_with("first")

    @pytest.mark.asyncio
    async def test_different_alert_types_not_limited(self):
        """Different alert_types should each get their own cooldown."""
        from core.telegram_alerter import TelegramAlerter
        mock_bot = AsyncMock()
        alerter = TelegramAlerter(admin_bot=mock_bot, cooldown_seconds=300)

        await alerter.send_alert("type_a", "msg_a")
        await alerter.send_alert("type_b", "msg_b")

        assert mock_bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_debug_no_rate_limit(self):
        """Debug messages should NOT be rate limited."""
        from core.telegram_alerter import TelegramAlerter
        mock_bot = AsyncMock()
        alerter = TelegramAlerter(admin_bot=mock_bot)

        await alerter.send_debug("debug1")
        await alerter.send_debug("debug2")
        await alerter.send_debug("debug3")

        assert mock_bot.send_message.call_count == 3

    @pytest.mark.asyncio
    async def test_reply_to_message_routes_to_bot(self):
        """reply_to_message should send flat message via bot."""
        from core.telegram_alerter import TelegramAlerter
        mock_bot = AsyncMock()
        alerter = TelegramAlerter(admin_bot=mock_bot)

        await alerter.reply_to_message("chat123", 456, "PnL: +$50")

        mock_bot.send_message.assert_called_once_with("PnL: +$50")

    @pytest.mark.asyncio
    async def test_set_bot(self):
        """set_bot should update the bot instance."""
        from core.telegram_alerter import TelegramAlerter
        alerter = TelegramAlerter(admin_bot=None)
        assert alerter._bot is None

        new_bot = AsyncMock()
        alerter.set_bot(new_bot)
        assert alerter._bot is new_bot


class TestAlerterSendFailure:
    """Test graceful failure handling."""

    @pytest.mark.asyncio
    async def test_send_alert_exception_handled(self):
        """Exception in bot.send_message should not propagate."""
        from core.telegram_alerter import TelegramAlerter
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = Exception("Network error")
        alerter = TelegramAlerter(admin_bot=mock_bot)

        # Should not raise
        await alerter.send_alert("test", "hello")

    @pytest.mark.asyncio
    async def test_send_debug_exception_handled(self):
        """Exception in debug send should not propagate."""
        from core.telegram_alerter import TelegramAlerter
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = Exception("Timeout")
        alerter = TelegramAlerter(admin_bot=mock_bot)

        await alerter.send_debug("debug msg")

    @pytest.mark.asyncio
    async def test_reply_exception_handled(self):
        """Exception in reply send should not propagate."""
        from core.telegram_alerter import TelegramAlerter
        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = Exception("Forbidden")
        alerter = TelegramAlerter(admin_bot=mock_bot)

        await alerter.reply_to_message("chat", 1, "text")
