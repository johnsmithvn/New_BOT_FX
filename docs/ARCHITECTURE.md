# ARCHITECTURE

## System Overview
- Runtime model: single Python process.
- Unified launcher: `run.py` — menu or CLI mode (`bot`, `dash`, `v2`, `dash+bot`, `v2+bot`).
- Primary flow:
  1. Telegram message received
  2. Message cleaned and parsed
  3. Signal validated and normalized
  4. Order type decided from live price context
  5. Pipeline generates entry plan(s) — single or multi-order
  6. MT5 request built and sent (per plan)
  7. Order group registered in PositionManager
  8. Result persisted and logged

## Core Modules

### `config/settings.py`
- Load env variables via `python-dotenv` and defaults.
- Validate required settings on startup (`_env()` fails fast).
- Provide typed config access via frozen `@dataclass` hierarchy:
  - `TelegramConfig`, `MT5Config`, `RiskConfig`, `SafetyConfig`, `LogConfig`, `ParserConfig`, `ExecutionConfig`, `RuntimeConfig`
  - Top-level `Settings` aggregates all sub-configs.

### `core/models.py`
- Central data contracts for entire signal pipeline.
- Enums: `Side`, `OrderKind`, `SignalStatus`, `SignalLifecycle`, `GroupStatus`.
- Dataclasses:
  - `ParsedSignal` — normalized signal (with `entry_range`, `is_now`, `parse_confidence`, `parse_source`)
  - `ParseFailure` — structured parse error
  - `TradeDecision` — order decision from builder
  - `ExecutionResult` — MT5 execution result
  - `EntryPlan` — one planned entry within a multi-order strategy
  - `SignalState` — runtime lifecycle state for active signals (range/scale_in)
  - `OrderGroup` — group of orders from one signal, managed as a unit (P10)
- Helper: `order_fingerprint(base_fp, level_id)` → `"{base_fp}:L{level_id}"`

### `core/telegram_listener.py`
- Connect to Telegram via Telethon user session.
- Subscribe to configured source chats/channels.
- Forward raw messages to parser pipeline.
- Callbacks: `set_pipeline_callback()`, `set_edit_callback()`, `set_reply_callback()`, `set_delete_callback()`.
- Auto-reconnect with exponential backoff.
- Proactive session reset every `SESSION_RESET_HOURS`.

> **Telegram Access Mode**
>
> The system uses a Telethon user session rather than a Telegram Bot API
> to ensure it can read messages from private groups and signal channels.

### `core/telegram_alerter.py`
- Send critical alerts to admin Telegram chat.
- Rate-limited per `alert_type` with configurable cooldown.
- Methods: `send_alert()`, `send_debug()` (no rate limiting), `reply_to_message()`.
- Sync wrappers: `send_alert_sync()`, `send_debug_sync()`, `reply_to_message_sync()`.
- Admin entity cached (invalidated on client change).

### `core/circuit_breaker.py`
- Circuit breaker pattern for trade execution safety.
- States: `CLOSED` (normal), `OPEN` (paused), `HALF_OPEN` (probe one trade).
- Opens after `failure_threshold` consecutive failures.
- Auto-resets after `cooldown_seconds`.
- State change callbacks for integration with alerter + health stats.

### `core/risk_manager.py`

Responsibilities:
- Determine trade volume (lot size)
- Support fixed lot or risk-based sizing
- Ensure volume respects broker min/max constraints

Inputs:
- account balance
- entry price
- stop loss
- configured risk percent

Outputs:
- trade volume (lot)

### `core/signal_parser/`
- `cleaner.py`: normalize raw text, strip emoji (→ space, not empty).
- `symbol_detector.py`: detect and map symbol aliases.
- `side_detector.py`: detect BUY/SELL/LONG/SHORT + typo-tolerant variants (SEL, BBUY, BYU, etc.).
- `entry_detector.py`: detect explicit entry, entry range (`[low, high]`), or market intent (NOW/CMP). Returns 4-tuple `(entry, entry_range, is_market, is_now)`.
- `sl_detector.py`: detect SL value.
- `tp_detector.py`: detect TP values (`TP`, `TP1`, `TP2`, ...). Filters relative TP (pips/points).
- `parser.py`: orchestrate detectors, produce `ParsedSignal` or `ParseFailure`. Fingerprint includes `source_message_id`.

