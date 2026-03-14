# Observability

## Purpose

Ensure every signal can be traced through the system.

## Signal Lifecycle

signal_received
→ parse_success / parse_failed
→ validation_pass / validation_rejected
→ order_submitted
→ order_result

## Signal Status

Signals stored in DB should have status:

received
parsed
rejected
submitted
executed
failed

## Log Format

Logs must be structured JSON.

Example:

{
 "event": "order_submitted",
 "fingerprint": "abc123",
 "symbol": "XAUUSD",
 "side": "BUY",
 "price": 2030,
 "timestamp": "..."
}

## Debug Workflow

To investigate a signal:

1. Search logs using fingerprint.
2. Check signal table record.
3. Check order table record.
4. Compare MT5 ticket if present.