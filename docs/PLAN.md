# PLAN

## Current Phase
- Phase: `P6 - Multi-Channel & Trade Tracking (complete)`
- Status: All core + medium-priority items done. See `docs/TASKS.md` for details.

## Execution Phases

### P0 - Foundation and Safety Baseline
- Roadmap reference: `R1`
- Goal:
  - Establish project baseline, rules, and documentation contracts.
- Major deliverables:
  - Documentation system in `docs/`
  - Initial safety and anti-hallucination rules
  - Base repository structure decisions
- Status: `complete`

### P1 - Signal Understanding
- Roadmap reference: `R2`
- Goal:
  - Implement robust parsing and normalization pipeline.
- Major deliverables:
  - Message cleaner and detectors (symbol, side, entry, SL, TP)
  - Normalized `ParsedSignal` contract
  - Parser test coverage for major message variants
- Status: `complete`

### P2 - Trade Decision and Execution
- Roadmap reference: `R3`
- Goal:
  - Build deterministic order decision and MT5 execution flow.
- Major deliverables:
  - Order type decision matrix using live bid/ask
  - MT5 request builder and executor with bounded retry
  - Execution result normalization and logging
- Status: `complete`

### P3 - Reliability for 24/7 Runtime
- Roadmap reference: `R4`
- Goal:
  - Ensure runtime resilience and state continuity.
- Major deliverables:
  - SQLite dedupe + audit storage
  - Reconnect/retry hardening
  - Operational error handling and incident-ready logs
- Status: `complete`

### P4 - Production Operations
- Roadmap reference: `R5`
- Goal:
  - Prepare repeatable deployment and operations lifecycle.
- Major deliverables:
  - VPS deployment runbook (`docs/DEPLOY.md`)
  - Monitoring/alerting strategy (`docs/MONITORING.md`)
  - Release/update procedure with rollback
  - Daily risk guard (MAX_DAILY_TRADES, MAX_DAILY_LOSS, MAX_CONSECUTIVE_LOSSES)
  - Startup position sync
  - Log rotation validation
- Status: `complete`

### P5 - Controlled Expansion
- Roadmap reference: `R6`
- Goal:
  - Add features while preserving safety baseline.
- Major deliverables:
  - Exposure/correlation guard (`core/exposure_guard.py`)
  - Position manager — breakeven, trailing stop, partial close (`core/position_manager.py`)
  - Signal management commands — CLOSE ALL, CLOSE SYMBOL, MOVE SL, BREAKEVEN (`core/command_parser.py`, `core/command_executor.py`)
  - Dynamic deviation in `core/order_builder.py`
  - 10 new configurable env keys, all opt-in (default disabled)
- Status: `complete`

### P6 - Multi-Channel & Trade Outcome Tracking
- Goal:
  - Support multiple Telegram signal channels with per-channel rules.
  - Track trade outcomes (PnL) and reply under the original signal.
- Major deliverables:
  - Versioned schema migration system in `core/storage.py`
  - `core/channel_manager.py` — per-channel rule configuration
  - `core/trade_tracker.py` — background deal polling, PnL tracking, reply messages
  - `core/telegram_alerter.py` — `reply_to_message()` for trade outcome threading
  - `core/position_manager.py` — per-channel breakeven/trailing/partial rules
  - Fingerprint updated to include `source_chat_id` (breaking change)
  - New DB tables: `trades`, `tracker_state`, `schema_versions`
  - 1 new env key: `TRADE_TRACKER_POLL_SECONDS`
- Status: `complete`

## Phase Completion Rule
- Current phase is complete only when all `High Priority` and `Medium Priority` tasks in `docs/TASKS.md` are checked.
- On completion:
  - Mark current phase `complete`
  - Move next phase to `in progress`
  - Regenerate `docs/TASKS.md` for the new current phase

## What's Next
- v0.7.0 done: per-channel metrics, message edit wiring, store_event channel_id, reply throttle
- v0.7.1 done: command response via Telegram, position manager alerts with throttle
- v0.8.0 done: reply-based signal management (reply to signal → close/SL/TP/BE on specific trade)
- Deferred: parser overrides per detector (no concrete need yet)
- Consider next: extended parser formats, multi-account support, web dashboard