> **Detector Safety Rule**
>
> Each detector (symbol, side, entry, SL, TP) must handle
> unexpected input safely and must not raise unhandled exceptions.
>
> Detectors should return None or structured failure information
> when parsing fails.

### `core/signal_validator.py`
- Validate required fields and numeric coherence.
- Validate SL/TP relative to entry or market reference.
- Enforce spread threshold and max open trade limit.
- Reject malformed or unsafe signals with explicit reason.
- Two-tier entry distance protection:
  - `MAX_ENTRY_DISTANCE_PIPS` (50) — rejects signals with entry too far from market (all order types).
  - `MAX_ENTRY_DRIFT_PIPS` (10) — tight guard for MARKET orders only, rejects when entry drifted too far.

### `core/order_builder.py`
- Read live bid/ask from MT5 tick.
- Decide order class:
  - BUY: market vs buy limit vs buy stop
  - SELL: market vs sell limit vs sell stop
- Build MT5 request payload (action, type, price, SL, TP, metadata).
- Dynamic deviation: `compute_deviation(spread_points)` widens slippage tolerance
  during high-spread conditions when `DYNAMIC_DEVIATION_MULTIPLIER > 0`.
- **P10d**: `order_types_allowed` filter — when STOP not in allowed list:
  - Price inside zone → MARKET
  - Price outside zone → LIMIT at zone midpoint
  - No zone info → MARKET fallback
- **P1**: `is_now` keyword → force MARKET when price inside entry zone.

> **Price Reference Rule**
>
> Order decision must use correct MT5 reference prices:
>
> BUY orders must compare entry against ASK price.
> SELL orders must compare entry against BID price.
>
> Using BID for BUY decisions or ASK for SELL decisions may lead
> to incorrect order classification and immediate slippage.
>
> Example:
>
> BUY:
>     entry > ask → BUY_STOP
>     entry <= ask → BUY_LIMIT or MARKET
>
> SELL:
>     entry < bid → SELL_STOP
>     entry >= bid → SELL_LIMIT or MARKET

### `core/trade_executor.py`
- Initialize MT5 terminal connection.
- Maintain connection health and expose retry-safe execution.
- Provide position query helpers for exposure guard integration.
- `get_position_symbols()`: list open position symbols (used by ExposureGuard).
- `get_tick()`, `account_info()`, `positions_total()`, `orders_total()`.

### `core/channel_manager.py` (v0.6.0, expanded v0.9.0)
- Load per-channel rules from `config/channels.json`.
- Merge default rules with channel-specific overrides.
- Falls back gracefully if no config file exists.
- Provides `get_rules(chat_id)` for per-channel rule lookup.
- **v0.9.0**: `get_strategy(chat_id)` for entry strategy config (mode, max_entries, volume_split, reentry_step_pips, reentry_tolerance_pips, min_sl_distance_pips, default_sl_pips_from_zone, max_reentry_distance_pips, sl_buffer_pips, max_sl_distance_pips, execute_all_immediately).
- **v0.9.0**: `get_risk_config(chat_id)` and `get_validation_config(chat_id)` for per-channel overrides.

### `core/trade_tracker.py` (v0.6.0)
- Background deal polling via MT5 `history_deals_get()`.
- Track trade outcomes (PnL, commission, swap, close reason).
- 3-step ticket→position resolution: ticket → position_ticket → MT5 `history_orders_get()` fallback.
- Detect pending order fills via `DEAL_ENTRY_IN`.
- Persist `last_deal_poll_time` for restart recovery.
- Dispatch PnL messages via `TelegramAlerter.send_debug()` (admin chat only, not source channel).
- Peak profit integration: includes `peak_pips`, `entry_price` in trade records.
- `get_position_symbols()`: list open position symbols (used by ExposureGuard).

