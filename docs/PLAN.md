# PLAN

## Current Phase
- Phase: `P9 - Channel-Driven Strategy Architecture`
- Status: `complete`

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

### P7 - Reply-Based Signal Management
- Goal:
  - Allow users to reply to original signal messages to manage trades.
- Major deliverables:
  - `core/reply_action_parser.py` — parse reply commands (close, SL, TP, BE, close N%)
  - `core/reply_command_executor.py` — per-ticket operations with position check
  - Telegram listener `reply_to_msg_id` forwarding
  - Storage `get_orders_by_message()` — multi-order lookup
  - TradeTracker reply-closed suppression with 5min TTL
  - `main.py` `_process_reply()` — multi-order, channel guard, grouped results
- Status: `complete`

### P8 - (Reserved)
- No P8 phase was defined — numbering skipped to P9.

### P9 - Channel-Driven Strategy Architecture
- Goal:
  - Redesign system to be channel-driven strategy-based, not just signal-driven.
  - Support range-based entry, multi-order per signal, dynamic re-entry.
- Major deliverables:
  - `core/entry_strategy.py` — multi-entry plan engine (single/range/scale_in)
  - `core/signal_state_manager.py` — active signal lifecycle with state machine
  - `core/range_monitor.py` — background price-cross re-entry trigger
  - `core/pipeline.py` — extracted sole orchestrator from main.py
  - `channels.json` expanded: strategy, risk, validation per channel
  - `core/models.py` — EntryPlan, SignalState, order_fingerprint
  - Storage migration V3: `active_signals` table
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
- v0.9.0 done: channel-driven strategy architecture (P9)
- Deferred: parser overrides per detector (no concrete need yet)
- Consider next: multi-account support, web dashboard
