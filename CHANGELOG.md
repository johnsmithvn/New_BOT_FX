# CHANGELOG

## 0.5.2 - 2026-03-15

### Added
- Signal debug messages: stream detailed decision logs directly to admin Telegram chat
- Configurable via `DEBUG_SIGNAL_DECISION` flag in `.env`
- Added `send_debug_sync` and `send_debug` to `TelegramAlerter` — deliberately bypasses standard alert cooldowns to ensure every signal gets logged
- Triggers at 3 key pipeline points in `main.py`:
  - `Validation FAIL`: logs raw, parsed text, market prices, and specific rule failure reason
  - `Entry drift FAIL`: logs rejection for market order drift
  - `Order decision SUCCESS`: logs exact volume, order type (MARKET/LIMIT/STOP), and deviation used
- Documentation: `docs/DEBUG_SIGNAL.md`

## 0.5.1 - 2026-03-15

### Fixed
- **CRITICAL**: `core/exposure_guard.py` — `_get_open_positions()` was directly importing `MetaTrader5` and calling `mt5.positions_get()`, bypassing the injected `TradeExecutor`. Now delegates to `TradeExecutor.get_position_symbols()`.
- **CRITICAL**: `core/order_builder.py` — `build_request()` used `self._base_deviation` (hardcoded base), making `compute_deviation()` and `DYNAMIC_DEVIATION_MULTIPLIER` dead code. Now calls `compute_deviation(spread_points)` for effective dynamic deviation.

### Changed
- `core/trade_executor.py` — added `get_position_symbols()` method for `ExposureGuard` to query positions through the executor abstraction
- `core/order_builder.py` — `build_request()` accepts `spread_points` parameter
- `main.py` — passes `spread_points` to `order_builder.build_request()`
- `docs/logic/LOGIC_PIPELINE_DEEP_DIVE.md` — synced with v0.5.1 pipeline: added Step 0 (command intercept), Step 2b (daily risk guard), Step 2c (exposure guard), Step 8b (entry drift guard), dynamic deviation in Step 8, updated ENV table (22 vars), added 11-layer safety note

## 0.5.0 - 2026-03-15

### Added
- `core/exposure_guard.py` — per-symbol and per-correlation-group position limits
  - `MAX_SAME_SYMBOL_TRADES`: max open positions on same symbol (default 0 = disabled)
  - `MAX_CORRELATED_TRADES`: max open across correlation group (default 0 = disabled)
  - `CORRELATION_GROUPS`: configurable groups (e.g., `XAUUSD:XAGUSD,EURUSD:GBPUSD`)
- `core/position_manager.py` — background position management (all disabled by default)
  - Breakeven: move SL to entry + lock pips when profit reaches trigger
  - Trailing stop: trail SL at fixed pip distance
  - Partial close: close percentage of volume at TP1
- `core/command_parser.py` — parse Telegram management commands
  - Supports: `CLOSE ALL`, `CLOSE <SYMBOL>`, `CLOSE HALF`, `MOVE SL <PRICE>`, `BREAKEVEN`
- `core/command_executor.py` — execute management commands against MT5
- Dynamic deviation in `core/order_builder.py`: `DYNAMIC_DEVIATION_MULTIPLIER` (default 0 = use fixed)
- 10 new env keys in `.env.example` for exposure guard, position manager, dynamic deviation

### Changed
- `main.py` — v0.5.0 banner, Step 0 command intercept, Step 2c exposure guard, position manager lifecycle
- `config/settings.py` — `SafetyConfig` and `ExecutionConfig` extended with P5 fields
- `docs/ARCHITECTURE.md` — added P5 module entries
- `docs/MONITORING.md` — added log rotation validation section
- `docs/DEPLOY.md` — enhanced update procedure with state preservation + rollback
- `docs/PLAN.md` — P4 complete, P5 in progress


### Added
- `core/daily_risk_guard.py` — poll-based daily risk limits using MT5 `history_deals_get()`
  - `MAX_DAILY_TRADES`: max closed deals per UTC day (default 0 = disabled)
  - `MAX_DAILY_LOSS`: max realized loss USD per UTC day (default 0.0 = disabled)
  - `MAX_CONSECUTIVE_LOSSES`: pause after N consecutive losing deals (default 0 = disabled)
  - Background poll every `DAILY_RISK_POLL_MINUTES` (default 5)
  - Telegram alert on first breach per day