### `core/storage.py`
- SQLite persistence (WAL mode, `check_same_thread=False`) with versioned migration system.
- Retry-safe writes (`_execute_with_retry`) for database locked errors.
- Tables:
  - `signals` — parsed signal fingerprints, status, channel context
  - `orders` — MT5 order audit trail with `channel_id`, `source_chat_id`, `source_message_id`, `symbol`, `volume`, `bid`, `ask`
  - `events` — runtime event records with `channel_id` (v0.7.0)
  - `trades` — trade outcomes: PnL, commission, swap, close reason, `entry_price`, `peak_pips`, `peak_price`, `peak_time` (v0.6.0, expanded v0.22.0)
  - `tracker_state` — key-value persistence for `TradeTracker` poll time (v0.6.0)
  - `schema_versions` — migration version tracking (v0.6.0)
  - `active_signals` — active signal lifecycle state for multi-order strategies (v0.9.0)
  - `signal_groups` — signal group state with `peak_pips`, `peak_price`, `peak_time` for restart recovery (v0.10.0, expanded v0.22.0)
- Fingerprint lookup by message: `get_fingerprint_by_message()` (v0.7.0)
- `get_orders_by_message()` — P9: direct join via `source_message_id` on orders table (supports sub-fingerprints).
- **P10 group persistence**: `store_group()`, `get_active_groups()`, `update_group_sl()`, `update_group_tickets()`, `complete_group_db()`, `reactivate_group_db()`, `update_group_peak()`.
- **Schema migrations** (V1–V7):
  - V1: Multi-channel support columns
  - V2: Trade outcome tracking + tracker state
  - V3: Active signal tracking (P9)
  - V4: Signal groups (P10)
  - V5: Symbol column on orders
  - V6: Peak profit tracking (`peak_pips`, `peak_price`, `peak_time`, `entry_price`)
  - V7: Market snapshot at entry (`orders.volume`, `orders.bid`, `orders.ask`)

### `core/entry_strategy.py` (v0.9.0, updated v0.19.0)
- Generate multi-entry plans from signal + strategy config + live tick.
- Strategy modes: `single` (1:1), `range` (N orders across range), `scale_in` (stepped re-entries).
- **G9**: When `reentry_step_pips > 0`, P2/P3 levels = P1 + N×step (instead of zone-spread).
- Volume split algorithms: `equal`, `pyramid`, `risk_based`, **`per_entry`** (G12a: each plan gets full lot size).
- Uses centralized `estimate_pip_size()` for consistent pip calculation.
- Pure logic only — no execution, no state, no side effects.

### `core/signal_state_manager.py` (v0.9.0)
- Track active signal lifecycle with state machine: PENDING → PARTIAL → COMPLETED → EXPIRED.
- In-memory registry backed by DB persistence for restart recovery.
- Query pending re-entry levels for RangeMonitor.
- Only tracks range/scale_in signals — single mode is fire-and-forget.
- `cancel_all_pending()`: cancel all pending re-entry plans + unfilled MT5 LIMIT/STOP orders (G6).

### `core/pipeline.py` (v0.9.0, updated v0.22.1)
- **SOLE orchestrator** for all order execution.
- `execute_signal_plans()`: replaces steps 7-9 for multi-order support.
- **G2**: Default SL from zone when signal has no SL (`default_sl_pips_from_zone`).
- **Max SL distance cap**: `max_sl_distance_pips` — caps SL when signal SL is too far from entry.
- **SL buffer**: `sl_buffer_pips` — widens SL to avoid spike-triggered hits (original SL only, not generated).
- `handle_reentry()`: callback from RangeMonitor with full risk guard gauntlet:
  - Circuit breaker → Daily guard → Exposure guard → **G1: min_sl_distance** → **G7: max_reentry_distance** → Calculate volume → **G8: Force MARKET** → SL buffer → Execute.
- Delegates to EntryStrategy for plan generation, OrderBuilder for request building.
- `_register_group_from_results()`: registers every signal's orders as a group in PositionManager (P10).
- Responsibility: Strategy generates, Monitor emits, **Pipeline decides**.

