# TASKS

## Current Phase
- `Reply Parser Expansion` ✅ COMPLETE (v0.21.5)

### v0.21.5 — Reply Parser Expansion
- [x] Expand `_SECURE_PROFIT` regex to match `done Npips`, `near N pips` formats
- [x] Add `_CLOSE_PROFIT` pattern for `+Npips close all/entry` → CLOSE action
- [x] Parse priority: CLOSE_PROFIT before SECURE_PROFIT
- [x] Test 21/21 cases pass
- [x] Typo audit across codebase — no issues found
- [x] Update CHANGELOG

## Previous Phase
- `Bug Fixes` ✅ COMPLETE (v0.21.2)

### v0.21.2 — Premature Group Completion Fix
- [x] Fix `_check_positions()` — check `orders_get()` (pending) alongside `positions_get()` (filled)
- [x] Fix `_restore_groups_from_db()` — same pending order check
- [x] Update CHANGELOG

### v0.21.1 — Reply Handler Bug Fixes
- [x] Fix `get_channel_rules()` → `get_rules()` typo in `main.py:1346`
- [x] Fix `_SECURE_PROFIT` regex to handle trailing emojis (`reply_action_parser.py`)
- [x] Fix `reply_to_message()` chat_id string→int for Telethon (`telegram_alerter.py`)
- [x] Add 5 new SECURE_PROFIT test cases
- [x] Update CHANGELOG

## Previous Phase
- `Codebase Stability Audit` ✅ COMPLETE (v0.19.1)

### v0.19.1 — Stability Audit (C1-C6, M1-M5)
- [x] C1: Prune closed tickets from PositionManager tracking dicts (`position_manager.py`)
- [x] C2: Clean stale entries in TradeTracker dicts (`trade_tracker.py`)
- [x] C3: Clean stale debounce entries in RangeMonitor (`range_monitor.py`)
- [x] C4: Remove dead `midnight_next` month-end crash (`daily_risk_guard.py`)
- [x] C5: Add `check_same_thread=False` to SQLite (`storage.py`)
- [x] C6: TTL-remove completed groups from PositionManager (`position_manager.py`)
- [x] M1: Cache entity in TelegramAlerter (`telegram_alerter.py`)
- [x] M2: Remove 6 dead convenience methods (`telegram_alerter.py`)
- [x] M5: Fix `is_enabled` to check channel configs (`position_manager.py`)
- [x] Update CHANGELOG
- [x] Update TASKS.md

## Previous Phase
- `Trading Logic Gaps` ✅ COMPLETE (v0.19.0)

### v0.19.0 — Trading Logic Gaps (G1-G12)

#### G1-G6 (from v0.18.0)
- [x] G1: Min SL Distance Guard — skip orders when price too close to SL (`pipeline.py`)
- [x] G2: Default SL from Zone — auto-generate SL from entry zone bounds (`pipeline.py`)
- [x] G3: Reply `+pip` Parser — parse `+30`, `+50 pip` as SECURE_PROFIT (`reply_action_parser.py`)
- [x] G4: Secure Profit Group — close worst entry + BE remaining (`position_manager.py`, `main.py`)
- [x] G5: Re-entry Tolerance — trigger within N pips of level (`range_monitor.py`, `main.py`)
- [x] G6: Cancel Pending Plans on Reply — CLOSE/SECURE_PROFIT cancels plans (`signal_state_manager.py`, `main.py`)

#### G7-G11 (new)
- [x] G7: Max Re-entry Distance Guard — skip re-entry if price > `max_reentry_distance_pips` past level (`pipeline.py`)
- [x] G8: Force MARKET for Re-entries — P2/P3 always MARKET, bypass `MARKET_TOLERANCE_POINTS` (`pipeline.py`)
- [x] G9: Step-based P2/P3 Levels — `reentry_step_pips > 0` → P2 = P1 + N×step (`entry_strategy.py`)
- [x] G10: ~~Multi-trigger on Scan~~ — **REVERTED**, each plan triggers individually via cross detection (`range_monitor.py`)
- [x] G11: SL Breach → Cancel All — if price crosses SL, cancel all pending plans for signal (`range_monitor.py`)

