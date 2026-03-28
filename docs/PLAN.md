# PLAN

## Current Phase
- Phase: `Admin Bot Panel`
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

### P10 - Smart Signal Group Management
- Goal:
  - Merge group management into PositionManager. Every signal = 1 managed group.
  - Coordinated group SL (zone/trail/signal), selective close via reply, auto-BE.
- Major deliverables:
  - `core/models.py` — `OrderGroup` dataclass, `GroupStatus` enum
  - `core/position_manager.py` — group-aware routing, register_group, group trailing SL,
    _calculate_group_sl (zone/signal/fixed/trail), _modify_group_sl (atomic apply to all tickets),
    close_selective_entry (strategy-based), apply_group_be, query methods, DB wiring
  - `core/pipeline.py` — _register_group_from_results, re-entry add_order_to_group
  - `core/order_builder.py` — order_types_allowed filter (STOP→MARKET/LIMIT fallback)
  - `main.py` — P10f selective close interceptor in _do_process_reply
  - `core/storage.py` — Migration V4: `signal_groups` table + 5 CRUD methods
  - `config/channels.example.json` — 6 new config fields
  - Restart recovery: `_restore_groups_from_db()` loads active groups on startup
- Status: `complete`

### Dashboard V2 Enhancements (v0.16.0–v0.16.1)
- Goal:
  - Add signal lifecycle management, data management, and advanced analytics to Dashboard V2.
- Major deliverables:
  - **Signal Lifecycle page** (`Signals.jsx`) — expandable grouped view, detail modal, cascade delete
  - **8 new API endpoints** — signals CRUD, data management (clear table/all)
  - **ConfirmModal** — shared glassmorphism popup for destructive actions
  - **DashboardDB write ops** — `_connect_rw()` for delete operations on read-only DB class
  - **Win Rate Gauge** — radial bar chart on Overview
  - **Signal Breakdown** — PLECTO-style table card (executed/rejected/failed counts)
  - **PnL by Weekday** — bar chart (Mon–Fri)
  - **Chart toggle** — Customize dropdown to show/hide any chart, persisted to localStorage
  - CORS updated to allow DELETE method
- Status: `complete`

### Trading Logic Gaps (v0.18.0–v0.19.0)
- Goal:
  - Close logic gaps in order execution, re-entry strategy, and position management.
  - Harden range-mode multi-order workflow with safety guards.
- Major deliverables:
  - **G1**: Min SL distance guard — reject orders too close to SL (`pipeline.py`)
  - **G2**: Default SL from zone — auto-generate SL from entry zone bounds (`pipeline.py`)
  - **G3**: Reply `+pip` parser — parse `+30`, `+50 pip` as SECURE_PROFIT (`reply_action_parser.py`)
  - **G4**: Secure profit group — close worst entry + BE remaining (`position_manager.py`)
  - **G5**: Re-entry tolerance — trigger within N pips of level (`range_monitor.py`)
  - **G6**: Cancel pending plans on reply — CLOSE/SECURE_PROFIT cancels plans (`signal_state_manager.py`)
  - **G7**: Max re-entry distance guard — skip if price > N pips past level (`pipeline.py`)
  - **G8**: Force MARKET for re-entries — P2/P3 bypass MARKET_TOLERANCE_POINTS (`pipeline.py`)
  - **G9**: Step-based P2/P3 levels — configurable step from P1 (`entry_strategy.py`)
  - **G10**: Multi-trigger — REVERTED, individual cross detection retained (`range_monitor.py`)
  - **G11**: SL breach cancel — cancel all pending when SL hit (`range_monitor.py`)
  - **G12a**: `per_entry` volume split — each plan gets full lot size (`entry_strategy.py`)
  - **G12b**: Reply BE lock pips — configurable BE offset per channel (`reply_command_executor.py`)
  - 8 new config keys in `channels.json` (rules + strategy sections)
- Status: `complete`

## Phase Completion Rule
- Current phase is complete only when all `High Priority` and `Medium Priority` tasks in `docs/TASKS.md` are checked.
- On completion:
  - Mark current phase `complete`
  - Move next phase to `in progress`
  - Regenerate `docs/TASKS.md` for the new current phase