### `core/range_monitor.py` (v0.9.0, updated v0.19.0)
- Background asyncio price monitor for re-entry triggers.
- Price-cross detection: triggers only when price **crosses through** a level (individually per plan).
- **G5**: Re-entry tolerance — trigger within N pips of level (`reentry_tolerance_pips`).
- **G11**: SL breach detection — if price crosses SL, cancel ALL pending plans for that signal via `cancel_all_pending()`.
- 30-second debounce per level to prevent spam.
- Symbol-grouped tick requests for efficiency.
- Emits events to Pipeline via callback — never executes orders directly.

### `utils/symbol_mapper.py`
- Map channel symbol aliases to broker symbols.
- Validate mapping availability before execution.
- `SYMBOL_SUFFIX` support: append broker-specific suffix (e.g. `m` for Exness).
- `estimate_pip_size(symbol)`: centralized pip size detection (metals=0.1, JPY=0.01, forex=0.0001). Single source of truth — replaces all `point * 10` heuristics.

### `utils/logger.py`
- Configure console + file logs via `loguru`.
- Emit structured event logs for traceability (`log_event()`).

### `main.py`
- Startup orchestration (via `Bot` class):
  - load config
  - init logger
  - init storage
  - init all components (parser, validator, risk, order builder, executor, circuit breaker, alerter, daily guard, exposure guard, channel manager, position manager, trade tracker, command/reply parsers, signal pipeline, range monitor, health server)
  - start Telegram listener
- Background tasks: heartbeat, storage cleanup, health server.
- Per-channel session metrics: `_SessionMetrics` with parsed/rejected/executed/failed + latency tracking.
- Signal debug to admin Telegram (configurable via `DEBUG_SIGNAL_DECISION`).
- Smart dry-run mode with simulated bid/ask from signal entry.

### `run.py`
- Unified launcher for the entire system.
- Modes: `bot` (trading bot), `dash` (Dashboard V1 on port 8000), `v2` (Dashboard V2 on port 5173), `dash+bot`, `v2+bot`.
- Interactive menu or CLI argument (`python run.py v2+bot`).
- Thread-based combo launcher for multi-component runs.

### `core/health.py` (v0.14.0)
- `HealthStats`: in-memory runtime stats — uptime, MT5 status, Telegram status, daily signal/order/error counters, circuit breaker state.
- Auto-reset daily counters at midnight UTC.
- Status computation: healthy / degraded (MT5 disconnected) / unhealthy (circuit breaker OPEN).
- `HealthCheckServer`: lightweight async HTTP server on port 8080 (configurable via `HEALTH_CHECK_PORT`).
- Serves `/health` endpoint — JSON response with full bot status. No external dependencies.

### `core/message_update_handler.py`
- Handle Telegram `MessageEdited` events.
- Detect updates to previously processed signals.
- Decide whether to: ignore, update existing pending order, cancel previous order.
- Group-aware: checks PositionManager for filled orders before deciding action.
- Prevent duplicate or conflicting trades caused by edited messages.

### `core/order_lifecycle_manager.py`
- Manage lifecycle of pending orders.
- Track expiration time for limit/stop orders.
- Cancel orders that exceed configured TTL.
- Prevent stale signals from executing hours later.

> **Pending Order Expiration Rule**
>
> Pending orders created from signals must have a maximum lifetime.
>
> If a pending order has not been triggered within the configured
> TTL (time-to-live), it must be cancelled automatically.
>
> Example configuration:
> pending_order_ttl = 15 minutes (setup on config file do not fixed number)

### `core/mt5_watchdog.py`
- Periodically verify MT5 connection health.
- Run lightweight checks (example: `account_info()`).
- Trigger MT5 reinitialization if connection is lost.
- Callbacks: `on_connection_lost`, `on_reinit_exhausted`, `on_health_update` (→ HealthStats).

### `core/daily_risk_guard.py`
- Poll-based daily risk limits using MT5 `history_deals_get()`.
- Background task refreshes counters every `DAILY_RISK_POLL_MINUTES`.
- Enforces three independent limits (all default 0 = disabled):
  - `MAX_DAILY_TRADES`: max closed deals per UTC day.
  - `MAX_DAILY_LOSS`: max realized loss (USD) per UTC day.
  - `MAX_CONSECUTIVE_LOSSES`: pause after N consecutive losing deals.
