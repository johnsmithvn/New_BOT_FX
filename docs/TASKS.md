# TASKS

## Current Phase
- `P3 - Reliability for 24/7 Runtime (R4)`

## High Priority

### Smart Dry-Run Mode
- [x] Add `DRY_RUN` setting to config.
- [x] In pipeline: derive bid/ask dynamically from signal entry.
- [x] Skip `order_send()` in dry-run, log full request, return mock success.

### Telegram Alerting
- [x] Implement `core/telegram_alerter.py` — rate-limited alerts to admin chat.
- [x] Add `TELEGRAM_ADMIN_CHAT` and `ALERT_COOLDOWN_SECONDS` to config.
- [x] Wire alerts: circuit breaker, MT5 reinit exhausted, bot startup/shutdown.

### Improved Console Logging + Pipeline Summary
- [x] Add one-line pipeline summary per signal to console.
- [x] Show rejection reason in console log.
- [x] Add startup self-check: MT5 account info, config summary.

### Global Error Handling
- [x] Wrap `_process_signal` in try/except — never crash event loop.
- [x] Add graceful shutdown with storage flush and clean disconnect.

### Circuit Breaker
- [x] Implement `core/circuit_breaker.py` — CLOSED/OPEN/HALF_OPEN states.
- [x] Open after N consecutive failures, auto-reset after cooldown.
- [x] Trigger Telegram alert on state change.

### Telegram Reconnect + Proactive Session Reset
- [x] Add auto-reconnect on disconnect with exponential backoff.
- [x] Add proactive session reset every `SESSION_RESET_HOURS`.

### MT5 Watchdog Improvements
- [x] Detect weekend/market-close — suppress false alarms.
- [x] Exponential backoff on reinit failures.
- [x] Alert callbacks for connection lost and reinit exhausted.

### Storage Hardening
- [x] Enable WAL mode.
- [x] Add retry on `sqlite3.OperationalError` (database locked).
- [x] Implement `cleanup_old_records(retention_days)` as background task.

### Signal Lifecycle Events (DB tracing)
- [x] Store `signal_received`, `signal_parsed`, `signal_rejected`, `signal_submitted`, `signal_executed`, `signal_failed` in events table.

## Medium Priority
- [ ] Add signal processing metrics (count parsed/rejected/executed per session).
- [ ] Add heartbeat log every N minutes.

## Completed (from previous phases)
- [x] All P0 tasks (documentation foundation).
- [x] All P1 tasks (signal parser pipeline, validation, risk manager, storage, tooling).
- [x] All P2 tasks (trade executor, order builder, Telegram listener, lifecycle manager, watchdog, pipeline wiring).
