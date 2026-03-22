# CHANGELOG

## 0.14.1 - 2026-03-22

### Fixed
- **R3**: `self.position_manager` → `self.position_mgr` — 13 references in main.py caused AttributeError (edit/delete/reply all broken)
- **R2**: orders table missing `symbol` column — added V5 migration, fixed reply-command query crash
- **R1**: single-mode execution now persists to orders table — fixes TradeTracker matching and PnL replies
- **R4**: `_restore_groups_from_db()` deferred to after `init_mt5()` — prevents stale group cleanup on restart
- **R5**: TradeTracker strips sub-fingerprint (`:L0`) before signal lookup — fixes PnL replies for multi-order trades
- **R9**: TradeTracker polls immediately on startup instead of waiting `poll_seconds`
- **R7**: Dashboard `_query()` only suppresses "no such table" errors (was swallowing all OperationalError)
- **R6**: Dashboard footer version updated to v0.14.0 (was hardcoded v0.12.0)
- **R10**: DASHBOARD.md API reference corrected for `/api/channel-list` response format
- **R8**: Added `config/channels.json` to `.gitignore`

## 0.14.0 - 2026-03-22

### Added
- **P13: Bot Hardening & Reliability**
  - Health check HTTP endpoint (`/health` on port 8080) — uptime, MT5 status, signal/order/error counters, circuit breaker state
  - Runtime health stats tracker (`HealthStats`) — daily auto-reset counters, status computation (healthy/degraded/unhealthy)
  - Watchdog → health stats bridge — MT5 connection status feeds into health endpoint in real-time
  - Circuit breaker → health stats bridge — CB state changes reflected in `/health` response
  - Signal/order/error tracking wired throughout the pipeline

### Changed
- `MT5Watchdog` now accepts `on_health_update` callback (non-breaking, optional param)
- Environment variable `HEALTH_CHECK_PORT` configures health server port (default 8080)

## 0.13.0 - 2026-03-22

### Added
- **P12: Dashboard Enhancement**
  - Channel name mapping — channel IDs now show human-readable names from `channels.json`
  - Equity curve chart — cumulative PnL over time (line chart with gradient fill)
  - Win rate by symbol chart — horizontal bar with color coding (green ≥60%, orange ≥45%, red <45%)
  - CSV export — download all trades as CSV with channel names, filterable by date/channel
  - Basic HTTP auth — `DASHBOARD_PASSWORD` env var protects page access
  - 3 new API endpoints: `/api/equity-curve`, `/api/symbol-stats`, `/api/export/csv`
  - `/api/channel-list` now returns `{id, name}` objects

### Changed
- All API responses now include `channel_name` field alongside `channel_id`
- Dashboard version bumped to 0.13.0

## 0.12.0 - 2026-03-21

### Added
- **P11: Web Analytics Dashboard** — separate FastAPI process for trade analytics
  - `dashboard/db/queries.py`: Read-only SQL aggregation (overview, daily PnL, channel stats, paginated trades, active groups)
  - `dashboard/api/routes.py`: 7 REST API endpoints with FastAPI dependency injection
  - `dashboard/dashboard.py`: FastAPI app with CORS, API key middleware, Jinja2 templates
  - `dashboard/templates/`: 3 pages — Overview (stat cards, charts), Channels (cards, comparison), Trades (filters, pagination)
  - `dashboard/static/`: Dark theme CSS (glassmorphism, responsive), Chart.js utilities, auto-refresh 30s
- New dependencies: `fastapi`, `uvicorn`, `jinja2`

## 0.11.0 - 2026-03-21

### Added
- **P10.1: MessageDeleted listener** — `telegram_listener.py` now listens for `events.MessageDeleted`, forwarding to `_process_delete()` which cancels pending orders from deleted signals
- **P10.1: `cancel_group_pending_orders()`** — new PositionManager method to cancel all unfilled pending orders in a group while keeping filled positions running
- **P10.1: `CANCEL_GROUP_PENDING` action** — new UpdateAction in `MessageUpdateHandler` for signals with mixed state (some filled, some pending)