#### G12 (additional improvements)
- [x] G12a: `per_entry` volume split — each plan gets full `FIXED_LOT_SIZE` instead of splitting total (`entry_strategy.py`)
- [x] G12b: Reply BE Lock Pips — reply "be" sets SL = entry ± N pip instead of exact entry (`reply_command_executor.py`, `main.py`)

#### Config & Docs
- [x] Update `channels.json` — 8 new config keys across rules + strategy
- [x] Update CHANGELOG
- [x] Update TASKS.md
- [x] Update PLAN.md
- [x] Update ARCHITECTURE.md

## Previous Phases
- `Signal Analysis Fixes` ✅ COMPLETE (v0.17.0)

### v0.17.0 — Signal Analysis Fixes (P0 + P1 + P2)
- [x] P0: Fingerprint dedup — add `source_message_id` to hash (`parser.py`)
- [x] P1: "Now" keyword → force MARKET when price in zone (`entry_detector.py`, `order_builder.py`, `models.py`)
- [x] P2: `execute_all_immediately` option for range mode (`pipeline.py`)
- [x] Update `channels.json` with new config keys
- [x] Update CHANGELOG
- [x] Update TASKS.md

## Previous Phases
- `Documentation Audit & Fix` ✅ COMPLETE (v0.16.7)

### v0.16.7 — Documentation Audit (21 fixes across 14 files)
- [x] Fix `MARKET_TOLERANCE_POINTS` default `30.0` → `5.0` (4 locations)
- [x] Update version `v0.16.1` → `v0.16.6` in PROJECT.md, README.md, DASHBOARD_FEATURES.md, FLOW_AND_SETUP_GUIDE.md, App.jsx, LOGIC_SIGNAL_PARSER.md, ARCHITECTURE.md
- [x] Add missing `/api/signal-status-counts` to ARCHITECTURE.md + DASHBOARD_FEATURES.md
- [x] Add missing `tests/`, `run.py` to PROJECT.md structure
- [x] Add v0.16.2–v0.16.6 entries to PLAN.md Done list
- [x] Fix P10_FEATURE_SPEC.md target version `v1.0.0` → `v0.10.0`
- [x] Add P10 group events to OBSERVABILITY.md
- [x] Add `run.py` launcher mention to DEPLOY.md
- [x] Add R9 (Dashboard) + R10 (Tests) milestones to ROADMAP.md
- [x] Add helper extraction + unit test notes to ARCHITECTURE.md

## Previous Phases
- `Codex + Copilot Review Fixes` ✅ COMPLETE (v0.16.6)

### v0.16.6 — Code Review Fixes (Codex P1 + P2, Copilot #2-#6)
- [x] P1: Add `signalStatusCounts` to `api/client.js`
- [x] P2: Extract `Overview.helpers.js` + `Analytics.helpers.js`
- [x] P2: Wire JSX components to import helpers
- [x] P2: Update tests to import from production helpers
- [x] Copilot #2: Remove unused `ValidationResult` import
- [x] Copilot #3: Fix permissive TP test assertion
- [x] Copilot #4: Fix word boundary test + comment
- [x] Copilot #5: Simplify client.test.js import
- [x] Copilot #6: Fix misleading test title
- [x] **Verified: 249 Python + 130 JS tests pass**

## Previous Phases
- `Bot System Unit Tests` ✅ COMPLETE (v0.16.5)

