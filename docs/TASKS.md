# TASKS

## Current Phase
- `P9 - Channel-Driven Strategy Architecture`

## High Priority

### P9 Phase 1: Foundation
- [x] `core/models.py` — add EntryPlan, SignalState, order_fingerprint()
- [x] `config/channels.json` — expand schema with strategy/risk/validation
- [x] `core/channel_manager.py` — add get_strategy(), get_risk_config(), get_validation_config()
- [x] `core/entry_strategy.py` — new, multi-entry plan engine (single/range/scale_in)

### P9 Phase 2: Signal State + Storage
- [x] `core/storage.py` — migration V3, active_signals table + CRUD
- [x] `core/storage.py` — update get_orders_by_message() to join via source_message_id directly
- [x] `core/signal_state_manager.py` — new, state machine + registry

### P9 Phase 3: Pipeline Refactor
- [x] `core/pipeline.py` — new, extract from main.py, multi-order loop + handle_reentry()
- [x] `main.py` — thin orchestration, delegate to pipeline

### P9 Phase 4: Range Monitor
- [x] `core/range_monitor.py` — new, price-cross detection + debounce
- [x] `main.py` — wire RangeMonitor lifecycle (start/stop)

### P9 Phase 5: Documentation
- [x] `docs/ARCHITECTURE.md` — update
- [x] `CHANGELOG.md` — v0.9.0
- [x] `docs/TASKS.md` — finalize
- [x] `config/channels.example.json` — update

### Previous Phases (completed)

### Schema Migration System
- [x] `core/storage.py` — versioned migration system with `schema_versions` table
- [x] Migration V1: multi-channel columns on `orders` + `events`
- [x] Migration V2: `trades` + `tracker_state` tables

### Multi-Channel Support
- [x] `config/channels.example.json` — per-channel rule template
- [x] `core/channel_manager.py` — rule merging with default fallback
- [x] `main.py` — wire ChannelManager, pass channel context through pipeline
- [x] `core/position_manager.py` — per-channel breakeven/trailing/partial rules
- [x] `core/position_manager.py` — ticket→channel cache + startup rebuild

### Trade Outcome Tracking
- [x] `core/trade_tracker.py` — background deal polling, PnL persistence
- [x] `core/trade_tracker.py` — 2-step ticket→position resolution
- [x] `core/trade_tracker.py` — pending fill detection (DEAL_ENTRY_IN → update position_ticket)
- [x] `core/telegram_alerter.py` — `reply_to_message()` for PnL threading
- [x] `core/storage.py` — `store_trade()`, `get_signal_reply_info()`, `update_position_ticket()`

### Core Model Updates
- [x] `core/models.py` — `parse_confidence`, `parse_source` on `ParsedSignal`
- [x] `core/signal_parser/parser.py` — fingerprint includes `source_chat_id` (breaking change)

### Integration
- [x] `config/settings.py` — `trade_tracker_poll_seconds` in ExecutionConfig
- [x] `main.py` — ChannelManager + TradeTracker init, lifecycle, DI wiring
- [x] `main.py` — `store_order` with channel_id/source_chat_id/source_message_id
- [x] `main.py` — `register_ticket()` on successful execution
- [x] `.env.example` — `TRADE_TRACKER_POLL_SECONDS`

### Documentation
- [x] `ARCHITECTURE.md` — updated ParsedSignal fields
- [x] `PLAN.md` — P6 phase
- [x] `TASKS.md` — P6 tasks
- [x] `CHANGELOG.md` — v0.6.0 with breaking change notice

## Medium Priority (v0.7.0)
- [x] Per-channel metrics (`dict[str, _SessionMetrics]`) + heartbeat breakdown
- [x] Message edit behavior — full `_process_edit` wired (fingerprint lookup → cancel → reprocess)
- [x] `store_event()` channel_id wiring — all 11 call sites
- [x] TradeTracker partial close reply throttle (60s cooldown)
- [x] `cancel_by_fingerprint()` on `OrderLifecycleManager`
- [x] Parser overrides per detector in `channels.json` — ⏸ **deferred** (overengineering, no concrete need)
- [x] Command response via Telegram — reply to source chat + admin log
- [x] Position manager Telegram alerts — breakeven/trailing/partial close with throttle + channel context

### P7: Reply-Based Signal Management (v0.8.0)
- [x] Reply action parser (`reply_action_parser.py`) — close/exit/đóng, SL/TP price, BE, close N%
- [x] Reply command executor (`reply_command_executor.py`) — per-ticket operations with position check
- [x] Telegram listener reply_to_msg_id forwarding (ReplyCallback)
- [x] Storage `get_orders_by_message()` — multi-order lookup
- [x] TradeTracker reply-closed suppression with 5min TTL
- [x] main.py `_process_reply()` — multi-order, channel guard, grouped results

## Completed (from previous phases)
- [x] All P0 tasks (documentation foundation)
- [x] All P1 tasks (signal parser pipeline, validation, risk manager, storage, tooling)
- [x] All P2 tasks (trade executor, order builder, Telegram listener, lifecycle manager, watchdog, pipeline wiring)
- [x] All P3 tasks (dry-run, circuit breaker, alerting, storage hardening, signal lifecycle DB, entry drift guard, execution metrics, ENV sync, session metrics, heartbeat log)
- [x] All P4 tasks (daily risk guard, startup position sync, VPS runbook, monitoring doc, log rotation validation, update procedure)
- [x] All P5 tasks (exposure guard, dynamic deviation, position manager, management commands)
- [x] All P5 Bug Fixes (exposure guard TradeExecutor delegation, dynamic deviation wiring)
