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
    → [G2] default_sl_generated (if no SL + has zone)
    → [G2] sl_distance_capped (if SL too far)
    → sl_buffer_applied (if configured + original SL)
  → order_result (executed / failed)
  → [if range/scale_in] signal_state_registered → range_monitor_trigger → reentry_executed
  → group_registered (P10: every signal → order group)
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
- `trailing_stop_moved` — SL trailed to new level (throttled: logged every move, alert only if ≥10 pips delta)
- `partial_close_executed` — volume partially closed
- `exposure_blocked` — signal rejected by exposure guard

## Trade Outcome Events (v0.6.0)

- `trade_tracked` — closing deal matched to DB order, PnL recorded (includes `peak_pips`, `entry_price`)
- `trade_tracker_orphan_deal` — deal not matched to any bot order
- `pending_fill_detected` — pending order filled, position_ticket updated
- `trade_tracker_partial_throttled` — partial close reply skipped (60s cooldown, v0.7.0)

## Message Edit Events (v0.7.0)

- `edit_received` — edited message detected
- `edit_no_original` — no matching signal found for this message
- `edit_decision` — handler produced decision (action + reason)
- `edit_cancel_attempted` — lifecycle manager cancel by fingerprint
- `edit_reprocess` — edited signal re-submitted through pipeline

## Message Delete Events (v0.11.0)

- `delete_received` — deleted message detected
- `group_pending_cancelled` — pending orders in group cancelled (edit/delete handling)

## Command Events (v0.7.1)

- `command_response` — command result sent to source chat + admin

## Position Management Alerts (v0.7.1, updated v0.22.0)

- `breakeven_alert` — Telegram alert on SL moved to breakeven (60s throttle per ticket)
- `trailing_alert` — Telegram alert on trailing SL moved ≥10 pips (60s throttle + delta threshold, was 5 pips pre-v0.22.0)
- `partial_close_alert` — Telegram alert on partial volume close (60s throttle per ticket)

## Reply-Based Signal Management (v0.8.0, expanded v0.19.0–v0.21.0)

- `reply_received` — reply message detected with reply_to_msg_id
- `reply_no_orders` — no orders found for replied message
- `reply_no_matching_orders` — orders exist but filtered by channel guard
- `reply_not_action` — reply text not parseable as action (comment)
- `reply_action_parsed` — reply parsed: action, price, percent, pips
- `reply_action` — executing action on specific ticket (with fingerprint)
- `reply_executed` — action result stored per ticket
- `reply_command` — aggregated result sent to user + admin
- `trade_tracker_reply_suppressed` — PnL reply suppressed for reply-closed ticket

## Multi-Order Strategy Events (v0.9.0)

- `pipeline_single_execute` — single mode: one order executed via SignalPipeline
- `pipeline_multi_execute` — range/scale_in: N orders created from one signal
- `pipeline_no_plans` — entry strategy produced no plans
- `pipeline_deferred_plans` — deferred plans registered for RangeMonitor
- `signal_state_registered` — signal entered state machine (PENDING)
- `signal_state_partial` — at least one level filled
- `signal_state_completed` — all levels filled or max_entries reached
- `signal_state_expired` — signal TTL exceeded, removed from monitoring
- `range_monitor_trigger` — price crossed through re-entry level (with debounce)
- `range_monitor_callback_error` — re-entry callback failed
- `reentry_executed` — re-entry order placed via Pipeline.handle_reentry()
- `reentry_blocked` — re-entry rejected by risk guards (circuit breaker, daily, exposure)
- `reentry_rejected` — re-entry rejected with specific reason (sl_too_close, price_too_far_from_level, zero_volume, no_tick)

## Signal Group Management Events (v0.10.0, expanded v0.22.0)

- `group_registered` — new signal group created (all signals → group of 1+)
- `group_already_registered` — duplicate group registration attempt
- `group_order_added` — re-entry order added to existing group
- `group_sl_modified` — group SL successfully applied to a ticket
- `group_sl_modify_failed` — group SL modification failed on a ticket
- `group_sl_moved` — group SL alert (significant SL movement across group)
- `group_completed` — all orders in group closed
- `group_selective_close` — reply-based selective close (strategy: highest/lowest entry, oldest)
- `group_be_applied` — auto-breakeven applied after partial group close
- `group_be_skipped` — breakeven skipped (current SL already better)
- `group_pending_cancelled` — pending orders in group cancelled (edit/delete handling, v0.11.0)
- `groups_restored` — groups rebuilt from DB on startup (with stale_completed count)

## Pipeline Guard Events (v0.19.0–v0.22.1)

- `default_sl_generated` — SL auto-generated from entry zone (G2)
- `sl_distance_capped` — SL was too far, capped to default distance
- `sl_buffer_applied` — SL widened by buffer pips (original signal SL only)
- `entry_skipped_sl_too_close` — entry plan skipped: price too close to SL (G1)

## Peak Profit Events (v0.22.0)

- `group_peak_updated` — peak profit tracked for signal group (persisted every +10p)
- `group_peak_final` — peak profit snapshot saved on group completion

## Health & Infrastructure Events

- `health_server_started` — HTTP health server started on configured port
- `health_server_failed` — health server failed to start (port conflict)
- `health_server_stopped` — health server stopped
- `circuit_breaker_state_change` — CB state transition (old → new, failures count)
- `position_manager_started` — PM started with config summary
- `position_manager_stopped` — PM stopped
- `position_manager_disabled` — PM not started (no features enabled)
- `position_manager_cache_rebuilt` — ticket→channel cache rebuilt from DB
- `position_manager_cleanup_done` — daily cleanup sweep results
- `position_manager_cleanup_scheduled` — next cleanup time logged
- `alert_sent` / `alert_rate_limited` / `alert_skipped` — TelegramAlerter events
- `schema_migration_applied` / `schema_migration_skipped` — DB migration events

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