- Sends Telegram alert on first breach per day.
- No manual counter management — derived from real MT5 deal history.

### `core/exposure_guard.py`
- Prevents over-concentration on correlated symbols.
- Queries live MT5 positions via `TradeExecutor.get_position_symbols()` on every signal (no stale counters).
- `MAX_SAME_SYMBOL_TRADES`: max open positions on same symbol.
- `MAX_CORRELATED_TRADES`: max open across configurable correlation groups.

### `core/position_manager.py`
- Background task managing open positions (poll-based).
- Breakeven: move SL to entry + lock pips when profit reaches trigger.
- Trailing stop: trail SL at fixed pip distance from current price.
- Partial close: close percentage of volume near TP1.
- Only manages positions matching bot's magic number.
- Per-channel rules via `ChannelManager` (v0.6.0)
- Telegram alerts on breakeven/trailing/partial with per-ticket 60s throttle (v0.7.1)
- Trailing alert delta threshold: ≥10 pips before alerting (v0.22.0, was 5)
- Daily cleanup loop at 1 AM (UTC+7): prunes tracking dicts + completed groups.
- Peak profit tracking per group: `_update_group_peak()`, `get_group_peak()`.
- **P10: Group-aware management**:
  - Every signal = 1 `OrderGroup` (group of 1 for single mode, group of N for range/scale_in)
  - `_check_positions()` routes to `_manage_group()` or `_manage_individual()`
  - Group SL: `_calculate_group_sl()` picks best SL from zone/signal/fixed/trail candidates
  - `_modify_group_sl()` applies SL atomically to ALL tickets, only moves favorably
  - `close_selective_entry()` — reply "close" closes one order by strategy (highest_entry/lowest_entry/oldest)
  - `secure_profit_group()` — reply "+N pip": close worst entry, set BE on remaining
  - `apply_group_be()` — auto-sets SL to min remaining entry after partial close
  - `cancel_group_pending_orders()` — cancel unfilled LIMIT/STOP orders in group (v0.11.0)
  - `restore_groups()` — rebuild from DB after restart, skip groups with all-closed tickets
  - DB persistence via `storage.py` for restart recovery

### `core/command_parser.py`
- Parse Telegram management commands (CLOSE ALL, CLOSE SYMBOL, CLOSE HALF, MOVE SL, BREAKEVEN, CANCEL ALL, CANCEL SYMBOL).
- Typo tolerance: `CANCELL ALL`, `HỦY ALL`, `HỦY TẤT CẢ`.
- Returns None for non-command messages (falls through to signal parser).

### `core/command_executor.py`
- Execute parsed commands against MT5 positions.
- All operations filter by bot's magic number.
- CANCEL commands use `mt5.orders_get()` + `TRADE_ACTION_REMOVE`.
- Returns human-readable summary strings.
- Command response sent to source chat + admin Telegram (v0.7.1)

### `core/reply_action_parser.py` (v0.8.0, updated v0.21.0)
- Parse reply messages into trade actions: `CLOSE`, `CLOSE_PARTIAL`, `MOVE_SL`, `MOVE_TP`, `BREAKEVEN`, `SECURE_PROFIT`, `CANCEL`.
- Separate from signal parser — replies are short imperative commands.
- Validation: price required for SL/TP, percent 1-100 for partial close.
- Built-in patterns:
  - close/exit/đóng
  - SL/TP {price}
  - BE/breakeven
  - close N%
  - `+N`, `+N pips`, `done Npips`, `near N pips` → SECURE_PROFIT
  - `+Npips close all` → CLOSE (priority over SECURE_PROFIT)
  - cancel/hủy/miss/bỏ/skip → CANCEL (allows trailing text)

### `core/reply_command_executor.py` (v0.8.0, updated v0.19.0)
- Execute reply actions on **specific** MT5 position tickets (unlike CommandExecutor which is global).
- Position existence check before execute.
- Symbol consistency guard: verify position matches expected symbol.
- Supports: close, close partial (percent), move SL, move TP, breakeven, secure profit, cancel.
- **G12b**: Breakeven sets SL = entry ± `reply_be_lock_pips` (BUY: +, SELL: -) instead of exact entry.
  - Config per channel: `rules.reply_be_lock_pips` (default: 1 pip).
  - Guard: won't overwrite a better SL (from auto-BE).
  - Lock pips passed per-call from channel config for multi-channel support.

