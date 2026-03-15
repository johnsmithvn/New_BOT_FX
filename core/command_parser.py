"""
core/command_parser.py

Parse Telegram management commands.

Supported commands:
  CLOSE ALL        — close all open positions
  CLOSE <SYMBOL>   — close all positions for a specific symbol
  CLOSE HALF       — close 50% of each open position
  MOVE SL <PRICE>  — move SL to a specific price on all positions
  BREAKEVEN        — move SL to entry on all profitable positions
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CommandType(str, Enum):
    CLOSE_ALL = "CLOSE_ALL"
    CLOSE_SYMBOL = "CLOSE_SYMBOL"
    CLOSE_HALF = "CLOSE_HALF"
    MOVE_SL = "MOVE_SL"
    BREAKEVEN = "BREAKEVEN"


@dataclass
class ManagementCommand:
    """Parsed management command."""
    command_type: CommandType
    symbol: str | None = None
    price: float | None = None
    raw_text: str = ""


class CommandParser:
    """Parse signal management commands from Telegram messages.

    Returns ManagementCommand if the message is a management command,
    or None if it's not a command (fall through to signal parser).
    """

    # Known trading symbols for disambiguation
    _KNOWN_SYMBOLS = {
        "XAUUSD", "XAGUSD", "GOLD", "SILVER",
        "EURUSD", "GBPUSD", "USDJPY", "USDCAD",
        "AUDUSD", "NZDUSD", "USDCHF", "EURGBP",
        "EURJPY", "GBPJPY", "BTCUSD", "ETHUSD",
    }

    def parse(self, text: str) -> ManagementCommand | None:
        """Try to parse text as a management command.

        Returns ManagementCommand or None if not a command.
        """
        if not text:
            return None

        cleaned = text.strip().upper()

        # BREAKEVEN
        if cleaned in ("BREAKEVEN", "BE", "BREAK EVEN"):
            return ManagementCommand(
                command_type=CommandType.BREAKEVEN,
                raw_text=text,
            )

        # CLOSE ALL
        if cleaned in ("CLOSE ALL", "CLOSE ALL TRADES", "CLOSE EVERYTHING"):
            return ManagementCommand(
                command_type=CommandType.CLOSE_ALL,
                raw_text=text,
            )

        # CLOSE HALF
        if cleaned in ("CLOSE HALF", "CLOSE 50%", "HALF CLOSE"):
            return ManagementCommand(
                command_type=CommandType.CLOSE_HALF,
                raw_text=text,
            )

        # CLOSE <SYMBOL>
        close_match = re.match(r"^CLOSE\s+([A-Z]{3,10})$", cleaned)
        if close_match:
            symbol = close_match.group(1)
            if symbol not in ("ALL", "HALF", "EVERYTHING"):
                return ManagementCommand(
                    command_type=CommandType.CLOSE_SYMBOL,
                    symbol=symbol,
                    raw_text=text,
                )

        # MOVE SL <PRICE>
        sl_match = re.match(
            r"^MOVE\s+SL\s+([\d]+(?:\.[\d]+)?)$", cleaned
        )
        if sl_match:
            price = float(sl_match.group(1))
            return ManagementCommand(
                command_type=CommandType.MOVE_SL,
                price=price,
                raw_text=text,
            )

        # Not a management command
        return None
