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
  → pipeline_execute (single or multi-order via SignalPipeline)
  → order_result (executed / failed)
  → [if range/scale_in] signal_state_registered → range_monitor_trigger → reentry_executed
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

## Trade Outcome Events (v0.6.0)

- `trade_tracked` — closing deal matched to DB order, PnL recorded
- `trade_tracker_orphan_deal` — deal not matched to any bot order
- `pending_fill_detected` — pending order filled, position_ticket updated
- `trade_tracker_partial_throttled` — partial close reply skipped (60s cooldown, v0.7.0)

## Message Edit Events (v0.7.0)

- `edit_received` — edited message detected
- `edit_no_original` — no matching signal found for this message
- `edit_decision` — handler produced decision (action + reason)
- `edit_cancel_attempted` — lifecycle manager cancel by fingerprint
- `edit_reprocess` — edited signal re-submitted through pipeline

## Command Events (v0.7.1)

- `command_response` — command result sent to source chat + admin

## Position Management Alerts (v0.7.1)

- `breakeven_alert` — Telegram alert on SL moved to breakeven (60s throttle per ticket)
- `trailing_alert` — Telegram alert on trailing SL moved ≥5 pips (60s throttle + delta)
- `partial_close_alert` — Telegram alert on partial volume close (60s throttle per ticket)

## Reply-Based Signal Management (v0.8.0)

- `reply_received` — reply message detected with reply_to_msg_id
- `reply_no_orders` — no orders found for replied message
- `reply_no_matching_orders` — orders exist but filtered by channel guard
- `reply_not_action` — reply text not parseable as action (comment)
- `reply_action_parsed` — reply parsed: action, price, percent
- `reply_action` — executing action on specific ticket (with fingerprint)
- `reply_executed` — action result stored per ticket
- `reply_command` — aggregated result sent to user + admin
- `trade_tracker_reply_suppressed` — PnL reply suppressed for reply-closed ticket

## Multi-Order Strategy Events (v0.9.0)

- `pipeline_single_execute` — single mode: one order executed via SignalPipeline
- `pipeline_multi_execute` — range/scale_in: N orders created from one signal
- `signal_state_registered` — signal entered state machine (PENDING)
- `signal_state_partial` — at least one level filled
- `signal_state_completed` — all levels filled or max_entries reached
- `signal_state_expired` — signal TTL exceeded, removed from monitoring
- `range_monitor_trigger` — price crossed through re-entry level (with debounce)
- `range_monitor_callback_error` — re-entry callback failed
- `reentry_executed` — re-entry order placed via Pipeline.handle_reentry()
- `reentry_blocked` — re-entry rejected by risk guards (circuit breaker, daily, exposure)

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