### v0.16.5 — Bot System Unit Tests (Python)
- [x] Install pytest, create `pytest.ini` + `conftest.py`
- [x] `tests/signal_parser/test_cleaner.py` — 13 tests
- [x] `tests/signal_parser/test_side_detector.py` — 12 tests
- [x] `tests/signal_parser/test_symbol_detector.py` — 13 tests
- [x] `tests/signal_parser/test_entry_detector.py` — 18 tests
- [x] `tests/signal_parser/test_sl_detector.py` — 10 tests
- [x] `tests/signal_parser/test_tp_detector.py` — 14 tests
- [x] `tests/signal_parser/test_parser.py` — 17 tests
- [x] `tests/test_signal_validator.py` — 24 tests
- [x] `tests/test_risk_manager.py` — 12 tests
- [x] `tests/test_circuit_breaker.py` — 11 tests
- [x] `tests/test_command_parser.py` — 17 tests
- [x] `tests/test_reply_action_parser.py` — 25 tests
- [x] `tests/test_models.py` — 17 tests
- [x] `tests/test_entry_strategy.py` — 24 tests
- [x] `tests/test_channel_manager.py` — 11 tests
- [x] `tests/test_exposure_guard.py` — 8 tests
- [x] **Total: 249 tests passed, 0 failures**

## Previous Phases
- `Bot System Test Case Documentation` ✅ COMPLETE (v0.16.4)

### v0.16.4 — Bot System Test Cases
- [x] Analyze all 27 core Python modules
- [x] Analyze 7 signal_parser submodules
- [x] Write `tests/TEST_CASES.md` — 254 test cases across 25 sections
- [x] Update docs/TASKS.md
- [x] Update CHANGELOG.md

## Previous Phase
- `Dashboard V2 Unit Tests` ✅ COMPLETE (v0.16.3)

### v0.16.3 — Dashboard V2 Unit Tests
- [x] Test framework setup — Vitest + React Testing Library + jsdom
- [x] `test/utils/format.test.js` — 5 functions, 29 test cases
- [x] `test/api/client.test.js` — fetchApi, URL construction, API key, DELETE, 12 test cases
- [x] `test/hooks/useApi.test.jsx` — 17 hooks, 20 test cases
- [x] `test/charts/ChartPrimitives.test.jsx` — PremiumTooltip, BarLabel, PieLabel, 17 test cases
- [x] `test/components/ChartCard.test.jsx` — 5 test cases
- [x] `test/components/ConfirmModal.test.jsx` — 7 test cases
- [x] `test/components/Navbar.test.jsx` — 4 test cases
- [x] `test/components/SparkCard.test.jsx` — 8 test cases
- [x] `test/components/StatCard.test.jsx` — 6 test cases
- [x] `test/pages/Overview.helpers.test.js` — 10 test cases (weekday, merge, monthly)
- [x] `test/pages/Analytics.helpers.test.js` — 12 test cases (weekly, histogram, drawdown, cumulative)
- [x] `docs/RULES.md` updated with test guidelines

## Previous Phase
- `Dashboard V2 Enhancements` ✅ COMPLETE (v0.16.1)

### v0.16.1 — Overview Enhancements
- [x] Win Rate Gauge — radial bar chart with center % + W/L counts
- [x] Signal Breakdown — table card (executed/rejected/failed/received counts)
- [x] PnL by Weekday — bar chart Mon–Fri with cumulative PnL per trading day
- [x] Chart toggle — "Customize" dropdown to show/hide any chart, persisted to localStorage
- [x] Signals nav icon changed from Workflow → GitBranch

### v0.16.0 — Signal Lifecycle Page
- [x] Backend: `queries.py` — `get_signals_paginated()`, `get_signal_lifecycle()`, `_connect_rw()` for write ops
- [x] Backend: `queries.py` — `delete_signal_cascade()`, `delete_order_by_id()`, `delete_trade_by_id()`
- [x] Backend: `queries.py` — `clear_table()`, `clear_all_data()`, `get_table_counts()`
- [x] Backend: `routes.py` — 8 new API endpoints (GET/DELETE signals, orders, trades, data management)
- [x] Backend: `dashboard.py` — CORS updated to allow DELETE method
- [x] Frontend: `ConfirmModal.jsx` — shared confirmation popup (glassmorphism, type-to-confirm)
- [x] Frontend: `Signals.jsx` — expandable grouped signal table + SignalDetailModal
- [x] Frontend: `client.js` — DELETE method support + 8 new API methods
- [x] Frontend: `useApi.js` — `useSignals`, `useSignalDetail`, `useTableCounts` hooks
- [x] Frontend: `App.jsx` + `Navbar.jsx` — added `/signals` route + nav link

## Previous Phase
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
