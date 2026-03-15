# Observability

## Purpose

Ensure every signal and command can be traced through the system.

## Signal Lifecycle

```
signal_received
  → parse_success / parse_failed
  → circuit_breaker_check
  → daily_risk_guard_check
  → exposure_guard_check
  → duplicate_check
  → validation_pass / validation_rejected
  → order_submitted
  → order_result (executed / failed)
```

## Command Lifecycle

```
command_received
  → command_executed (with summary)
```

## Signal Status

Signals stored in DB have status:
- `received` — Telegram message captured
- `parsed` — normalized into ParsedSignal
- `rejected` — failed safety rule (with reason)
- `submitted` — MT5 order request sent
- `executed` — MT5 confirmed fill
- `failed` — MT5 returned error

## Position Events

- `breakeven_applied` — SL moved to entry + lock
- `trailing_stop_moved` — SL trailed to new level
- `partial_close_executed` — volume partially closed
- `exposure_blocked` — signal rejected by exposure guard

## Log Format

Logs are structured JSON (loguru file sink).

Example:
```json
{
  "event": "order_submitted",
  "fingerprint": "abc123def456",
  "symbol": "XAUUSD",
  "side": "BUY",
  "price": 2030,
  "timestamp": "2026-03-15T10:30:00Z"
}
```

## Debug Workflow

To investigate a signal:

1. Search logs using fingerprint: `grep "fp=<first-12>" logs/bot.log`
2. Check signal table record in `data/bot.db`
3. Check order table record
4. Compare MT5 ticket if present
5. Check for rejection reason: `grep "validation_rejected" logs/bot.log`