- Startup position sync: `_sync_positions_on_startup()` logs audit of pre-existing MT5 state
  - Warns if open positions >= `MAX_OPEN_TRADES`
  - Sends Telegram alert if at capacity
- Daily guard stats in heartbeat: `daily_trades`, `daily_loss`, `consec_losses`
- `docs/DEPLOY.md` — Ubuntu VPS deployment runbook (Wine + MT5, systemd, first-run auth, maintenance)
- `deploy/telegram-mt5-bot.service` — systemd unit with `Restart=always`, security hardening
- `docs/MONITORING.md` — alert catalog (10 types), heartbeat interpretation, debug workflow, escalation playbook
- 4 new env keys in `.env.example`: `MAX_DAILY_TRADES`, `MAX_DAILY_LOSS`, `MAX_CONSECUTIVE_LOSSES`, `DAILY_RISK_POLL_MINUTES`

### Changed
- `main.py` — v0.4.0 banner, DailyRiskGuard integration (Step 2b), startup position sync, heartbeat daily stats
- `config/settings.py` — `SafetyConfig` extended with daily risk fields (added in prior planning session)
- `docs/ARCHITECTURE.md` — added `core/daily_risk_guard.py` module entry
- `README.md` — bumped to v0.4.0, added Daily Risk Guard + Production Deployment sections, fixed Safety Gates table
- P4 tasks marked complete in `docs/TASKS.md`

## 0.3.4 - 2026-03-15

### Added
- `_SessionMetrics` dataclass in `main.py` — in-memory counters per session: `parsed`, `rejected`, `executed`, `failed`
- Execution latency tracking: `avg_execution_latency_ms` and `max_execution_latency_ms` (recorded only on successfully executed signals)
- `_heartbeat_loop()` background task — fires every `HEARTBEAT_INTERVAL_MINUTES` (default 30, set 0 to disable)
- `_emit_heartbeat()` — rich status line: uptime, session counters, avg/max latency, `open_positions`, `pending_orders`, `mt5=OK/FAIL`, `telegram=OK/FAIL`
- Session summary on graceful shutdown — `[SESSION]` line with full metrics
- `HEARTBEAT_INTERVAL_MINUTES` to `RuntimeConfig` and `.env.example`
- `TradeExecutor.is_connected` property — lightweight MT5 health check via `account_info()`
- `TradeExecutor.orders_total()` — returns count of active pending orders from MT5
- `TelegramListener.is_connected` property — checks `client.is_connected()`

### Changed
- P3 → `complete`, P4 → `in progress` in `docs/PLAN.md`
- `docs/TASKS.md` regenerated for P4 with full task list (VPS runbook, daily risk guard with `MAX_CONSECUTIVE_LOSSES`, startup position sync, monitoring doc)
- Version banner bumped to `v0.3.4`


## 0.3.3 - 2026-03-15

### Added
- Entry drift guard: `MAX_ENTRY_DRIFT_PIPS=10.0` — tight safety gate for MARKET orders, rejects when entry price has drifted too far from signal intent
- `signal_validator.py` — new public `validate_entry_drift()` method
- `main.py` — Step 8b: drift check after order type decision, before execution
- Execution timing: `latency_ms` in all pipeline summary outputs
- `TASKS.md` — P4/P5 backlog items (daily risk guard, position manager, management commands, etc.)

### Changed
- Re-enabled Rule 5 (entry distance check) — was commented out
- `config/settings.py` — added `max_entry_drift_pips` to SafetyConfig
- `.env.example` — added `MAX_ENTRY_DRIFT_PIPS`
- `ARCHITECTURE.md` — documented two-tier distance protection

### Fixed
- `.env` — fixed stale naming (`MAX_SPREAD_POINTS`→`MAX_SPREAD_PIPS`, `MAX_ENTRY_DISTANCE_POINTS`→`MAX_ENTRY_DISTANCE_PIPS`)
- `.env` — added missing Trade Execution + Runtime sections (was incomplete vs `.env.example`)

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
