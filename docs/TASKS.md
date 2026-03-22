# TASKS

## Current Phase
- `Dashboard V2` ✅ COMPLETE (v0.15.0)

### Dashboard V2 — React SPA
- [x] Project scaffold (Vite + React 19)
- [x] Design system (dark glassmorphism, 3 CSS files)
- [x] API client + 13 TanStack Query hooks
- [x] Navbar + StatCard + ChartCard components
- [x] Overview page (equity curve, daily PnL, win/loss donut, channels, active)
- [x] Analytics page (PnL distribution, drawdown, symbol bars, activity)
- [x] Channels page (comparison bar, interactive cards, daily drill-down)
- [x] Symbols page (performance table, PnL ranking, radar)
- [x] Trades page (multi-filter, paginated table, CSV export)
- [x] Settings page (connection status, API key, about)
- [x] Build verification (2773 modules, 249kB gzip)

## Previous Phase
- `PR Review Bug Fixes` ✅ COMPLETE (v0.14.1)

### PR Review Fixes
- [x] R3: `position_manager` → `position_mgr` typo (13 refs, main.py)
- [x] R2: V5 migration — add `symbol` column to orders table (storage.py)
- [x] R1: Single-mode `store_order()` + `register_ticket()` (pipeline.py)
- [x] R4: Defer `_restore_groups_from_db()` to after MT5 init (position_manager.py + main.py)
- [x] R5: Strip sub-fingerprint before signal lookup (trade_tracker.py)
- [x] R6: Footer version v0.12.0 → v0.14.0 (base.html)
- [x] R7: Narrow OperationalError catch (queries.py)
- [x] R8: Add channels.json to .gitignore
- [x] R9: Poll immediately on TradeTracker start (trade_tracker.py)
- [x] R10: Fix DASHBOARD.md channel-list response format

## Previous Phase
- `P10 - Smart Signal Group Management` ✅ COMPLETE

### P10 Phase 1: Models + Routing (P10a)
- [x] `core/models.py` — OrderGroup dataclass + GroupStatus enum
- [x] `core/position_manager.py` — _groups dict, _ticket_to_group, _check_positions routing

### P10 Phase 2: Config (P10b)
- [x] `config/channels.example.json` — 6 new config fields (group_trailing_pips, sl_mode, etc.)

### P10 Phase 3: Group SL Logic (P10c)
- [x] `core/position_manager.py` — _manage_group, _calculate_group_sl, _modify_group_sl

### P10 Phase 4: OrderBuilder STOP Filter (P10d)
- [x] `core/order_builder.py` — allowed_types + zone params for STOP→MARKET/LIMIT fallback

### P10 Phase 5: Pipeline Integration (P10e)
- [x] `core/pipeline.py` — _register_group_from_results + re-entry add_order_to_group

### P10 Phase 6: Reply Enhancement (P10f)
- [x] `core/position_manager.py` — close_selective_entry + apply_group_be
- [x] `main.py` — interceptor in _do_process_reply for selective close

### P10 Phase 7: DB Persistence (P10g)
- [x] `core/storage.py` — V4 migration signal_groups + CRUD methods
- [x] `core/position_manager.py` — wire storage calls (store/update/complete)

### P10 Documentation
- [x] `CHANGELOG.md` — v0.10.0
- [x] `docs/TASKS.md` — updated

## Previous Phase

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