### Reply-Based Signal Management Flow (v0.8.0, enhanced v0.21.0)
```
Reply message (reply_to = signal_msg_id)
  → listener detects reply_to_msg_id → forward to _process_reply()
  → storage.get_orders_by_message() → list of ALL orders for that signal
  → channel guard + success filter
  → reply_action_parser.parse() → ReplyAction | None
  → P10: if CLOSE + group has selective strategy:
      → PositionManager.close_selective_entry(strategy)
      → auto apply_group_be if configured
      → return early with selective result
  → if SECURE_PROFIT:
      → PositionManager.secure_profit_group() → close worst + BE rest
      → cancel_all_pending() (G6)
  → if CANCEL:
      → cancel pending MT5 orders + re-entry plans by fingerprint
  → else: for each order: execute on ticket (with position check)
  → group results: "✅ closed" / "⏭ already closed"
  → reply aggregated summary to user (admin chat only)
  → mark_reply_closed() → TradeTracker suppresses duplicate PnL reply
```

## Dependencies
- External:
  - Telegram API (Telethon user session)
  - Local MT5 terminal connected to broker
- Internal:
  - parser→ validator→ risk_manager→ order_builder→ pipeline→ executor
  - validator/executor depend on settings and storage
  - all runtime modules depend on logger

## Data Contracts

### `ParsedSignal`
- `symbol: str`
- `side: BUY|SELL`
- `entry: float | null`
- `entry_range: list[float] | None`  — `[low, high]` if range detected
- `sl: float | null`
- `tp: list[float]`
- `raw_text: str`
- `source_chat_id: str`
- `source_message_id: str`
- `received_at: datetime`
- `fingerprint: str` — includes `source_chat_id` + `source_message_id`
- `parse_confidence: float` — 0.0-1.0 confidence score
- `parse_source: str` — which parser produced this signal
- `is_now: bool` — "Now" keyword detected — prefer MARKET if in zone

### `TradeDecision`
- `order_kind: MARKET|BUY_LIMIT|BUY_STOP|SELL_LIMIT|SELL_STOP`
- `price: float | null`
- `sl: float | null`
- `tp: float | null`

### `ExecutionResult`
- `success: bool`
- `retcode: int`
- `ticket: int | null`
- `message: str`

## Data Flow Detail
1. Listener receives message and creates event context.
2. Step 0: Command intercept (management commands bypass signal pipeline).
3. Parser pipeline converts raw text into normalized signal.
4. Circuit breaker → Daily risk guard → Exposure guard checks.
5. Duplicate check via fingerprint.
6. Validator applies safety rules (distance, spread, drift).
7. Pipeline generates entry plan(s) via EntryStrategy (single or multi-order).
8. For each plan: OrderBuilder decides type, RiskManager calculates volume, Executor submits MT5 request.
9. PositionManager registers order group (group of 1 or N).
10. If deferred plans exist: SignalStateManager registers, RangeMonitor monitors price for re-entries.
11. Storage writes signal/order/event records.
12. Logger emits structured logs for each stage.

## Failure Paths
- Parse failure -> reject and log, no trade action.
- Validation failure -> reject and log reason.
- MT5 unavailable -> retry; on final failure log and mark failed.
- Duplicate signal within TTL -> ignore and log dedupe event.
- Circuit breaker OPEN -> reject all signals until cooldown.
- Daily risk limit hit -> reject with specific guard reason.
- Exposure guard hit -> reject with symbol/correlation reason.


## Dashboard V2 — React SPA (v0.15.0–v0.16.6)

### Frontend Architecture
- **Tech**: React 19 + Vite 6 + Recharts + TanStack Query + Framer Motion
- **Location**: `dashboard-v2/`
- **Port**: `http://localhost:5173` (dev), proxied to FastAPI on `:8000`
- **Design**: Dark glassmorphism, JetBrains Mono numbers, Framer Motion animations