## What's Next

### Done
- v0.7.0: per-channel metrics, message edit wiring, store_event channel_id, reply throttle
- v0.7.1: command response via Telegram, position manager alerts with throttle
- v0.8.0: reply-based signal management (reply to signal → close/SL/TP/BE on specific trade)
- v0.9.0: channel-driven strategy architecture (P9)
- v0.10.0: smart signal group management (P10) + restart recovery
- v0.10.1: codebase audit cleanup (dead code, swallowed exceptions, outdated docs)
- v0.11.0: edit & delete message handling (P10.1) — group-aware cancel, MessageDeleted listener
- v0.12.0: web analytics dashboard (P11) — FastAPI + Jinja2 + Chart.js, 3 pages, 7 API endpoints
- v0.13.0: dashboard enhancement (P12) — channel names, equity curve, symbol stats, CSV export, basic auth
- v0.14.0: bot hardening (P13) — health check endpoint, runtime stats, watchdog+CB bridge
- v0.15.0: Dashboard V2 — React SPA (6 pages, Recharts, TanStack Query, Framer Motion)
- v0.16.0: Signal Lifecycle page — expandable table, detail modal, cascade delete, 8 API endpoints
- v0.16.1: Overview enhancements — Win Rate Gauge, Signal Breakdown, PnL by Weekday, chart toggle
- v0.16.2: Bug fixes — API 404 status codes, sub-fingerprint SQL, CSS fixes, `/api/signal-status-counts` endpoint
- v0.16.3: Dashboard V2 unit tests — 130 Vitest tests across 11 files
- v0.16.4: Bot system test case documentation — 254 test cases across 25 modules
- v0.16.5: Bot system unit tests — 249 pytest tests across 17 files
- v0.16.6: Code review fixes — helper extraction (`Overview.helpers.js`, `Analytics.helpers.js`), test alignment
- v0.16.7: Documentation audit — 21 fixes across 14 files
- v0.17.0: Signal analysis fixes — fingerprint dedup, "Now" keyword MARKET, `execute_all_immediately`
- v0.18.0: Trading logic gaps G1-G6 — SL guard, default SL, +pip parser, secure profit, re-entry tolerance, cancel pending
- v0.19.0: Trading logic gaps G7-G12 — max re-entry distance, force MARKET, step levels, SL breach cancel, per_entry split, reply BE lock
- v0.19.1: Reply CLOSE_PROFIT action, CANCEL reply action, cancel ALL/SYMBOL management commands, trailing text support in reply parser
- v0.20.0: Parse hardening — typo-tolerant side detection (SEL/SELLL/BBUY/BYU), emoji-to-space cleaner, centralized `estimate_pip_size()` replacing 12 `point * 10` heuristics
- v0.21.0: SYMBOL_SUFFIX support, 3-step ticket resolution in TradeTracker, `dynamic_deviation_multiplier` exposure
- v0.22.0: Peak profit tracking per signal group with DB persistence (migration V6), trailing alert threshold 5→10 pips
- v0.22.1: SL buffer + max SL distance cap, market snapshot at entry (migration V7)
- v0.22.2: Breakeven diagnostic logging, parse fix for `is_now` flag
- v0.22.3: Full documentation audit — 8 docs rewritten/updated, R11 milestone added to ROADMAP
- v0.23.0: Telegram Bot API admin panel — `core/admin_bot.py`, inline keyboard order management, alert/debug routing via Bot API, `telegram_alerter.py` rewritten



### Upcoming

#### P14 — Multi-Account Support
- **Why**: Chạy nhiều account broker từ 1 bot instance
- **Scope**: Architecture change lớn, ~800+ LOC, high risk
- **Deliverables**:
  - Account config trong settings (list of MT5 accounts)
  - Per-account TradeExecutor instances
  - Per-account risk sizing
  - Dashboard: per-account filtering

### Deferred
- Parser overrides per detector (no concrete need yet)
- WebSocket live updates for dashboard (polling 30s đủ dùng)
- Dockerize dashboard
- Mobile PWA
- Migrate SQLite → PostgreSQL

