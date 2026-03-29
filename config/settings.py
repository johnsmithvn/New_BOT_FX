"""
config/settings.py

Load environment variables and provide typed config access.
Validates required settings on startup.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
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
    source_chats: list[str | int]
    admin_chat: str | int
    session_reset_hours: int
    bot_token: str              # Bot API token from @BotFather
    bot_admin_id: int           # Numeric Telegram user ID for security


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
    max_spread_pips: float         # XAUUSD: 5 pips = $0.50
    max_open_trades: int
    pending_order_ttl_minutes: int
    signal_age_ttl_seconds: int
    max_entry_distance_pips: float  # XAUUSD: 50 pips = $5.00
    max_entry_drift_pips: float    # tight drift guard for MARKET orders
    # Daily Risk Guard (P4)
    max_daily_trades: int          # 0 = disabled
    max_daily_loss_usd: float      # 0.0 = disabled
    max_consecutive_losses: int    # 0 = disabled
    daily_risk_poll_minutes: int
    # Exposure Guard (P5)
    max_same_symbol_trades: int    # 0 = disabled
    max_correlated_trades: int     # 0 = disabled
    correlation_groups: str        # colon-separated groups, comma-separated
    # Position Manager (P5)
    breakeven_trigger_pips: float  # 0 = disabled
    breakeven_lock_pips: float     # pips above entry to lock SL
    trailing_stop_pips: float      # 0 = disabled
    partial_close_percent: int     # 0 = disabled; % of volume at TP1
    partial_close_trigger_pips: float  # 0 = disabled; pips of profit to trigger auto partial close
    partial_close_lot: float           # fixed lot to close when trigger_pips reached; 0 = use percent mode
    position_manager_poll_seconds: int


@dataclass(frozen=True)
class LogConfig:
    level: str
    file: str
    rotation: str


@dataclass(frozen=True)
class ParserConfig:
    max_message_length: int


@dataclass(frozen=True)
class ExecutionConfig:
    bot_magic_number: int
    deviation_points: int
    market_tolerance_points: float
    max_retries: int
    retry_delay_seconds: float
    watchdog_interval_seconds: int
    watchdog_max_reinit: int
    lifecycle_check_interval_seconds: int
    dynamic_deviation_multiplier: float  # 0 = disabled, e.g. 1.5
    trade_tracker_poll_seconds: int      # 0 = disabled


@dataclass(frozen=True)
class RuntimeConfig:
    dry_run: bool
    alert_cooldown_seconds: int
    circuit_breaker_threshold: int
    circuit_breaker_cooldown: int
    storage_retention_days: int
    heartbeat_interval_minutes: int  # heartbeat frequency; 0 = disabled
    debug_signal_decision: bool      # send pipeline debug to admin Telegram


@dataclass(frozen=True)
class Settings:
    telegram: TelegramConfig
    mt5: MT5Config
    risk: RiskConfig
    safety: SafetyConfig
    log: LogConfig
    parser: ParserConfig
    execution: ExecutionConfig
    runtime: RuntimeConfig


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

    raw_source = _env_list("TELEGRAM_SOURCE_CHATS")
    
    def _parse_chat(val: str) -> str | int:
        val = val.split('#')[0].strip()
        return int(val) if val.lstrip('-').isdigit() else val

    source_chats = [_parse_chat(c) for c in raw_source]
    admin_chat = _parse_chat(_env("TELEGRAM_ADMIN_CHAT"))

    telegram = TelegramConfig(
        api_id=_env_int("TELEGRAM_API_ID", 0),
        api_hash=_env("TELEGRAM_API_HASH"),
        session_name=_env("TELEGRAM_SESSION_NAME", "forex_bot"),
        phone=_env("TELEGRAM_PHONE"),
        source_chats=source_chats,
        admin_chat=admin_chat,
        session_reset_hours=_env_int("SESSION_RESET_HOURS", 12),
        bot_token=_env("TELEGRAM_BOT_TOKEN", ""),
        bot_admin_id=_env_int("TELEGRAM_BOT_ADMIN_ID", 0),
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
        max_spread_pips=_env_float("MAX_SPREAD_PIPS", 5.0),
        max_open_trades=_env_int("MAX_OPEN_TRADES", 5),
        pending_order_ttl_minutes=_env_int("PENDING_ORDER_TTL_MINUTES", 15),
        signal_age_ttl_seconds=_env_int("SIGNAL_AGE_TTL_SECONDS", 60),
        max_entry_distance_pips=_env_float("MAX_ENTRY_DISTANCE_PIPS", 50.0),
        max_entry_drift_pips=_env_float("MAX_ENTRY_DRIFT_PIPS", 10.0),
        max_daily_trades=_env_int("MAX_DAILY_TRADES", 0),
        max_daily_loss_usd=_env_float("MAX_DAILY_LOSS", 0.0),
        max_consecutive_losses=_env_int("MAX_CONSECUTIVE_LOSSES", 0),
        daily_risk_poll_minutes=_env_int("DAILY_RISK_POLL_MINUTES", 5),
        max_same_symbol_trades=_env_int("MAX_SAME_SYMBOL_TRADES", 0),
        max_correlated_trades=_env_int("MAX_CORRELATED_TRADES", 0),
        correlation_groups=_env("CORRELATION_GROUPS", ""),
        breakeven_trigger_pips=_env_float("BREAKEVEN_TRIGGER_PIPS", 0.0),
        breakeven_lock_pips=_env_float("BREAKEVEN_LOCK_PIPS", 2.0),
        trailing_stop_pips=_env_float("TRAILING_STOP_PIPS", 0.0),
        partial_close_percent=_env_int("PARTIAL_CLOSE_PERCENT", 0),
        partial_close_trigger_pips=_env_float("PARTIAL_CLOSE_TRIGGER_PIPS", 0.0),
        partial_close_lot=_env_float("PARTIAL_CLOSE_LOT", 0.0),
        position_manager_poll_seconds=_env_int("POSITION_MANAGER_POLL_SECONDS", 5),
    )

    log = LogConfig(
        level=_env("LOG_LEVEL", "INFO"),
        file=_env("LOG_FILE", "logs/bot.log"),
        rotation=_env("LOG_ROTATION", "10 MB"),
    )

    parser = ParserConfig(
        max_message_length=_env_int("MAX_MESSAGE_LENGTH", 2000),
    )

    execution = ExecutionConfig(
        bot_magic_number=_env_int("BOT_MAGIC_NUMBER", 234000),
        deviation_points=_env_int("DEVIATION_POINTS", 20),
        market_tolerance_points=_env_float("MARKET_TOLERANCE_POINTS", 5.0),
        max_retries=_env_int("ORDER_MAX_RETRIES", 3),
        retry_delay_seconds=_env_float("ORDER_RETRY_DELAY_SECONDS", 1.0),
        watchdog_interval_seconds=_env_int("WATCHDOG_INTERVAL_SECONDS", 30),
        watchdog_max_reinit=_env_int("WATCHDOG_MAX_REINIT", 5),
        lifecycle_check_interval_seconds=_env_int("LIFECYCLE_CHECK_INTERVAL_SECONDS", 30),
        dynamic_deviation_multiplier=_env_float("DYNAMIC_DEVIATION_MULTIPLIER", 0.0),
        trade_tracker_poll_seconds=_env_int("TRADE_TRACKER_POLL_SECONDS", 30),
    )

    _dry_run_raw = _env("DRY_RUN", "false").lower()
    _debug_raw = _env("DEBUG_SIGNAL_DECISION", "false").lower()
    runtime = RuntimeConfig(
        dry_run=_dry_run_raw in ("true", "1", "yes"),
        alert_cooldown_seconds=_env_int("ALERT_COOLDOWN_SECONDS", 300),
        circuit_breaker_threshold=_env_int("CIRCUIT_BREAKER_THRESHOLD", 3),
        circuit_breaker_cooldown=_env_int("CIRCUIT_BREAKER_COOLDOWN", 300),
        storage_retention_days=_env_int("STORAGE_RETENTION_DAYS", 30),
        heartbeat_interval_minutes=_env_int("HEARTBEAT_INTERVAL_MINUTES", 30),
        debug_signal_decision=_debug_raw in ("true", "1", "yes"),
    )

    return Settings(
        telegram=telegram,
        mt5=mt5,
        risk=risk,
        safety=safety,
        log=log,
        parser=parser,
        execution=execution,
        runtime=runtime,
    )