### Changed
- **`message_update_handler.py`** — `handle_edit()` now accepts `has_filled_orders` param; uses MT5 position check instead of blind CANCEL_ORDER; removed stale TODO
- **`main.py`** `_process_edit()` — group-aware: checks PositionManager for filled orders before deciding action; routes to `cancel_group_pending_orders()` for groups
- **`telegram_listener.py`** — added `DeleteCallback` type, `set_delete_callback()`, and `events.MessageDeleted` handler registration

## 0.10.1 - 2026-03-21

### Fixed
- **Swallowed exception** in `main.py:691` — pip_size calculation now logs warning + uses fallback instead of `except: pass`
- **Swallowed exception** in `circuit_breaker.py:111` — state change callback errors now logged instead of silently ignored

### Removed
- 6 unused imports: `field` (settings.py), `Settings` TYPE_CHECKING (command_executor.py), `timezone` (message_update_handler.py, storage.py), `json`/`Side`/`SignalLifecycle`/`SignalStatus` (pipeline.py)
- 5 dead functions (grep-verified 0 callers): `check_symbol()` (trade_executor.py), `cleanup_debounce()` (range_monitor.py), `expire_active_signals()` (storage.py), `is_known_channel()` + `get_all_channel_ids()` (channel_manager.py)

### Changed
- **README.md**: Updated to v0.10.0, added P9/P10 modules to project structure, updated pipeline flow, reply docs, customization guide
- **PROJECT.md**: Updated to v0.10.0, added P10 group management features
- **ROADMAP.md**: Added R8 milestone (Smart Signal Group Management)

## 0.10.0 - 2026-03-21

### Added
- **P10: Smart Signal Group Management** — every signal creates a managed order group
- `core/models.py` — `OrderGroup` dataclass and `GroupStatus` enum for group lifecycle
- `core/position_manager.py` — Group-aware position management:
  - `_check_positions()` routes to group vs individual management
  - `register_group()` creates groups from pipeline results
  - `add_order_to_group()` for re-entry orders from RangeMonitor
  - `_manage_group()` with group trailing SL, zone SL, and auto-BE
  - `_calculate_group_sl()` — multi-source SL calculation (zone, signal, fixed, trail)
  - `_modify_group_sl()` — applies SL to ALL tickets atomically
  - `close_selective_entry()` — strategy-based single order close from reply
  - `apply_group_be()` — auto-breakeven after partial group close
  - `get_group()`, `get_group_by_ticket()`, `get_group_status()` — query methods
- `core/pipeline.py` — `_register_group_from_results()` called after every execution
- `core/order_builder.py` — `order_types_allowed` filter (P10d):
  - STOP not allowed → MARKET (if price in zone) or LIMIT at zone midpoint
- `core/storage.py` — Migration V4: `signal_groups` table for restart recovery
  - `store_group()`, `get_active_groups()`, `update_group_sl()`, `update_group_tickets()`, `complete_group_db()`
- `config/channels.example.json` — 6 new config fields:
  - `group_trailing_pips`, `group_be_on_partial_close`, `reply_close_strategy`
  - `sl_mode` (`signal`/`zone`/`fixed`), `sl_max_pips_from_zone`, `order_types_allowed`

### Changed
- `main.py` — Reply handler intercepts CLOSE for groups with selective strategy
- `core/position_manager.py` — Per-position logic extracted to `_manage_individual()`
- Cleanup task now includes `signal_groups` table

## 0.9.0 - 2026-03-21

### Added
- **Channel-driven strategy architecture** (P9) — multi-order per signal with per-channel strategy config
- `core/entry_strategy.py` — generate multi-entry plans from signal + strategy config
  - Strategy modes: `single` (backward-compat), `range` (N orders across entry zone), `scale_in` (stepped re-entries)
  - Volume split: `equal`, `pyramid`, `risk_based` (weighted by SL distance per entry)
- `core/signal_state_manager.py` — active signal lifecycle tracking
  - State machine: PENDING → PARTIAL → COMPLETED → EXPIRED
  - DB-backed persistence for restart recovery
- `core/pipeline.py` — sole orchestrator for multi-order execution
  - `execute_signal_plans()` replaces single-order execute path
  - `handle_reentry()` with full risk guard gauntlet (circuit breaker, daily guard, exposure guard)
