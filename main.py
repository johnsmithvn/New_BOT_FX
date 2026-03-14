"""
main.py

Startup orchestration for telegram-mt5-bot.
- Load config
- Init logger
- Init storage
- Init parser pipeline
- Start Telegram listener (P2)
"""

from __future__ import annotations

import sys

from config.settings import load_settings
from core.signal_parser.parser import SignalParser
from core.signal_validator import SignalValidator
from core.risk_manager import RiskManager
from core.storage import Storage
from utils.logger import setup_logger, log_event
from utils.symbol_mapper import SymbolMapper


def main() -> None:
    """Initialize and start the bot."""

    # 1. Load settings
    settings = load_settings()

    # 2. Init logger
    setup_logger(
        level=settings.log.level,
        file_path=settings.log.file,
        rotation=settings.log.rotation,
    )

    log_event("system_startup", symbol="", fingerprint="")

    # 3. Init storage
    storage = Storage()

    # 4. Init parser pipeline
    mapper = SymbolMapper()
    parser = SignalParser(
        symbol_mapper=mapper,
        max_message_length=settings.parser.max_message_length,
    )

    # 5. Init validator
    validator = SignalValidator(
        max_entry_distance_points=settings.safety.max_entry_distance_points,
        signal_age_ttl_seconds=settings.safety.signal_age_ttl_seconds,
    )

    # 6. Init risk manager
    risk_manager = RiskManager(
        mode=settings.risk.mode,
        fixed_lot_size=settings.risk.fixed_lot_size,
        risk_percent=settings.risk.risk_percent,
        lot_min=settings.risk.lot_min,
        lot_max=settings.risk.lot_max,
        lot_step=settings.risk.lot_step,
    )

    print("=" * 50)
    print("  telegram-mt5-bot  v0.1.0")
    print("=" * 50)
    print(f"  Risk mode  : {settings.risk.mode}")
    print(f"  Max spread : {settings.safety.max_spread_points} pts")
    print(f"  Signal TTL : {settings.safety.signal_age_ttl_seconds}s")
    print(f"  Pending TTL: {settings.safety.pending_order_ttl_minutes}min")
    print("=" * 50)

    # TODO: P2 — Init MT5 connection
    # TODO: P2 — Start Telegram listener
    # TODO: P2 — Wire parser → validator → risk_manager → order_builder → executor

    log_event("system_ready", symbol="", fingerprint="")
    print("\n[INFO] System initialized. Telegram listener not yet wired (P2).")
    print("[INFO] Use tools/parse_cli.py to test the parser pipeline.")


if __name__ == "__main__":
    main()