### Pages
| Page | Component | Purpose |
|------|-----------|---------|
| Overview | `Overview.jsx` | SparkCards, Equity Curve, Daily PnL combo, Win/Loss donut, Top Channels, Active Positions, **Win Rate Gauge**, **Signal Breakdown**, **PnL by Weekday** (v0.16.1) |
| Analytics | `Analytics.jsx` | Weekly win/loss, PnL distribution, drawdown, activity, symbol butterfly |
| Channels | `Channels.jsx` | Channel comparison, interactive cards, daily drill-down |
| Symbols | `Symbols.jsx` | Performance table, PnL ranking, radar chart |
| Trades | `Trades.jsx` | Multi-filter, paginated table, CSV export |
| Signals | `Signals.jsx` | **Expandable grouped signal table**, detail modal, cascade delete (v0.16.0) |
| Settings | `Settings.jsx` | Connection status (live ping), API key, about |

### Key Features (v0.16.x)
- **Chart Toggle** (v0.16.1): `useChartVisibility()` hook — localStorage-persisted visibility map for 9 chart cards on Overview. "Customize" dropdown UI.
- **Signal Lifecycle** (v0.16.0): Signals grouped by fingerprint, expandable child orders, `SignalDetailModal` with raw text → parsed → orders → trades timeline.
- **ConfirmModal** (v0.16.0): Shared glassmorphism confirmation popup with type-to-confirm for destructive actions.
- **Helper extraction** (v0.16.6): Page-specific data transforms extracted to `Overview.helpers.js` and `Analytics.helpers.js` for testability.
- **Unit tests** (v0.16.3–v0.16.5): 130 Vitest (dashboard-v2) + 249 pytest (bot) tests.

### Backend — Dashboard API (`dashboard/`)
- **`dashboard/dashboard.py`**: FastAPI app, CORS (GET + DELETE), serves both V1 (Jinja2) and V2 (API). Optional HTTP auth via `DASHBOARD_PASSWORD`.
- **`dashboard/api/routes.py`**: API router with all endpoints, channel name resolution from `channels.json`.
- **`dashboard/db/queries.py`**: `DashboardDB` class — read-only by default, `_connect_rw()` for write operations.

### API Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/overview` | High-level summary stats |
| `GET` | `/api/daily-pnl` | Daily PnL (last N days) |
| `GET` | `/api/channels` | Per-channel performance with names |
| `GET` | `/api/channels/{id}/daily-pnl` | Channel daily PnL drill-down |
| `GET` | `/api/trades` | Paginated trade history with filters |
| `GET` | `/api/active` | Active signal groups |
| `GET` | `/api/equity-curve` | Cumulative PnL for equity chart |
| `GET` | `/api/symbol-stats` | Per-symbol win rate + PnL |
| `GET` | `/api/export/csv` | CSV export with filters |
| `GET` | `/api/symbols` | Unique traded symbols |
| `GET` | `/api/channel-list` | Channel list with names `{id, name}` |
| `GET` | `/api/signals` | Paginated signals grouped by fingerprint |
| `GET` | `/api/signals/{fingerprint}` | Full signal lifecycle detail |
| `DELETE` | `/api/signals/{fingerprint}` | Cascade delete signal + orders + trades |
| `DELETE` | `/api/orders/{order_id}` | Delete individual order |
| `DELETE` | `/api/trades/{trade_id}` | Delete individual trade |
| `GET` | `/api/data/counts` | Row counts per table |
| `DELETE` | `/api/data/all` | Clear all data tables |
| `DELETE` | `/api/data/{table}` | Clear specific table |
| `GET` | `/api/signal-status-counts` | Signal status breakdown counts |

### Data Flow
```
Browser (React) ──→ TanStack Query ──→ fetch(/api/*) ──→ Vite proxy ──→ FastAPI ──→ DashboardDB ──→ SQLite
                                                                            ↕
                                                                     _connect_rw (write ops)
```

## Observability

> For signal lifecycle events, event types, and trace requirements, see [OBSERVABILITY.md](OBSERVABILITY.md).