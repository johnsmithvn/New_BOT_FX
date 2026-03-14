# TASKS

## Current Phase
- `P2 - Trade Decision and Execution (R3 + R3.5)`

## High Priority

### Telegram Listener
- [x] Implement `core/telegram_listener.py` — Telethon user session, subscribe to source chats, forward raw messages to parser pipeline.
- [x] Wire listener into `main.py` startup with async event loop.

### Order Builder
- [x] Implement `core/order_builder.py` — read live bid/ask from MT5 tick, decide order type (MARKET, BUY_LIMIT, BUY_STOP, SELL_LIMIT, SELL_STOP).
- [x] Enforce correct price reference: BUY uses ASK, SELL uses BID.
- [x] Build MT5 request payload with action, type, price, SL, TP, deviation, magic number, comment.

### Trade Executor
- [x] Implement `core/trade_executor.py` — initialize MT5 connection, verify terminal state.
- [x] Implement symbol selection and tradability check.
- [x] Implement `order_send` with bounded retry (max retries, backoff, failure logging).
- [x] Normalize MT5 return codes into `ExecutionResult`.

### Spread Gate
- [x] Implement spread threshold check in validator using live tick data.
- [x] Reject signal if current spread exceeds `MAX_SPREAD_POINTS`.

### Max Open Trades Gate
- [x] Implement max open trades check using MT5 `positions_total()`.
- [x] Reject signal if open positions >= `MAX_OPEN_TRADES`.

### Duplicate Signal Filter
- [x] Wire fingerprint duplicate check via `Storage.is_duplicate()` before order submission.

### Order Lifecycle
- [x] Implement `core/order_lifecycle_manager.py` — track pending orders, auto-cancel after TTL.
- [x] Wire lifecycle manager into main event loop.

### MT5 Watchdog
- [x] Implement `core/mt5_watchdog.py` — periodic health check via `account_info()`, trigger reinit on connection loss.

### Pipeline Integration
- [x] Wire full pipeline: listener → parser → validator → risk_manager → order_builder → executor → storage.
- [x] Emit structured log events at each pipeline stage with fingerprint.
- [x] Store signal, order, and event records in SQLite at appropriate stages.

## Medium Priority
- [x] Handle multi-TP by sending first TP to MT5 and logging remaining TPs for manual management.
- [x] Implement MT5 error code mapping to human-readable messages.
- [x] Wire `MessageUpdateHandler` into Telegram `MessageEdited` event.
- [ ] Add Telegram notification on execution result (optional, send back to user/admin chat).

## Low Priority
- [ ] Add execution dry-run mode (log intent without sending to MT5).
- [ ] Add CLI command to manually submit a signal for execution testing.

## Completed (from previous phases)
- [x] All P0 tasks (documentation foundation).
- [x] All P1 tasks (signal parser pipeline, validation, risk manager, storage, tooling).
