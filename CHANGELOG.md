# CHANGELOG

## 0.3.2 - 2026-03-14

### Fixed
- **CRITICAL**: `_validate_entry_distance` was comparing raw price difference against pip-based config — gate was effectively useless for XAUUSD (500 meant $500 instead of 50 pips = $5)

### Changed
- All distance/spread units standardized to **PIPS** (not points)
- `signal_validator.py` — rewritten with `pip_size` param, all thresholds in pips
- `config/settings.py` — `SafetyConfig`: renamed `max_spread_points`→`max_spread_pips` (default 5.0), `max_entry_distance_points`→`max_entry_distance_pips` (default 50.0)
- `.env.example` — renamed `MAX_SPREAD_POINTS`→`MAX_SPREAD_PIPS`, `MAX_ENTRY_DISTANCE_POINTS`→`MAX_ENTRY_DISTANCE_PIPS`, with XAUUSD pip explanations
- `main.py` — resolve `point`/`pip_size` BEFORE validation (was incorrectly after), pass `pip_size` to validator, convert spread points→pips
- `docs/RULES.md` — added §5a "Unit Consistency — Pips vs Points" rule

### ⚠️ Breaking: .env rename required
- `MAX_SPREAD_POINTS=50` → `MAX_SPREAD_PIPS=5.0`
- `MAX_ENTRY_DISTANCE_POINTS=500` → `MAX_ENTRY_DISTANCE_PIPS=50.0`

## 0.3.1 - 2026-03-14

### Changed
- Moved 8 hardcoded trade execution values to `.env`: `BOT_MAGIC_NUMBER`, `DEVIATION_POINTS`, `MARKET_TOLERANCE_POINTS`, `ORDER_MAX_RETRIES`, `ORDER_RETRY_DELAY_SECONDS`, `WATCHDOG_INTERVAL_SECONDS`, `WATCHDOG_MAX_REINIT`, `LIFECYCLE_CHECK_INTERVAL_SECONDS`
- `config/settings.py` — added `ExecutionConfig` dataclass
- `core/order_builder.py` — removed hardcoded `BOT_MAGIC_NUMBER=234000` and `DEFAULT_DEVIATION=20`, now from config
- `main.py` — wires all ExecutionConfig values into OrderBuilder, TradeExecutor, MT5Watchdog, OrderLifecycleManager
- `.env.example` — added Trade Execution section with ⚠️ CRITICAL warnings and explanations
- `README.md` — added CRITICAL warning section at top: price reference rule, market tolerance, deviation, risk sizing, all safety gates

## 0.3.0 - 2026-03-14

### Added
- Smart dry-run mode: `DRY_RUN=true` simulates execution with dynamic bid/ask derived from signal entry price
- Circuit breaker: `core/circuit_breaker.py` — CLOSED/OPEN/HALF_OPEN states, pause trading after N consecutive failures
- Telegram alerter: `core/telegram_alerter.py` — rate-limited critical alerts to admin chat
- Pipeline summary logging: one-line console output per signal with outcome
- Signal lifecycle events stored in DB: `signal_received`, `signal_parsed`, `signal_rejected`, `signal_submitted`, `signal_executed`, `signal_failed`
- Background storage cleanup: auto-delete records older than `STORAGE_RETENTION_DAYS`
- Startup self-check: MT5 account info, config summary, component status

### Changed
- `config/settings.py` — added `RuntimeConfig` (DRY_RUN, ALERT_COOLDOWN, CIRCUIT_BREAKER, STORAGE_RETENTION), `TELEGRAM_ADMIN_CHAT`, `SESSION_RESET_HOURS`
- `core/storage.py` — WAL mode, retry on OperationalError, `cleanup_old_records()` method
- `core/telegram_listener.py` — auto-reconnect with exponential backoff, proactive session reset every N hours
- `core/mt5_watchdog.py` — weekend/market-close detection, exponential backoff, alert callbacks
- `main.py` — global exception handling, circuit breaker integration, smart dry-run, pipeline summary, graceful shutdown

## 0.2.0 - 2026-03-14

### Added
- Telegram listener: `core/telegram_listener.py`
- Order builder: `core/order_builder.py` — BUY→ASK / SELL→BID price reference rule
- Trade executor: `core/trade_executor.py` — bounded retry, 35+ retcode mappings
- Order lifecycle manager: `core/order_lifecycle_manager.py`
- MT5 watchdog: `core/mt5_watchdog.py`
- Full pipeline wiring in `main.py`

### Changed
- `core/signal_validator.py` — spread gate, max trades gate, duplicate filter
- `requirements.txt` — pinned `numpy<2`

## 0.1.0 - 2026-03-14

### Added
- Project foundation and configuration
- Signal parser pipeline (7 modules)
- Signal validation, risk management, SQLite storage
- MessageEdited handler prototype, parser CLI, benchmark tool