- `core/range_monitor.py` — background price-cross re-entry trigger
  - Price-cross detection (not proximity — only triggers on actual crossing)
  - 30-second debounce per level to prevent order spam
- **Order fingerprint v2**: `base_fp:L{N}` — unique per order, debuggable, linkable via base_fp
- `core/models.py` — `EntryPlan`, `SignalState`, `SignalLifecycle` enum, `order_fingerprint()`
- Storage migration V3: `active_signals` table with status/plans/expiry tracking
- `channels.json` schema expanded: `strategy`, `risk`, `validation` sections per channel
- Index `idx_orders_source_msg` on `(source_chat_id, source_message_id)` for P9 reply handler

### Changed
- `core/channel_manager.py` — `get_strategy()`, `get_risk_config()`, `get_validation_config()` with `_get_section()` DRY pattern
- `core/storage.py` — `get_orders_by_message()` now uses direct source_message_id join (supports sub-fingerprints), with fallback to old fingerprint JOIN for pre-P9 orders
- `config/channels.example.json` — updated with full strategy/risk/validation example

## 0.8.1 - 2026-03-18

### Fixed
- **CRITICAL**: Reply management completely broken — `orders.fingerprint` stored as truncated 12-char string while `signals.fingerprint` stored as full 16-char string, causing JOIN in `get_orders_by_message()` to never match. All reply actions (close, SL, TP, BE) were non-functional since v0.6.0. Fix: `fp` now uses full fingerprint for all DB operations, `fp_short` for console display only.
- Signal debug messages now sent on **parse failures** — previously only triggered after successful parse
- Market data section skipped in debug message when no market data available (parse fail stage)

## 0.8.0 - 2026-03-18

### Added
- Reply-based signal management: channel admin replies to signal → bot acts on specific trade(s)
- `reply_action_parser.py` — parse reply text (close/exit/đóng, SL/TP {price}, BE, close N%)
- `reply_command_executor.py` — per-ticket MT5 operations with position existence check
- Multi-order support: all orders from a signal are actioned, results grouped
- Channel guard: cross-channel reply prevention
- Symbol consistency check before execution
- TradeTracker PnL reply suppression for reply-closed tickets (5 min TTL)
- "No active trade found" UX feedback for replies to non-signal messages
- Percent range validation (1-100) for partial close

### Changed
- `telegram_listener.py` — new `ReplyCallback`, detects `reply_to_msg_id`, early return (no signal parser fallthrough)
- `storage.py` — `get_orders_by_message()` returns list of all orders for a signal
- `trade_tracker.py` — `_reply_closed` dict with TTL, `mark_reply_closed()`, `_is_reply_closed()` with auto-cleanup

## 0.7.1 - 2026-03-17

### Added
- Command response via Telegram: reply to source chat + admin log
- Position manager Telegram alerts: breakeven, trailing stop, partial close with channel context
- Per-ticket alert throttle (60s cooldown per event_type)
- Trailing stop delta threshold: only alert if SL moved ≥ 5 pips

### Changed
- `telegram_alerter.py` — `parse_mode="md"` on all `send_message` calls for proper markdown rendering

## 0.7.0 - 2026-03-17

### Added
- `store_event()` calls in pipeline now include `channel_id` — all 11 call sites wired (2 parse-fail, 9 post-parse)
- `Storage.get_fingerprint_by_message()` — lookup fingerprint by `(source_chat_id, source_message_id)`
- `OrderLifecycleManager.cancel_by_fingerprint()` — cancel pending order by matching fingerprint in comment field
- Per-channel session metrics: `_channel_metrics` dict with lazy-init per-channel `_SessionMetrics`, heartbeat breakdown for multi-channel
- `_SessionMetrics.as_summary()` — one-line per-channel heartbeat output
- `_process_edit()` fully wired: fingerprint lookup → `MessageUpdateHandler.handle_edit()` → cancel/reprocess decision
- TradeTracker partial close reply throttle: 60s cooldown per `position_id` prevents Telegram spam

