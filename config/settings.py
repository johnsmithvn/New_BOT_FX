"""
config/settings.py

Load environment variables and provide typed config access.
Validates required settings on startup.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _env(key: str, default: str | None = None, required: bool = False) -> str:
    """Read an env var, fail fast if required and missing."""
    value = os.getenv(key, default)
    if required and not value:
        print(f"FATAL: missing required env variable: {key}")
        sys.exit(1)
    return value or ""


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, str(default))
    try:
        return int(raw)
    except ValueError:
        print(f"FATAL: env variable {key} must be integer, got: {raw}")
        sys.exit(1)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key, str(default))
    try:
        return float(raw)
    except ValueError:
        print(f"FATAL: env variable {key} must be float, got: {raw}")
        sys.exit(1)


def _env_list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int
    api_hash: str
    session_name: str
    phone: str
    source_chats: list[str]


@dataclass(frozen=True)
class MT5Config:
    path: str
    login: int
    password: str
    server: str


@dataclass(frozen=True)
class RiskConfig:
    mode: str  # FIXED_LOT or RISK_PERCENT
    fixed_lot_size: float
    risk_percent: float
    lot_min: float
    lot_max: float
    lot_step: float


@dataclass(frozen=True)
class SafetyConfig:
    max_spread_points: int
    max_open_trades: int
    pending_order_ttl_minutes: int
    signal_age_ttl_seconds: int
    max_entry_distance_points: int


@dataclass(frozen=True)
class LogConfig:
    level: str
    file: str
    rotation: str


@dataclass(frozen=True)
class ParserConfig:
    max_message_length: int


@dataclass(frozen=True)
class Settings:
    telegram: TelegramConfig
    mt5: MT5Config
    risk: RiskConfig
    safety: SafetyConfig
    log: LogConfig
    parser: ParserConfig


def load_settings(env_path: str | Path | None = None) -> Settings:
    """Load and validate all settings from .env file.

    Args:
        env_path: Optional explicit path to .env file.
                  Defaults to .env in project root.
    """
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()

    telegram = TelegramConfig(
        api_id=_env_int("TELEGRAM_API_ID", 0),
        api_hash=_env("TELEGRAM_API_HASH"),
        session_name=_env("TELEGRAM_SESSION_NAME", "forex_bot"),
        phone=_env("TELEGRAM_PHONE"),
        source_chats=_env_list("TELEGRAM_SOURCE_CHATS"),
    )

    mt5 = MT5Config(
        path=_env("MT5_PATH"),
        login=_env_int("MT5_LOGIN", 0),
        password=_env("MT5_PASSWORD"),
        server=_env("MT5_SERVER"),
    )

    risk = RiskConfig(
        mode=_env("RISK_MODE", "FIXED_LOT"),
        fixed_lot_size=_env_float("FIXED_LOT_SIZE", 0.01),
        risk_percent=_env_float("RISK_PERCENT", 1.0),
        lot_min=_env_float("LOT_MIN", 0.01),
        lot_max=_env_float("LOT_MAX", 100.0),
        lot_step=_env_float("LOT_STEP", 0.01),
    )

    safety = SafetyConfig(
        max_spread_points=_env_int("MAX_SPREAD_POINTS", 50),
        max_open_trades=_env_int("MAX_OPEN_TRADES", 5),
        pending_order_ttl_minutes=_env_int("PENDING_ORDER_TTL_MINUTES", 15),
        signal_age_ttl_seconds=_env_int("SIGNAL_AGE_TTL_SECONDS", 60),
        max_entry_distance_points=_env_int("MAX_ENTRY_DISTANCE_POINTS", 500),
    )

    log = LogConfig(
        level=_env("LOG_LEVEL", "INFO"),
        file=_env("LOG_FILE", "logs/bot.log"),
        rotation=_env("LOG_ROTATION", "10 MB"),
    )

    parser = ParserConfig(
        max_message_length=_env_int("MAX_MESSAGE_LENGTH", 2000),
    )

    return Settings(
        telegram=telegram,
        mt5=mt5,
        risk=risk,
        safety=safety,
        log=log,
        parser=parser,
    )
