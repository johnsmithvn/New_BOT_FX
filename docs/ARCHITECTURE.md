# ARCHITECTURE

## System Overview
- Runtime model: single Python process.
- Primary flow:
  1. Telegram message received
  2. Message cleaned and parsed
  3. Signal validated and normalized
  4. Order type decided from live price context
  5. MT5 request built and sent
  6. Result persisted and logged

## Core Modules

### `config/settings.py`
- Load env variables and defaults.
- Validate required settings on startup.
- Provide typed config access across modules.

### `core/telegram_listener.py`
- Connect to Telegram via Telethon session.
- Subscribe to configured source chats/channels.
- Forward raw messages to parser pipeline.
Telegram Access Mode

The system uses a Telethon user session rather than a Telegram Bot API
to ensure it can read messages from private groups and signal channels.

### core/risk_manager.py

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
- `cleaner.py`: normalize raw text.
- `symbol_detector.py`: detect and map symbol aliases.
- `side_detector.py`: detect BUY/SELL/LONG/SHORT.
- `entry_detector.py`: detect explicit entry or market intent.
- `sl_detector.py`: detect SL value.
- `tp_detector.py`: detect TP values (`TP`, `TP1`, `TP2`, ...).
- `parser.py`: orchestrate detectors and produce `ParsedSignal`.

Detector Safety Rule

Each detector (symbol, side, entry, SL, TP) must handle
unexpected input safely and must not raise unhandled exceptions.

Detectors should return None or structured failure information
when parsing fails.

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
Price Reference Rule

Order decision must use correct MT5 reference prices:

BUY orders must compare entry against ASK price.
SELL orders must compare entry against BID price.

Using BID for BUY decisions or ASK for SELL decisions may lead
to incorrect order classification and immediate slippage.

Example:

BUY:
    entry > ask → BUY_STOP
    entry <= ask → BUY_LIMIT or MARKET

SELL:
    entry < bid → SELL_STOP
    entry >= bid → SELL_LIMIT or MARKET


### `core/trade_executor.py`
- Initialize MT5 terminal connection.
- Maintain connection health and expose retry-safe execution.
- Provide position query helpers for exposure guard integration.

### `core/channel_manager.py` (v0.6.0)
- Load per-channel rules from `config/channels.json`.
- Merge default rules with channel-specific overrides.
- Falls back gracefully if no config file exists.
- Provides `get_rules(chat_id)` for per-channel rule lookup.

### `core/trade_tracker.py` (v0.6.0)
- Background deal polling via MT5 `history_deals_get()`.
- Track trade outcomes (PnL, commission, swap, close reason).
- 2-step ticket→position resolution (MARKET + pending orders).
- Detect pending order fills via `DEAL_ENTRY_IN`.
- Persist `last_deal_poll_time` for restart recovery.
- Dispatch PnL reply messages under original signals via `TelegramAlerter`.

- `get_position_symbols()`: list open position symbols (used by ExposureGuard).

### `core/storage.py`
- SQLite persistence (WAL mode) with versioned migration system.
- Tables:
  - `signals` — parsed signal fingerprints, status, channel context
  - `orders` — MT5 order audit trail with `channel_id`, `source_chat_id`, `source_message_id`
  - `events` — runtime event records with `channel_id` (v0.7.0)
  - `trades` — trade outcomes: PnL, commission, swap, close reason (v0.6.0)
  - `tracker_state` — key-value persistence for `TradeTracker` poll time (v0.6.0)
  - `schema_versions` — migration version tracking (v0.6.0)
- Fingerprint lookup by message: `get_fingerprint_by_message()` (v0.7.0)

### `utils/symbol_mapper.py`
- Map channel symbol aliases to broker symbols.
- Validate mapping availability before execution.

### `utils/logger.py`
- Configure console + file logs.
- Emit structured event logs for traceability.

### `main.py`
- Startup orchestration:
  - load config
  - init logger
  - init storage
  - init MT5
  - start Telegram listener

### `core/message_update_handler.py`
- Handle Telegram `MessageEdited` events.
- Detect updates to previously processed signals.
- Decide whether to:
  - ignore
  - update existing pending order
  - cancel previous order
- Prevent duplicate or conflicting trades caused by edited messages.

### `core/order_lifecycle_manager.py`
- Manage lifecycle of pending orders.
- Track expiration time for limit/stop orders.
- Cancel orders that exceed configured TTL.
- Prevent stale signals from executing hours later.
Pending Order Expiration Rule

Pending orders created from signals must have a maximum lifetime.

If a pending order has not been triggered within the configured
TTL (time-to-live), it must be cancelled automatically.

Example configuration:
pending_order_ttl = 15 minutes (setup on config file do not fixed number)

### `core/mt5_watchdog.py`
- Periodically verify MT5 connection health.
- Run lightweight checks (example: `account_info()`).
- Trigger MT5 reinitialization if connection is lost.

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
- Trailing alert delta threshold: ≥5 pips before alerting (v0.7.1)

### `core/command_parser.py`
- Parse Telegram management commands (CLOSE ALL, CLOSE SYMBOL, MOVE SL, BREAKEVEN).
- Returns None for non-command messages (falls through to signal parser).

### `core/command_executor.py`
- Execute parsed commands against MT5 positions.
- All operations filter by bot's magic number.
- Returns human-readable summary strings.
- Command response sent to source chat + admin Telegram (v0.7.1)

## Dependencies
- External:
  - Telegram API (Telethon session)
  - Local MT5 terminal connected to broker
- Internal:
  - parser→ validator→ risk_manager→ order_builder→ executor
  - validator/executor depend on settings and storage
  - all runtime modules depend on logger

## Data Contracts

### `ParsedSignal`
- `symbol: str`
- `side: BUY|SELL`
- `entry: float | null`
- `sl: float | null`
- `tp: list[float]`
- `raw_text: str`
- `source_chat_id: str`
- `source_message_id: str`
- `received_at: datetime`
- `fingerprint: str` — includes `source_chat_id` (v0.6.0 breaking change)
- `parse_confidence: float` — 0.0-1.0 confidence score
- `parse_source: str` — which parser produced this signal

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
2. Parser pipeline converts raw text into normalized signal.
3. Validator applies safety rules and dedupe checks.
4. Order builder compares entry to live bid/ask and selects order type.
5. Executor submits MT5 request and processes return code.
6. Storage writes signal/order/event records.
7. Logger emits structured logs for each stage.

## Failure Paths
- Parse failure -> reject and log, no trade action.
- Validation failure -> reject and log reason.
- MT5 unavailable -> retry; on final failure log and mark failed.
- Duplicate signal within TTL -> ignore and log dedupe event.


## Observability and Signal Trace

The system MUST provide full traceability for every signal processed.

Each signal MUST have a unique `fingerprint` generated from:
- symbol
- side
- entry
- SL
- TP values

All processing stages MUST log structured events with this fingerprint.

### Core Event Types

signal_received
- Telegram message received.

parse_success
- Signal successfully parsed into normalized format.

parse_failed
- Parser unable to interpret signal.

validation_rejected
- Signal rejected due to safety rule (spread, SL logic, duplicate, etc).

duplicate_filtered
- Signal ignored due to dedupe window.

order_submitted
- MT5 order request created and sent.

order_result
- MT5 execution response received.

### Trace Requirement

All logs and database records MUST include:
- signal fingerprint
- source message id
- symbol
- timestamp