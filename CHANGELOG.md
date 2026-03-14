# CHANGELOG

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
