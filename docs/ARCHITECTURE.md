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

### `core/order_builder.py`
- Read live bid/ask from MT5 tick.
- Decide order class:
  - BUY: market vs buy limit vs buy stop
  - SELL: market vs sell limit vs sell stop
- Build MT5 request payload (action, type, price, SL, TP, metadata).
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
- Initialize and verify MT5 connection.
- Ensure symbol selected and tradeable.
- Execute `order_send` with bounded retry.
- Return normalized execution result.

### `core/storage.py`
- SQLite persistence for:
  - signal fingerprints (dedupe window)
  - order audit trail
  - runtime event records

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
- `fingerprint: str`

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