### Changed
- `main.py` — `_process_edit()` from stub to full implementation with cancel+reprocess flow
- Heartbeat log includes per-channel breakdown when `len(_channel_metrics) > 1`

## 0.6.0 - 2026-03-17

### ⚠️ Breaking Change
- **Fingerprint format changed**: `generate_fingerprint()` now includes `source_chat_id` as first element. Dedup is no longer backward compatible with v0.5.x data. **Backup DB before upgrading.**

### Added
- **Versioned schema migration system** in `core/storage.py` — `schema_versions` table, idempotent migrations safe for repeated restarts
- **`core/channel_manager.py`** — per-channel configuration via `config/channels.json`, rule merging with default fallback
- **`core/trade_tracker.py`** — background deal polling, PnL persistence, Telegram reply under original signal
  - 2-step ticket→position resolution (MARKET + pending order support)
  - Pending fill detection: `DEAL_ENTRY_IN` → `update_position_ticket()`
  - `tracker_state` table for restart recovery (`last_deal_poll_time`)
- **`core/telegram_alerter.py`** — `reply_to_message()` + `reply_to_message_sync()` for trade outcome threading
- DB tables: `trades` (deal_ticket UNIQUE), `tracker_state` (key-value), `schema_versions` (version tracking)
- DB columns: `orders.channel_id`, `orders.source_chat_id`, `orders.source_message_id`, `orders.position_ticket`, `events.channel_id`
- 8 new `Storage` methods: `store_trade()`, `get_open_tickets()`, `get_signal_reply_info()`, `update_position_ticket()`, `get/set_tracker_state()`, `get_order_by_ticket/position_ticket()`
- `ParsedSignal.parse_confidence` + `ParsedSignal.parse_source` fields
- `TRADE_TRACKER_POLL_SECONDS` env key (default 30, 0 = disabled)
- `config/channels.example.json` — per-channel rule template

### Changed
- `core/position_manager.py` — accepts `ChannelManager` + `Storage`, per-channel breakeven/trailing/partial rules, ticket→channel cache with startup rebuild
- `core/storage.py` — `store_order()` and `store_event()` accept channel context params
- `main.py` — wires `ChannelManager`, `TradeTracker`, passes channel context through pipeline, `register_ticket()` on execution
- `config/settings.py` — `trade_tracker_poll_seconds` in `ExecutionConfig`

## 0.5.5 - 2026-03-18

### Added
- **Entry Range Parsing**: `SignalParser` now accurately parses signal ranges (e.g., `Buy Gold 5162 - 5170` or `BUY GOLD zone 4963 - 4961 now`).
  - Supports multiple optional words between side keyword and price (e.g., `GOLD ZONE`).
  - Supports `-`, `/`, `–` (em-dash), and `TO` as range separators.
  - Automatically identifies extreme bounds `[low, high]`.
  - Determines final execution `entry` strictly by `Side` (uses lowest for `BUY` and highest for `SELL`).

### Changed
- **Strict Entry Enforcement**: If the parser cannot identify a single entry price and no explicit `MARKET` intent (like `NOW` or `CMP`) is passed, the signal is now explicitly REJECTED as a `ParseFailure` instead of wrongly defaulting to a market execution.
- **Relative TP Filtering**: `tp_detector` now skips TP values followed by `PIPS`/`POINTS`/`PTS` — these are relative offsets from entry, not absolute price levels. Signals like `TP: 30 pips – 50 pips` correctly return `tp=[]`.
- **Market Keyword Priority**: Market keywords (`NOW`, `CMP`, etc.) are now checked **last** in the entry detection chain, ensuring numeric entry/range detection always takes priority.

## 0.5.4 - 2026-03-15

### Fixed
- **CRITICAL**: Fixed Telethon `get_entity` failures by resolving `TELEGRAM_ADMIN_CHAT` and `TELEGRAM_SOURCE_CHATS` string IDs to integers. Previously, integer IDs like `"6638536622   #@ShuMaou"` passed from `.env` caused Telethon to attempt (and fail) to resolve them as usernames because `python-dotenv` string typing retained inline comments. These are now stripped and purely numerical sequences are properly coerced into correct Python `int` objects.

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
