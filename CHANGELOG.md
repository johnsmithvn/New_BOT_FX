# CHANGELOG
## 0.24.0 - 2026-03-29

### Added
- **Auto partial close at N pips** — new position management mode that closes a fixed lot when unrealized profit reaches a configurable pip threshold
  - `PARTIAL_CLOSE_TRIGGER_PIPS`: profit pips to trigger (0 = disabled, uses legacy TP1-based logic)
  - `PARTIAL_CLOSE_LOT`: fixed lot to close when trigger hit (e.g. 0.02)
  - After close: TP stays as-is, SL stays as-is, trailing SL continues protecting
  - Each position only triggers once (same `_partially_closed` set)
  - Guard: `PARTIAL_CLOSE_LOT >= pos.volume` → log warning + skip
  - When `PARTIAL_CLOSE_TRIGGER_PIPS > 0` and `PARTIAL_CLOSE_LOT > 0`, overrides legacy `PARTIAL_CLOSE_PERCENT` (TP1-based)
  - Telegram alert: `✂️ Auto Partial Close` with lot/remaining/pips info
- New log events: `auto_partial_close_executed`, `auto_partial_close_failed`, `partial_close_lot_exceeds_volume`

### Files Modified
- `config/settings.py` — 2 new fields in SafetyConfig
- `core/position_manager.py` — new `_apply_partial_close_by_pips()` method, routing logic in `_manage_individual()`
- `.env` — 2 new env vars
- `.env.example` — 2 new env vars

## 0.23.0 - 2026-03-28

### Added
- **Telegram Bot API admin panel** (`core/admin_bot.py`) — interactive inline keyboard for order management
  - `/start` or `/menu` → 4-button admin panel
  - 📋 List open positions (symbol, side, volume, PnL, ticket)
  - ⏳ List pending orders (symbol, type, price, age, ticket)
  - ❌ Cancel all pending orders (with confirmation step)
  - 🔴 Close all orders (with confirmation step)
  - Security: restricted to `TELEGRAM_BOT_ADMIN_ID` only
- New env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_ADMIN_ID`
- New dependency: `python-telegram-bot>=20.0`

### Changed
- **`telegram_alerter.py` rewritten** — all alerts/debug/PnL now route through Bot API instead of Telethon user session
  - Removed Telethon dependency from alerter
  - `reply_to_message()` now sends to admin bot chat (flat message, no longer reply-under-signal)
  - `set_client()` removed, replaced by `set_bot()`
- **`main.py`** — AdminBot wired into component initialization, startup, and shutdown lifecycle
- **`settings.py`** — added `bot_token` and `bot_admin_id` to `TelegramConfig`

### Files Modified
- `core/admin_bot.py` — NEW
- `core/telegram_alerter.py` — rewritten (Bot API transport)
- `main.py` — AdminBot wiring
- `config/settings.py` — 2 new config fields
- `.env.example` — 2 new env vars
- `requirements.txt` — python-telegram-bot added

## 0.22.3 - 2026-03-27

### Changed
- **ARCHITECTURE.md rewrite** — entire document rewritten to match v0.22.2 codebase state:
  - Added 6 undocumented modules: `core/models.py`, `core/health.py`, `core/circuit_breaker.py`, `core/telegram_alerter.py`, `core/reply_action_parser.py`, `run.py`
  - Updated dashboard structure: `dashboard/` → `dashboard/api/routes.py` + `dashboard/db/queries.py`
  - Expanded API endpoints table from 8 to 20 endpoints
  - Corrected data contracts: added `entry_range`, `is_now`, `parse_confidence`, `parse_source` on `ParsedSignal`
  - Updated data flow from 8 to 12 steps
  - Updated storage migrations V1–V4 → V1–V7
  - Updated position manager: trailing alert threshold 5→10, peak profit tracking, P10 group management details
  - Added pipeline features: G2 default SL, SL buffer, SL cap, force MARKET re-entries
  - Added reply action types: SECURE_PROFIT, CANCEL, CLOSE_PROFIT
  - Added Dashboard V2 section with full page list, chart toggle, signal lifecycle, unit tests
- **OBSERVABILITY.md rewrite** — added 7 new event sections:
  - Message Delete events (v0.11.0)
  - Pipeline Guard events (v0.19.0–v0.22.1): `default_sl_generated`, `sl_distance_capped`, `sl_buffer_applied`, `entry_skipped_sl_too_close`
  - Peak Profit events (v0.22.0): `group_peak_updated`, `group_peak_final`
  - Health & Infrastructure events: health server, circuit breaker state, position manager lifecycle, alert system, schema migrations
  - Expanded existing sections with missing events
  - Corrected trailing alert threshold documentation (5→10 pips)
- **DASHBOARD_FEATURES.md** — fixed 7 outdated API response formats:
  - `/api/overview` response: added `total_signals`, `total_swap`, `total_pnl`, `last_trade_time`
  - `/api/active` response: added `fingerprint`, `entry_prices`, `current_group_sl`, `sl_mode`, `created_at`
  - 4 DELETE endpoints: corrected response format to `{ok: true, deleted: {...}}`
  - Settings version corrected (v0.16.6 → v0.16.2 hardcoded)
- **ENV_BACKGROUND_TASKS.md** — added 3 missing background tasks (TradeTracker, Heartbeat, HealthCheckServer), 10+ missing env vars, new sections (Exposure Guard, Dashboard, Watchdog)
- **FLOW_AND_SETUP_GUIDE.md** — version v0.16.6→v0.22.3, added 7 strategy keys (v0.19.0), 8 rules keys (v0.10.0–v0.19.0), `per_entry` volume split, expanded decision table (+5 rows), expanded file structure (+14 entries)
- **MONITORING.md** — corrected trailing threshold 5→10 pips, removed dead alerts (`bot_started`/`bot_stopped`), added 8 new alerts (group, secure profit, SL breach, peak, health), expanded log queries, added health endpoint to data sources
- **ROADMAP.md** — added R11 milestone (Trading Logic Hardening & Observability v0.19.0–v0.22.x)
- **PLAN.md** — updated current phase to Documentation Audit, added v0.19.1–v0.22.3 to Done list (+7 entries)
- **PROJECT.md** — version v0.16.6→v0.22.3, added 20+ feature lines (reply actions, pipeline guards, peak profit, dashboard, health endpoint), expanded tech stack
- **LOGIC_PIPELINE_DEEP_DIVE.md** — added 4 missing ParsedSignal fields (`entry_range`, `is_now`, `parse_confidence`, `parse_source`), added v0.19.0+ pipeline guard notice (G1-G12)

### Files Modified
- `docs/ARCHITECTURE.md` — full rewrite
- `docs/OBSERVABILITY.md` — full rewrite
- `docs/DASHBOARD_FEATURES.md` — API response corrections
- `docs/ENV_BACKGROUND_TASKS.md` — full rewrite
- `docs/FLOW_AND_SETUP_GUIDE.md` — version + config key updates
- `docs/MONITORING.md` — alert catalog + log queries update
- `docs/ROADMAP.md` — R11 milestone added
- `docs/PLAN.md` — phase + Done list update
- `docs/PROJECT.md` — version + features + tech stack update
- `docs/logic/LOGIC_PIPELINE_DEEP_DIVE.md` — ParsedSignal + guards update

## 0.22.2 - 2026-03-27

### Changed
- **Breakeven diagnostic logging** — `reply_breakeven_fail` and `reply_breakeven_ok` log events now include `entry`, `new_sl`, `bid`, `ask`, `lock_pips` fields for post-mortem analysis. Previously only logged `ticket` and `retcode`, making it impossible to determine why MT5 rejected the SL modification (e.g. retcode 10016 INVALID_STOPS).
- **Secure profit diagnostics** — `secure_profit_single` log event now includes `be_result` (success/fail string from executor), `bid`, `ask` so breakeven failures during `+pip` reply are immediately visible without cross-referencing logs.

### Fixed
- **Critical: Emoji-adjacent keywords not parsed** — `_strip_emoji()` in `cleaner.py` deleted emoji characters, merging adjacent words (e.g. `Now🔼BUY` → `NowBUY`). `\bBUY\b` regex then failed to match. Fix: replace emoji with space instead of empty string (`Now🔼BUY` → `Now BUY`).
- **Typo-tolerant side detection** — Added fuzzy matching for common BUY/SELL typos: `SEL`, `SELLL`, `SEEL`, `SSEL`, `SSELL`, `SEELL` → SELL; `BBUY`, `BUUY`, `BYU` → BUY. Intentionally excludes `BY`/`BU` to avoid false positives.
- **Cancel reply with trailing text** — `_CANCEL` regex used `$` (full string match) so `Cancel wait😍😍` was ignored as `reply_not_action`. Changed to `\b` (word boundary) to allow trailing words.
- **Entry detector didn't recognize typo side keywords** — `entry_detector.py` had its own `BUY|SELL` regex that didn't include `SEL` and other typos. Side was detected correctly but entry price extraction failed. Unified side keywords via shared `_SIDE_KW` constant.
- **SECURE_PROFIT/CANCEL unhandled in executor** — `reply_command_executor.execute()` had no case for `SECURE_PROFIT` or `CANCEL`, falling through to `Unknown action`. Added handlers: `SECURE_PROFIT` → breakeven, `CANCEL` → no-op for open positions.

### Files Modified
- `core/reply_command_executor.py` — `_breakeven()` method enhanced logging
- `core/position_manager.py` — `secure_profit_group()` single-order branch enhanced logging
- `core/signal_parser/cleaner.py` — `_strip_emoji()` replaces with space instead of empty string
- `core/signal_parser/side_detector.py` — Added `SEL` alias for `SELL`
- `core/signal_parser/entry_detector.py` — Unified side keywords via `_SIDE_KW` constant
- `core/reply_action_parser.py` — `_CANCEL` regex relaxed to allow trailing text

## 0.22.1 - 2026-03-26

### Fixed
- **Peak profit tracking** — `_update_group_peak()` and `get_group_peak()` were never implemented in `position_manager.py` despite being called at line 511 and referenced by `trade_tracker.py`. All 17 trades had `peak_pips: NULL`. Now properly tracks and persists peak unrealized P&L per group.
- **Phantom trades** — `trade_tracker._resolve_order()` now has 3-step lookup (ticket → position_ticket → MT5 history). Previously LIMIT orders that filled created orphan trades with `position_ticket: None` (50% of all orders).

### Added
- **SL buffer** — `strategy.sl_buffer_pips` widens SL by N pips away from entry to avoid spike-triggered SL hits. BUY: SL moves lower, SELL: SL moves higher. Uses `estimate_pip_size()` for consistent pip units. Applied in both `execute_signal_plans()` and `handle_reentry()` paths. Default: 0 (disabled). Logged as `sl_buffer_applied` event.
- **Max SL distance cap** — `strategy.max_sl_distance_pips` caps SL when signal SL is too far from entry. If SL distance > N pips, replaces SL with `default_sl_pips_from_zone`. Applied BEFORE `sl_buffer_pips`. Default: 0 (disabled). Logged as `sl_distance_capped` event.
- DB migration V7: `orders.volume`, `orders.bid`, `orders.ask` columns for market snapshot at entry time
- `store_order()` now accepts `volume`, `bid`, `ask` params — all 5 pipeline call sites updated
- MT5 `history_orders_get(position=)` fallback in `_resolve_order()` with auto position_ticket backfill

### Files Modified
- `core/position_manager.py` — added `_update_group_peak()`, `get_group_peak()`
- `core/storage.py` — V7 migration, `store_order()` expanded
- `core/pipeline.py` — 5 `store_order()` calls updated, `sl_buffer_pips` logic in 2 paths
- `core/trade_tracker.py` — 3-step `_resolve_order()` with MT5 history fallback
- `config/channels.json` — added `sl_buffer_pips: 0` to defaults

## 0.22.0 - 2026-03-26

### Added
- **Peak profit tracking** — position_manager now tracks the highest unrealized P&L per signal group during its lifetime
- DB migration V6: `signal_groups` and `trades` tables gain `peak_pips`, `peak_price`, `peak_time` columns; `trades` gains `entry_price`
- `Storage.update_group_peak()` persists peak data periodically (every +10p) and on group completion
- `PositionManager.get_group_peak()` exposes peak data for trade_tracker integration
- `trade_tracked` log event now includes `peak_pips` field

### Changed
- **Log spam reduction** — removed `daily_risk_guard_no_deals` log (was 270×/day), trailing log now only fires when SL moves ≥ 10 pips (was every movement, ~54×/day)
- `TradeTracker` now accepts `position_manager` param for peak data access
- `_TRAILING_ALERT_MIN_PIPS` increased from 5 to 10

### Files Modified
- `core/storage.py` — migration V6, `store_trade()` expanded, `update_group_peak()` added
- `core/position_manager.py` — `_group_peak` dict, `_update_group_peak()`, `get_group_peak()`, trailing log throttle
- `core/trade_tracker.py` — peak data + entry_price integration in `_process_closing_deal()`
- `core/daily_risk_guard.py` — removed noisy `daily_risk_guard_no_deals` log
- `main.py` — wire `position_manager` into `TradeTracker`
## 0.21.5 - 2026-03-25

### Changed
- **Reply parser expanded** — `_SECURE_PROFIT` regex now matches `done Npips` and `near N pips` formats (previously only `+N` prefix)
- **New `_CLOSE_PROFIT` pattern** — `+Npips close all` and `+Npips close entry XXXX` replies now correctly trigger CLOSE action instead of SECURE_PROFIT
- Parse priority: CLOSE_PROFIT checked before SECURE_PROFIT to prevent partial match

### Files Modified
- `core/reply_action_parser.py`

## 0.21.4 - 2026-03-25

### Fixed
- Fixed bug where `PositionManager` failed to resurrect a `COMPLETED` group when a re-entry order triggered after the original base order had expired or closed. `add_order_to_group()` now properly sets `GroupStatus.ACTIVE` and calls `Storage.reactivate_group_db()`. This ensures group reply commands (`+30pips`, `close`, etc.) work correctly for re-entry orders even if the base order was missed.

### Files Modified
- `core/position_manager.py`
- `core/storage.py`

## 0.21.3 - 2026-03-25

### Changed
- Removed all reply-to-source-channel logic — bot no longer tries to post messages in source signal channels (requires admin privileges). All trade outcomes and reply command results are now sent to admin chat only.

### Files Modified
- `main.py` — removed 6 `reply_to_message_sync()` calls
- `core/trade_tracker.py` — PnL reply now uses `send_debug()` (admin chat) instead of `reply_to_message()`

## 0.21.2 - 2026-03-25

### Fixed
- **Critical: Premature group completion** — `_check_positions()` only checked `mt5.positions_get()` (filled positions) when determining if a group is complete. Pending LIMIT/STOP orders (from `mt5.orders_get()`) were not checked, causing groups to be marked COMPLETED within seconds of registration. This stopped ALL auto SL management (breakeven, trailing) for positions that started as pending orders.
- Same fix applied to `_restore_groups_from_db()` — pending orders now count as alive during restart recovery.

### Files Modified
- `core/position_manager.py` — `_check_positions()` and `_restore_groups_from_db()` now check both `positions_get()` AND `orders_get()` before completing a group

## 0.21.1 - 2026-03-25

### Fixed
- **Critical: Reply handler crash** — `main.py:1346` called `get_channel_rules()` but `ChannelManager` only has `get_rules()`. Crashed ALL reply command execution (SL, close, BE, TP actions) with `AttributeError`.
- **SECURE_PROFIT regex** — `_SECURE_PROFIT` pattern used `$` anchor which rejected messages with trailing emojis/text (e.g. `+60pips🔼🔼🔼`). Changed to `\b` word boundary.
- **Trade outcome reply failure** — `telegram_alerter.py` passed string chat_id to Telethon `get_entity()` which requires `int` for numeric peer IDs. Added string→int conversion.

### Files Modified
- `main.py` — `get_channel_rules()` → `get_rules()`
- `core/reply_action_parser.py` — `_SECURE_PROFIT` regex `$` → `\b`
- `core/telegram_alerter.py` — chat_id string→int conversion in `reply_to_message()`
- `tests/test_reply_action_parser.py` — 5 new SECURE_PROFIT test cases

## 0.21.0 - 2026-03-24

### Added
- **CANCEL ALL** management command — cancels all pending limit/stop orders placed by the bot
- **CANCEL \<SYMBOL\>** — cancels pending orders for a specific symbol
- **Reply CANCEL** — reply "cancel", "hủy", "miss", "bỏ", "skip" to a signal message to cancel its pending orders + re-entry plans
- Parser matches: `CANCEL ALL`, `CANCELL ALL` (common typo), `HỦY ALL`, `HỦY TẤT CẢ`
- Executor uses `mt5.orders_get()` + `TRADE_ACTION_REMOVE` for clean order removal

### Files Modified
- `core/command_parser.py` — added `CANCEL_ALL`, `CANCEL_SYMBOL` enum + regex patterns
- `core/command_executor.py` — added `_cancel_all`, `_cancel_symbol`, `_cancel_order`, `_get_bot_orders`
- `core/reply_action_parser.py` — added `CANCEL` action type + regex pattern
- `main.py` — added CANCEL reply handler (cancel MT5 orders + re-entry plans by fingerprint)

## 0.20.1 - 2026-03-24

### Fixed
- **Critical: pip_size calculation broken for 3-digit gold brokers** (Exness XAUUSDm). All 12 instances of `point * 10` heuristic replaced with centralized `estimate_pip_size(symbol)` that uses symbol-name detection. The old heuristic gave `0.001 * 10 = 0.01` for 3-digit gold, but correct pip is `0.1`.
  - This caused valid signals to be rejected (e.g. 86 pip distance reported as 865 pips)
  - Also affected: breakeven, trailing stop, partial close, group SL, range monitor, entry strategy, pipeline guards

### Files Modified
- `utils/symbol_mapper.py` — new `estimate_pip_size(symbol)` function (single source of truth)
- `main.py` — use `estimate_pip_size` for live pip detection
- `core/position_manager.py` — 6 sites fixed (individual + group management)
- `core/pipeline.py` — 4 sites fixed (default SL, SL guard, re-entry guard, multi-order guard)
- `core/reply_command_executor.py` — 1 site fixed (breakeven reply)
- `core/entry_strategy.py` — removed broken `_estimate_pip_size(point)`, use centralized function
- `core/range_monitor.py` — 1 site fixed (re-entry tolerance)

## 0.20.0 - 2026-03-24

### Added
- **SYMBOL_SUFFIX** env var — append broker-specific suffix to all resolved symbols (e.g. `m` for Exness: `XAUUSD` → `XAUUSDm`). Set in `.env`, applied transparently by `SymbolMapper`.

### Files Modified
- `utils/symbol_mapper.py` — `symbol_suffix` parameter in constructor, applied in `resolve()`
- `main.py` — pass `SYMBOL_SUFFIX` env var to `SymbolMapper`
- `.env.example` — documented `SYMBOL_SUFFIX` key

## 0.19.1 - 2026-03-23

### Fixed
- **C1: PositionManager memory leak** — 5 tracking dicts (`_ticket_to_channel`, `_breakeven_applied`, `_partially_closed`, `_last_alert_time`, `_last_trailing_sl`) now pruned at end of each poll cycle for closed positions
- **C2: TradeTracker memory leak** — `_partial_reply_times` and `_reply_closed` dicts now TTL-cleaned each poll
- **C3: RangeMonitor memory leak** — `_last_trigger` debounce entries cleaned after 2× debounce age
- **C4: DailyRiskGuard month-end crash** — removed dead `midnight_next` variable that computed `day+1` (ValueError on 31st)
- **C5: SQLite thread safety** — added `check_same_thread=False` to `sqlite3.connect()`
- **C6: Completed groups never freed** — groups with COMPLETED status now removed after 1h TTL
- **M1: TelegramAlerter entity cache** — `get_entity()` for admin chat now cached (was called every alert)
- **M5: PositionManager `is_enabled` silent skip** — now checks channel-specific rules in `channels.json`, not just global settings; previously channel-only `breakeven_lock_pips: 30` was silently ignored

### Removed
- **M2: Dead convenience methods** — removed 6 unused async methods: `alert_circuit_breaker_opened/closed`, `alert_mt5_connection_lost`, `alert_mt5_reinit_exhausted`, `alert_bot_started/stopped`

### Files Modified
- `core/position_manager.py` (C1, C6, M5)
- `core/trade_tracker.py` (C2)
- `core/range_monitor.py` (C3)
- `core/daily_risk_guard.py` (C4)
- `core/storage.py` (C5)
- `core/telegram_alerter.py` (M1, M2)

## 0.19.0 - 2026-03-22

### Added
- **G1: Min SL Distance Guard** — skip placing orders if current price is within `min_sl_distance_pips` of SL. Applies to both initial multi-order execution and re-entry triggers. Config: `strategy.min_sl_distance_pips` (default: 0 = disabled). (`pipeline.py`)
- **G2: Default SL from Zone** — auto-generate SL from entry zone bounds when signal has no explicit SL. SELL: `zone_high + N pips`, BUY: `zone_low - N pips`. Config: `strategy.default_sl_pips_from_zone` (default: 0 = disabled). (`pipeline.py`)
- **G3: Reply `+pip` Parser** — parse `+30`, `+50 pip`, `+120 pips` replies as `SECURE_PROFIT` action. New `ReplyActionType.SECURE_PROFIT` and `pips` field on `ReplyAction`. (`reply_action_parser.py`)
- **G4: Secure Profit Group Action** — when admin replies `+pip`, close worst entry in group (SELL: lowest entry = least profitable), set BE on remaining orders. Single order: just set BE. New `secure_profit_group()` method. Config: `rules.secure_profit_action` (default: `close_worst_be_rest`). (`position_manager.py`, `main.py`)
- **G5: Re-entry Tolerance** — allow re-entry trigger within N pips of level, not just exact cross. Config: `strategy.reentry_tolerance_pips` (default: 0 = exact). (`range_monitor.py`, `main.py`)
- **G6: Cancel Pending Plans on Reply** — when CLOSE, SECURE_PROFIT, or BREAKEVEN reply succeeds, cancel all pending re-entry plans AND unfilled LIMIT/STOP orders on MT5. New `cancel_all_pending()` method. (`signal_state_manager.py`, `main.py`, `position_manager.py`)
- **G7: Max Re-entry Distance Guard** — skip re-entry if price has moved more than `max_reentry_distance_pips` past the plan level. Config: `strategy.max_reentry_distance_pips` (default: 0 = disabled). (`pipeline.py`)
- **G8: Force MARKET for Re-entries** — P2/P3 re-entries triggered by RangeMonitor always execute as MARKET orders, bypassing `MARKET_TOLERANCE_POINTS` check that could incorrectly place a LIMIT. (`pipeline.py`)
- **G9: Step-based P2/P3 Levels** — when `reentry_step_pips > 0`, P2/P3 levels calculated as P1 + N×step instead of spreading across zone. Config: `strategy.reentry_step_pips` (default: 0 = zone-spread). (`entry_strategy.py`)
- **G10: Multi-trigger** — ~~trigger all crossed levels simultaneously~~ **REVERTED**: each plan triggers individually via cross detection. (`range_monitor.py`)
- **G11: SL Breach → Cancel All** — if price crosses SL while plans are pending, cancel all pending plans for that signal. Prevents re-entries on invalidated signals. (`range_monitor.py`)
- **G12a: `per_entry` Volume Split** — new `volume_split` mode where each plan gets the full `FIXED_LOT_SIZE` instead of splitting total. Use case: `FIXED_LOT=0.01`, 3 entries → each 0.01. (`entry_strategy.py`)
- **G12b: Reply BE Lock Pips** — reply "be" now sets SL = entry ± N pip (profitable side) instead of exact entry. Config per channel: `rules.reply_be_lock_pips` (default: 1 pip). (`reply_command_executor.py`, `main.py`)

### Fixed
- **G12b: Reply BE guard** — reply "be" no longer overwrites a better SL. If auto BE already set SL to lock $3, reply "be" (lock $1) will keep the better SL and return info message. (`reply_command_executor.py`)
- **G4: Secure profit floor SL** — reply "+N pip" now sets remaining SL to closed entry ± lock (group floor) instead of per-position entry ± lock. SELL: closes lowest entry (worst), sets SL = closed_entry - lock for all remaining. Includes SL direction guard. (`position_manager.py`)
- **G7: sym_info scope** — max re-entry distance guard now fetches symbol_info independently instead of relying on G1's scoped variable. (`pipeline.py`)
- **G5: docstring** — range_monitor tolerance docstring corrected to match code: BUY = level + tol, SELL = level - tol. (`range_monitor.py`)
- **G1: cancelled plan leak** — plans skipped by min_sl_distance guard are now marked `cancelled` so RangeMonitor can't trigger them later. (`pipeline.py`)

### Changed
- `channels.json` — 8 new config keys:
  - **strategy**: `min_sl_distance_pips`, `default_sl_pips_from_zone`, `reentry_tolerance_pips`, `max_reentry_distance_pips`, `reentry_step_pips`
  - **rules**: `secure_profit_action`, `reply_be_lock_pips`
  - **volume_split**: added `per_entry` mode option
- Noval channel: `reentry_step_pips: 2`, `max_reentry_distance_pips: 10`, `reentry_tolerance_pips: 5`, `volume_split: per_entry`, `reply_be_lock_pips: 1`

### Files Modified
- `core/pipeline.py` (G1, G2, G7, G8)
- `core/reply_action_parser.py` (G3)
- `core/position_manager.py` (G4)
- `core/range_monitor.py` (G5, G11)
- `core/signal_state_manager.py` (G6)
- `core/entry_strategy.py` (G9, G12a)
- `core/reply_command_executor.py` (G12b)
- `main.py` (G4, G5, G6, G12b)
- `config/channels.json`

## 0.17.0 - 2026-03-22

### Added
- **P1: "Now" keyword → force MARKET** — when signal contains "Now" keyword and current price is within entry zone, places MARKET order immediately instead of LIMIT/STOP. New `is_now` field on `ParsedSignal` model. (`entry_detector.py`, `order_builder.py`, `models.py`)
- **P2: `execute_all_immediately`** — new strategy config option. When `true`, all entry plans in range mode are placed as orders immediately (LIMIT/STOP) instead of deferring to RangeMonitor. Default: `false`. (`pipeline.py`, `channels.json`)

### Changed
- **P0: Fingerprint includes `source_message_id`** — identical signals from different Telegram messages now generate different fingerprints, preventing false duplicate rejection. **Breaking change**: fingerprints from v0.16.x are not compatible. (`parser.py`)
- `entry_detector.detect()` now returns 4-tuple `(entry, entry_range, is_market, is_now)` — callers must update accordingly
- Noval channel config example updated with `strategy` section showing range mode + `execute_all_immediately`

### Files Modified
- `core/signal_parser/parser.py`
- `core/signal_parser/entry_detector.py`
- `core/order_builder.py`
- `core/models.py`
- `core/pipeline.py`
- `config/channels.json`

## 0.16.7 - 2026-03-22

### Fixed
- **CRITICAL**: `MARKET_TOLERANCE_POINTS` default documented as `30.0` in 4 locations — actual code default is `5.0` (`config/settings.py`)
- Version references stuck at `v0.16.1` in `PROJECT.md`, `README.md`, `DASHBOARD_FEATURES.md`
- Version stuck at `v0.16.2` in `App.jsx` footer
- Version stuck at `v0.9.0` in `FLOW_AND_SETUP_GUIDE.md` and `LOGIC_SIGNAL_PARSER.md`
- `FLOW_AND_SETUP_GUIDE.md` stale `main.py (1401 dòng)` LOC count
- `P10_FEATURE_SPEC.md` target version `v1.0.0` → `v0.10.0` (shipped)

### Added
- `ARCHITECTURE.md`: `/api/signal-status-counts` endpoint (v0.16.2), helper extraction note, unit test note
- `PROJECT.md`: `tests/` and `run.py` in repository structure
- `PLAN.md`: v0.16.2–v0.16.6 Done entries
- `DASHBOARD_FEATURES.md`: `/api/signal-status-counts` endpoint
- `OBSERVABILITY.md`: 10 P10 group management events
- `DEPLOY.md`: `run.py` unified launcher mention
- `ROADMAP.md`: R9 (Analytics Dashboard & Health Check) and R10 (Test Infrastructure) milestones

### Changed
- 14 files updated, 21 issues resolved (1 critical, 15 major, 5 minor)

## 0.16.6 - 2026-03-22

### Fixed
- **P1** `signalStatusCounts` method added to `dashboard-v2/src/api/client.js` — previously missing, causing runtime undefined error
- **P2** Extracted inline transforms from `Overview.jsx` → `Overview.helpers.js` and `Analytics.jsx` → `Analytics.helpers.js` — tests now import production code (single source of truth)
- Removed unused `ValidationResult` import in `test_signal_validator.py`
- Fixed permissive TP assertion in `test_tp_detector.py` (now exact value)
- Added word boundary test for `detect("BUYING GOLD")` in `test_side_detector.py`
- Simplified `client.test.js` to static import (removed unnecessary dynamic import)
- Fixed misleading test title in `format.test.js` for `resolveChannelName`

### Added
- `dashboard-v2/src/pages/Overview.helpers.js` — extracted page transforms
- `dashboard-v2/src/pages/Analytics.helpers.js` — extracted page transforms

## 0.16.5 - 2026-03-22

### Added
- **Bot system unit tests** — 249 pytest tests across 17 files
  - `tests/signal_parser/` — 7 files (97 tests): cleaner, side_detector, symbol_detector, entry_detector, sl_detector, tp_detector, parser orchestration
  - `tests/test_signal_validator.py` — 24 tests (all 8 validation rules)
  - `tests/test_risk_manager.py` — 12 tests (fixed lot, risk-percent, clamping)
  - `tests/test_circuit_breaker.py` — 11 tests (state machine, cooldown, callbacks)
  - `tests/test_command_parser.py` — 17 tests (all 5 command types)
  - `tests/test_reply_action_parser.py` — 25 tests (all 5 action types)
  - `tests/test_models.py` — 17 tests (enums, dataclasses, fingerprint)
  - `tests/test_entry_strategy.py` — 24 tests (single/range/scale_in, volume splits)
  - `tests/test_channel_manager.py` — 11 tests (load, rules, strategy, reload)
  - `tests/test_exposure_guard.py` — 8 tests (same-symbol, correlated limits)
- `pytest.ini` — test runner configuration
- `tests/conftest.py` — shared test fixtures

## 0.16.4 - 2026-03-22

### Added
- **Bot system test case documentation** — `tests/TEST_CASES.md`
  - 254 test cases across 25 module sections
  - Full coverage of: signal_parser (66), signal_validator (19), risk_manager + order_builder (29), entry_strategy (17), safety guards (22), command/reply parsers (26), config/models (20), storage (13), execution (10), background tasks (20), infrastructure (12)
  - Each test case includes: input, expected output, and purpose

## 0.16.3 - 2026-03-22

### Added
- **Dashboard V2 unit test suite** — 130 tests across 11 test files
  - Test framework: Vitest + React Testing Library + jsdom
  - `test/utils/format.test.js` — all 5 format utilities (29 cases)
  - `test/api/client.test.js` — fetchApi, URL construction, API key, DELETE methods (12 cases)
  - `test/hooks/useApi.test.jsx` — all 17 React Query hooks (20 cases)
  - `test/charts/ChartPrimitives.test.jsx` — PremiumTooltip, BarLabel, PieLabel (17 cases)
  - `test/components/*.test.jsx` — ChartCard, ConfirmModal, Navbar, SparkCard, StatCard (30 cases)
  - `test/pages/*.test.js` — Overview + Analytics data transforms (22 cases)
- `vitest.config.js` — Vitest configuration with jsdom environment
- `test/setup.js` — global test setup (jest-dom matchers, localStorage mock)
- `npm test` and `npm run test:watch` scripts

### Changed
- `docs/RULES.md` — added §12 Frontend Unit Test Guidelines
- `dashboard-v2/package.json` — added vitest, @testing-library/react, @testing-library/jest-dom, jsdom devDependencies

## 0.16.2 - 2026-03-22

### Fixed
- **API routes**: Return proper HTTP 404/400 status codes instead of 200 with error body (`routes.py`)
- **Sub-fingerprint SQL**: Paginated signals query now aggregates by base fingerprint (strips `:L0`, `:L1` suffixes) — multi-order signals no longer undercount orders/trades/PnL
- **CSS `composes: card`**: Replaced invalid CSS Modules syntax with duplicated base styles in plain CSS (`components.css`)
- **Missing `--bg-card` CSS var**: Added to design system — `SparkCard` no longer renders transparent background
- **Unused imports**: Removed `PieChart`/`Pie` from `Overview.jsx`, `ChartCard` from `Trades.jsx`
- **DELETE no-op returns 200**: Signal/order/trade delete now returns 404 when target not found
- **Settings fake "Connected"**: Connection panel now pings `/api/overview` to check real API reachability (online/offline + auto-refresh 30s)
- **Signal Breakdown incomplete counts**: Replaced client-side counting (max 100) with dedicated `/api/signal-status-counts` backend endpoint
- **Analytics timezone parsing**: Weekly aggregation uses UTC date parsing to avoid timezone-related day/week shifts
- **VITE_API_URL docs misleading**: Corrected default from `/api` to `http://localhost:8000` with note about double `/api/api/` trap

### Changed
- **Version consistency**: Synchronized version to `v0.16.1` across all locations:
  - `App.jsx` footer, `Settings.jsx` About panel, `README.md` (root), `dashboard-v2/README.md`
- **Dependency table**: Corrected `recharts` 2.x → 3.x, `@nivo/core` 0.88.x → 0.99.x, `lucide-react` 0.47x → 0.577+ in `dashboard-v2/README.md`
- **Root README.md**: Corrected "read-only" claim — V2 supports DELETE operations for test data cleanup; pages 6 → 7

### Added
- **`/api/signal-status-counts`** backend endpoint + `useSignalStatusCounts` hook for accurate signal breakdown
- **`.spin` CSS utility** — keyframe animation for Settings refresh button

### Removed
- **Dead template files**: Deleted `src/App.css` and `src/index.css` (leftover Vite scaffolding, not imported)
- **Unused `signal` import** in `run.py`
- **`useSignals({ per_page: 100 })` in Overview** — replaced by backend-counted signal status endpoint

## 0.16.1 - 2026-03-22

### Added
- **Overview page enhancements** — 3 new PLECTO-inspired chart cards:
  - **Win Rate Gauge** — radial bar chart with center percentage + W/L counts
  - **Signal Breakdown** — table card showing executed/rejected/failed/received counts (like PLECTO MRR Breakdown)
  - **PnL by Weekday** — bar chart showing cumulative PnL per trading day (Mon–Fri)
- **Chart toggle** — "Customize" dropdown to show/hide any chart card, persisted to `localStorage`

### Changed
- `dashboard-v2/src/pages/Overview.jsx` — rebuilt with chart visibility system + 3 new charts
- `dashboard-v2/src/components/Navbar.jsx` — changed Signals icon from `Workflow` to `GitBranch`


## 0.16.0 - 2026-03-22

### Added
- **Signal Lifecycle page** — new "Signals" tab in Dashboard V2
  - Expandable table grouping orders under their parent signal (fingerprint)
  - Filters: channel, symbol, status, date range + pagination
  - **SignalDetailModal** — full lifecycle popup showing:
    - Raw signal text from Telegram
    - Parsed result (symbol, side, entry, SL, TP)
    - Timeline of all events (received → parsed → executed/rejected → reply → close)
    - Orders table with status + delete per order
    - Trade outcomes with PnL
    - Signal group info
  - **Cascade delete** — delete signal removes all related orders, trades, events, groups
  - **Individual order delete** — remove single orders to clean test data
  - **ConfirmModal** — shared popup component (glassmorphism, type-to-confirm for destructive ops)
- **Backend API** — 8 new endpoints:
  - `GET /api/signals` — paginated signal list with aggregated stats
  - `GET /api/signals/{fp}` — full lifecycle detail
  - `DELETE /api/signals/{fp}` — cascade delete
  - `DELETE /api/orders/{id}` — single order delete
  - `DELETE /api/trades/{id}` — single trade delete
  - `GET /api/data/counts` — table row counts
  - `DELETE /api/data/all` — clear all tables
  - `DELETE /api/data/{table}` — clear specific table
- **DashboardDB write ops** — added `_connect_rw()` for write operations on read-only DB class

### Changed
- `dashboard/db/queries.py` — added signal lifecycle queries + delete methods
- `core/storage.py` — added lifecycle queries + cascade/granular delete methods
- `dashboard/api/routes.py` — 8 new endpoints
- `dashboard-v2/src/api/client.js` — added `method` support for DELETE + new API methods
- `dashboard-v2/src/hooks/useApi.js` — `useSignals`, `useSignalDetail`, `useTableCounts`
- `dashboard-v2/src/components/Navbar.jsx` — added Signals nav link
- `dashboard-v2/src/App.jsx` — added `/signals` route


## 0.15.0 - 2026-03-22

### Added
- **Dashboard V2** — React SPA with advanced analytics (`dashboard-v2/`)
  - 6 pages: Overview, Analytics, Channels, Symbols, Trades, Settings
  - Tech: React 19 + Vite 6 + Recharts + TanStack Query + Framer Motion
  - Premium dark mode with glassmorphism, gradient accents, micro-animations
  - Charts: equity curve, daily PnL bars, win/loss donut, PnL distribution histogram, drawdown, symbol radar, trading activity area, channel comparison
  - Interactive channel cards with per-channel daily PnL drill-down
  - Symbol performance table with inline win-rate progress bars
  - Trade journal with multi-filter (channel, symbol, date, outcome) + pagination + CSV export
  - Settings page with API key management and connection status
  - Shares same FastAPI API backend as V1, no duplication
  - Users choose which dashboard to run (V1 port 8000, V2 port 5173)

## 0.14.1 - 2026-03-22

### Fixed
- **R3**: `self.position_manager` → `self.position_mgr` — 13 references in main.py caused AttributeError (edit/delete/reply all broken)
- **R2**: orders table missing `symbol` column — added V5 migration, fixed reply-command query crash
- **R1**: single-mode execution now persists to orders table — fixes TradeTracker matching and PnL replies
- **R4**: `_restore_groups_from_db()` deferred to after `init_mt5()` — prevents stale group cleanup on restart
- **R5**: TradeTracker strips sub-fingerprint (`:L0`) before signal lookup — fixes PnL replies for multi-order trades
- **R9**: TradeTracker polls immediately on startup instead of waiting `poll_seconds`
- **R7**: Dashboard `_query()` only suppresses "no such table" errors (was swallowing all OperationalError)
- **R6**: Dashboard footer version updated to v0.14.0 (was hardcoded v0.12.0)
- **R10**: DASHBOARD.md API reference corrected for `/api/channel-list` response format
- **R8**: Added `config/channels.json` to `.gitignore`

## 0.14.0 - 2026-03-22

### Added
- **P13: Bot Hardening & Reliability**
  - Health check HTTP endpoint (`/health` on port 8080) — uptime, MT5 status, signal/order/error counters, circuit breaker state
  - Runtime health stats tracker (`HealthStats`) — daily auto-reset counters, status computation (healthy/degraded/unhealthy)
  - Watchdog → health stats bridge — MT5 connection status feeds into health endpoint in real-time
  - Circuit breaker → health stats bridge — CB state changes reflected in `/health` response
  - Signal/order/error tracking wired throughout the pipeline

### Changed
- `MT5Watchdog` now accepts `on_health_update` callback (non-breaking, optional param)
- Environment variable `HEALTH_CHECK_PORT` configures health server port (default 8080)

## 0.13.0 - 2026-03-22

### Added
- **P12: Dashboard Enhancement**
  - Channel name mapping — channel IDs now show human-readable names from `channels.json`
  - Equity curve chart — cumulative PnL over time (line chart with gradient fill)
  - Win rate by symbol chart — horizontal bar with color coding (green ≥60%, orange ≥45%, red <45%)
  - CSV export — download all trades as CSV with channel names, filterable by date/channel
  - Basic HTTP auth — `DASHBOARD_PASSWORD` env var protects page access
  - 3 new API endpoints: `/api/equity-curve`, `/api/symbol-stats`, `/api/export/csv`
  - `/api/channel-list` now returns `{id, name}` objects

### Changed
- All API responses now include `channel_name` field alongside `channel_id`
- Dashboard version bumped to 0.13.0

## 0.12.0 - 2026-03-21

### Added
- **P11: Web Analytics Dashboard** — separate FastAPI process for trade analytics
  - `dashboard/db/queries.py`: Read-only SQL aggregation (overview, daily PnL, channel stats, paginated trades, active groups)
  - `dashboard/api/routes.py`: 7 REST API endpoints with FastAPI dependency injection
  - `dashboard/dashboard.py`: FastAPI app with CORS, API key middleware, Jinja2 templates
  - `dashboard/templates/`: 3 pages — Overview (stat cards, charts), Channels (cards, comparison), Trades (filters, pagination)
  - `dashboard/static/`: Dark theme CSS (glassmorphism, responsive), Chart.js utilities, auto-refresh 30s
- New dependencies: `fastapi`, `uvicorn`, `jinja2`

## 0.11.0 - 2026-03-21

### Added
- **P10.1: MessageDeleted listener** — `telegram_listener.py` now listens for `events.MessageDeleted`, forwarding to `_process_delete()` which cancels pending orders from deleted signals
- **P10.1: `cancel_group_pending_orders()`** — new PositionManager method to cancel all unfilled pending orders in a group while keeping filled positions running
- **P10.1: `CANCEL_GROUP_PENDING` action** — new UpdateAction in `MessageUpdateHandler` for signals with mixed state (some filled, some pending)

### Changed
- **`message_update_handler.py`** — `handle_edit()` now accepts `has_filled_orders` param; uses MT5 position check instead of blind CANCEL_ORDER; removed stale TODO
- **`main.py`** `_process_edit()` — group-aware: checks PositionManager for filled orders before deciding action; routes to `cancel_group_pending_orders()` for groups
- **`telegram_listener.py`** — added `DeleteCallback` type, `set_delete_callback()`, and `events.MessageDeleted` handler registration

## 0.10.1 - 2026-03-21

### Fixed
- **Swallowed exception** in `main.py:691` — pip_size calculation now logs warning + uses fallback instead of `except: pass`
- **Swallowed exception** in `circuit_breaker.py:111` — state change callback errors now logged instead of silently ignored

### Removed
- 6 unused imports: `field` (settings.py), `Settings` TYPE_CHECKING (command_executor.py), `timezone` (message_update_handler.py, storage.py), `json`/`Side`/`SignalLifecycle`/`SignalStatus` (pipeline.py)
- 5 dead functions (grep-verified 0 callers): `check_symbol()` (trade_executor.py), `cleanup_debounce()` (range_monitor.py), `expire_active_signals()` (storage.py), `is_known_channel()` + `get_all_channel_ids()` (channel_manager.py)

### Changed
- **README.md**: Updated to v0.10.0, added P9/P10 modules to project structure, updated pipeline flow, reply docs, customization guide
- **PROJECT.md**: Updated to v0.10.0, added P10 group management features
- **ROADMAP.md**: Added R8 milestone (Smart Signal Group Management)

## 0.10.0 - 2026-03-21

### Added
- **P10: Smart Signal Group Management** — every signal creates a managed order group
- `core/models.py` — `OrderGroup` dataclass and `GroupStatus` enum for group lifecycle
- `core/position_manager.py` — Group-aware position management:
  - `_check_positions()` routes to group vs individual management
  - `register_group()` creates groups from pipeline results
  - `add_order_to_group()` for re-entry orders from RangeMonitor
  - `_manage_group()` with group trailing SL, zone SL, and auto-BE
  - `_calculate_group_sl()` — multi-source SL calculation (zone, signal, fixed, trail)
  - `_modify_group_sl()` — applies SL to ALL tickets atomically
  - `close_selective_entry()` — strategy-based single order close from reply
  - `apply_group_be()` — auto-breakeven after partial group close
  - `get_group()`, `get_group_by_ticket()`, `get_group_status()` — query methods
- `core/pipeline.py` — `_register_group_from_results()` called after every execution
- `core/order_builder.py` — `order_types_allowed` filter (P10d):
  - STOP not allowed → MARKET (if price in zone) or LIMIT at zone midpoint
- `core/storage.py` — Migration V4: `signal_groups` table for restart recovery
  - `store_group()`, `get_active_groups()`, `update_group_sl()`, `update_group_tickets()`, `complete_group_db()`
- `config/channels.example.json` — 6 new config fields:
  - `group_trailing_pips`, `group_be_on_partial_close`, `reply_close_strategy`
  - `sl_mode` (`signal`/`zone`/`fixed`), `sl_max_pips_from_zone`, `order_types_allowed`

### Changed
- `main.py` — Reply handler intercepts CLOSE for groups with selective strategy
- `core/position_manager.py` — Per-position logic extracted to `_manage_individual()`
- Cleanup task now includes `signal_groups` table

## 0.9.0 - 2026-03-21

### Added
- **Channel-driven strategy architecture** (P9) — multi-order per signal with per-channel strategy config
- `core/entry_strategy.py` — generate multi-entry plans from signal + strategy config
  - Strategy modes: `single` (backward-compat), `range` (N orders across entry zone), `scale_in` (stepped re-entries)
  - Volume split: `equal`, `pyramid`, `risk_based` (weighted by SL distance per entry)
- `core/signal_state_manager.py` — active signal lifecycle tracking
  - State machine: PENDING → PARTIAL → COMPLETED → EXPIRED
  - DB-backed persistence for restart recovery
- `core/pipeline.py` — sole orchestrator for multi-order execution
  - `execute_signal_plans()` replaces single-order execute path
  - `handle_reentry()` with full risk guard gauntlet (circuit breaker, daily guard, exposure guard)
- `core/range_monitor.py` — background price-cross re-entry trigger
  - Price-cross detection (not proximity — only triggers on actual crossing)
  - 30-second debounce per level to prevent order spam
- **Order fingerprint v2**: `base_fp:L{N}` — unique per order, debuggable, linkable via base_fp
- `core/models.py` — `EntryPlan`, `SignalState`, `SignalLifecycle` enum, `order_fingerprint()`
- Storage migration V3: `active_signals` table with status/plans/expiry tracking
- `channels.json` schema expanded: `strategy`, `risk`, `validation` sections per channel
- Index `idx_orders_source_msg` on `(source_chat_id, source_message_id)` for P9 reply handler

### Changed
- `core/channel_manager.py` — `get_strategy()`, `get_risk_config()`, `get_validation_config()` with `_get_section()` DRY pattern
- `core/storage.py` — `get_orders_by_message()` now uses direct source_message_id join (supports sub-fingerprints), with fallback to old fingerprint JOIN for pre-P9 orders
- `config/channels.example.json` — updated with full strategy/risk/validation example

## 0.8.1 - 2026-03-18

### Fixed
- **CRITICAL**: Reply management completely broken — `orders.fingerprint` stored as truncated 12-char string while `signals.fingerprint` stored as full 16-char string, causing JOIN in `get_orders_by_message()` to never match. All reply actions (close, SL, TP, BE) were non-functional since v0.6.0. Fix: `fp` now uses full fingerprint for all DB operations, `fp_short` for console display only.
- Signal debug messages now sent on **parse failures** — previously only triggered after successful parse
- Market data section skipped in debug message when no market data available (parse fail stage)

## 0.8.0 - 2026-03-18

### Added
- Reply-based signal management: channel admin replies to signal → bot acts on specific trade(s)
- `reply_action_parser.py` — parse reply text (close/exit/đóng, SL/TP {price}, BE, close N%)
- `reply_command_executor.py` — per-ticket MT5 operations with position existence check
- Multi-order support: all orders from a signal are actioned, results grouped
- Channel guard: cross-channel reply prevention
- Symbol consistency check before execution
- TradeTracker PnL reply suppression for reply-closed tickets (5 min TTL)
- "No active trade found" UX feedback for replies to non-signal messages
- Percent range validation (1-100) for partial close

### Changed
- `telegram_listener.py` — new `ReplyCallback`, detects `reply_to_msg_id`, early return (no signal parser fallthrough)
- `storage.py` — `get_orders_by_message()` returns list of all orders for a signal
- `trade_tracker.py` — `_reply_closed` dict with TTL, `mark_reply_closed()`, `_is_reply_closed()` with auto-cleanup

## 0.7.1 - 2026-03-17

### Added
- Command response via Telegram: reply to source chat + admin log
- Position manager Telegram alerts: breakeven, trailing stop, partial close with channel context
- Per-ticket alert throttle (60s cooldown per event_type)
- Trailing stop delta threshold: only alert if SL moved ≥ 5 pips

### Changed
- `telegram_alerter.py` — `parse_mode="md"` on all `send_message` calls for proper markdown rendering

## 0.7.0 - 2026-03-17

### Added
- `store_event()` calls in pipeline now include `channel_id` — all 11 call sites wired (2 parse-fail, 9 post-parse)
- `Storage.get_fingerprint_by_message()` — lookup fingerprint by `(source_chat_id, source_message_id)`
- `OrderLifecycleManager.cancel_by_fingerprint()` — cancel pending order by matching fingerprint in comment field
- Per-channel session metrics: `_channel_metrics` dict with lazy-init per-channel `_SessionMetrics`, heartbeat breakdown for multi-channel
- `_SessionMetrics.as_summary()` — one-line per-channel heartbeat output
- `_process_edit()` fully wired: fingerprint lookup → `MessageUpdateHandler.handle_edit()` → cancel/reprocess decision
- TradeTracker partial close reply throttle: 60s cooldown per `position_id` prevents Telegram spam

### Changed
- `main.py` — `_process_edit()` from stub to full implementation with cancel+reprocess flow
- Heartbeat log includes per-channel breakdown when `len(_channel_metrics) > 1`

## 0.6.0 - 2026-03-17

### ⚠️ Breaking Change
- **Fingerprint format changed**: `generate_fingerprint()` now includes `source_chat_id` as first element. Dedup is no longer backward compatible with v0.5.x data. **Backup DB before upgrading.**

### Added
- **Versioned schema migration system** in `core/storage.py` — `schema_versions` table, idempotent migrations safe for repeated restarts
- **`core/channel_manager.py`** — per-channel configuration via `config/channels.json`, rule merging with default fallback
- **`core/trade_tracker.py`** — background deal polling, PnL persistence, Telegram reply under original signal
  - 2-step ticket→position resolution (MARKET + pending order support)
  - Pending fill detection: `DEAL_ENTRY_IN` → `update_position_ticket()`
  - `tracker_state` table for restart recovery (`last_deal_poll_time`)
- **`core/telegram_alerter.py`** — `reply_to_message()` + `reply_to_message_sync()` for trade outcome threading
- DB tables: `trades` (deal_ticket UNIQUE), `tracker_state` (key-value), `schema_versions` (version tracking)
- DB columns: `orders.channel_id`, `orders.source_chat_id`, `orders.source_message_id`, `orders.position_ticket`, `events.channel_id`
- 8 new `Storage` methods: `store_trade()`, `get_open_tickets()`, `get_signal_reply_info()`, `update_position_ticket()`, `get/set_tracker_state()`, `get_order_by_ticket/position_ticket()`
- `ParsedSignal.parse_confidence` + `ParsedSignal.parse_source` fields
- `TRADE_TRACKER_POLL_SECONDS` env key (default 30, 0 = disabled)
- `config/channels.example.json` — per-channel rule template

### Changed
- `core/position_manager.py` — accepts `ChannelManager` + `Storage`, per-channel breakeven/trailing/partial rules, ticket→channel cache with startup rebuild
- `core/storage.py` — `store_order()` and `store_event()` accept channel context params
- `main.py` — wires `ChannelManager`, `TradeTracker`, passes channel context through pipeline, `register_ticket()` on execution
- `config/settings.py` — `trade_tracker_poll_seconds` in `ExecutionConfig`

## 0.5.5 - 2026-03-18

### Added
- **Entry Range Parsing**: `SignalParser` now accurately parses signal ranges (e.g., `Buy Gold 5162 - 5170` or `BUY GOLD zone 4963 - 4961 now`).
  - Supports multiple optional words between side keyword and price (e.g., `GOLD ZONE`).
  - Supports `-`, `/`, `–` (em-dash), and `TO` as range separators.
  - Automatically identifies extreme bounds `[low, high]`.
  - Determines final execution `entry` strictly by `Side` (uses lowest for `BUY` and highest for `SELL`).

### Changed
- **Strict Entry Enforcement**: If the parser cannot identify a single entry price and no explicit `MARKET` intent (like `NOW` or `CMP`) is passed, the signal is now explicitly REJECTED as a `ParseFailure` instead of wrongly defaulting to a market execution.
- **Relative TP Filtering**: `tp_detector` now skips TP values followed by `PIPS`/`POINTS`/`PTS` — these are relative offsets from entry, not absolute price levels. Signals like `TP: 30 pips – 50 pips` correctly return `tp=[]`.
- **Market Keyword Priority**: Market keywords (`NOW`, `CMP`, etc.) are now checked **last** in the entry detection chain, ensuring numeric entry/range detection always takes priority.

## 0.5.4 - 2026-03-15

### Fixed
- **CRITICAL**: Fixed Telethon `get_entity` failures by resolving `TELEGRAM_ADMIN_CHAT` and `TELEGRAM_SOURCE_CHATS` string IDs to integers. Previously, integer IDs like `"6638536622   #@ShuMaou"` passed from `.env` caused Telethon to attempt (and fail) to resolve them as usernames because `python-dotenv` string typing retained inline comments. These are now stripped and purely numerical sequences are properly coerced into correct Python `int` objects.

## 0.5.2 - 2026-03-15

### Added
- Signal debug messages: stream detailed decision logs directly to admin Telegram chat
- Configurable via `DEBUG_SIGNAL_DECISION` flag in `.env`
- Added `send_debug_sync` and `send_debug` to `TelegramAlerter` — deliberately bypasses standard alert cooldowns to ensure every signal gets logged
- Triggers at 3 key pipeline points in `main.py`:
  - `Validation FAIL`: logs raw, parsed text, market prices, and specific rule failure reason
  - `Entry drift FAIL`: logs rejection for market order drift
  - `Order decision SUCCESS`: logs exact volume, order type (MARKET/LIMIT/STOP), and deviation used
- Documentation: `docs/DEBUG_SIGNAL.md`

## 0.5.1 - 2026-03-15

### Fixed
- **CRITICAL**: `core/exposure_guard.py` — `_get_open_positions()` was directly importing `MetaTrader5` and calling `mt5.positions_get()`, bypassing the injected `TradeExecutor`. Now delegates to `TradeExecutor.get_position_symbols()`.
- **CRITICAL**: `core/order_builder.py` — `build_request()` used `self._base_deviation` (hardcoded base), making `compute_deviation()` and `DYNAMIC_DEVIATION_MULTIPLIER` dead code. Now calls `compute_deviation(spread_points)` for effective dynamic deviation.

### Changed
- `core/trade_executor.py` — added `get_position_symbols()` method for `ExposureGuard` to query positions through the executor abstraction
- `core/order_builder.py` — `build_request()` accepts `spread_points` parameter
- `main.py` — passes `spread_points` to `order_builder.build_request()`
- `docs/logic/LOGIC_PIPELINE_DEEP_DIVE.md` — synced with v0.5.1 pipeline: added Step 0 (command intercept), Step 2b (daily risk guard), Step 2c (exposure guard), Step 8b (entry drift guard), dynamic deviation in Step 8, updated ENV table (22 vars), added 11-layer safety note

## 0.5.0 - 2026-03-15

### Added
- `core/exposure_guard.py` — per-symbol and per-correlation-group position limits
  - `MAX_SAME_SYMBOL_TRADES`: max open positions on same symbol (default 0 = disabled)
  - `MAX_CORRELATED_TRADES`: max open across correlation group (default 0 = disabled)
  - `CORRELATION_GROUPS`: configurable groups (e.g., `XAUUSD:XAGUSD,EURUSD:GBPUSD`)
- `core/position_manager.py` — background position management (all disabled by default)
  - Breakeven: move SL to entry + lock pips when profit reaches trigger
  - Trailing stop: trail SL at fixed pip distance
  - Partial close: close percentage of volume at TP1
- `core/command_parser.py` — parse Telegram management commands
  - Supports: `CLOSE ALL`, `CLOSE <SYMBOL>`, `CLOSE HALF`, `MOVE SL <PRICE>`, `BREAKEVEN`
- `core/command_executor.py` — execute management commands against MT5
- Dynamic deviation in `core/order_builder.py`: `DYNAMIC_DEVIATION_MULTIPLIER` (default 0 = use fixed)
- 10 new env keys in `.env.example` for exposure guard, position manager, dynamic deviation

### Changed
- `main.py` — v0.5.0 banner, Step 0 command intercept, Step 2c exposure guard, position manager lifecycle
- `config/settings.py` — `SafetyConfig` and `ExecutionConfig` extended with P5 fields
- `docs/ARCHITECTURE.md` — added P5 module entries
- `docs/MONITORING.md` — added log rotation validation section
- `docs/DEPLOY.md` — enhanced update procedure with state preservation + rollback
- `docs/PLAN.md` — P4 complete, P5 in progress


### Added
- `core/daily_risk_guard.py` — poll-based daily risk limits using MT5 `history_deals_get()`
  - `MAX_DAILY_TRADES`: max closed deals per UTC day (default 0 = disabled)
  - `MAX_DAILY_LOSS`: max realized loss USD per UTC day (default 0.0 = disabled)
  - `MAX_CONSECUTIVE_LOSSES`: pause after N consecutive losing deals (default 0 = disabled)
  - Background poll every `DAILY_RISK_POLL_MINUTES` (default 5)
  - Telegram alert on first breach per day
- Startup position sync: `_sync_positions_on_startup()` logs audit of pre-existing MT5 state
  - Warns if open positions >= `MAX_OPEN_TRADES`
  - Sends Telegram alert if at capacity
- Daily guard stats in heartbeat: `daily_trades`, `daily_loss`, `consec_losses`
- `docs/DEPLOY.md` — Ubuntu VPS deployment runbook (Wine + MT5, systemd, first-run auth, maintenance)
- `deploy/telegram-mt5-bot.service` — systemd unit with `Restart=always`, security hardening
- `docs/MONITORING.md` — alert catalog (10 types), heartbeat interpretation, debug workflow, escalation playbook
- 4 new env keys in `.env.example`: `MAX_DAILY_TRADES`, `MAX_DAILY_LOSS`, `MAX_CONSECUTIVE_LOSSES`, `DAILY_RISK_POLL_MINUTES`

### Changed
- `main.py` — v0.4.0 banner, DailyRiskGuard integration (Step 2b), startup position sync, heartbeat daily stats
- `config/settings.py` — `SafetyConfig` extended with daily risk fields (added in prior planning session)
- `docs/ARCHITECTURE.md` — added `core/daily_risk_guard.py` module entry
- `README.md` — bumped to v0.4.0, added Daily Risk Guard + Production Deployment sections, fixed Safety Gates table
- P4 tasks marked complete in `docs/TASKS.md`

## 0.3.4 - 2026-03-15

### Added
- `_SessionMetrics` dataclass in `main.py` — in-memory counters per session: `parsed`, `rejected`, `executed`, `failed`
- Execution latency tracking: `avg_execution_latency_ms` and `max_execution_latency_ms` (recorded only on successfully executed signals)
- `_heartbeat_loop()` background task — fires every `HEARTBEAT_INTERVAL_MINUTES` (default 30, set 0 to disable)
- `_emit_heartbeat()` — rich status line: uptime, session counters, avg/max latency, `open_positions`, `pending_orders`, `mt5=OK/FAIL`, `telegram=OK/FAIL`
- Session summary on graceful shutdown — `[SESSION]` line with full metrics
- `HEARTBEAT_INTERVAL_MINUTES` to `RuntimeConfig` and `.env.example`
- `TradeExecutor.is_connected` property — lightweight MT5 health check via `account_info()`
- `TradeExecutor.orders_total()` — returns count of active pending orders from MT5
- `TelegramListener.is_connected` property — checks `client.is_connected()`

### Changed
- P3 → `complete`, P4 → `in progress` in `docs/PLAN.md`
- `docs/TASKS.md` regenerated for P4 with full task list (VPS runbook, daily risk guard with `MAX_CONSECUTIVE_LOSSES`, startup position sync, monitoring doc)
- Version banner bumped to `v0.3.4`


## 0.3.3 - 2026-03-15

### Added
- Entry drift guard: `MAX_ENTRY_DRIFT_PIPS=10.0` — tight safety gate for MARKET orders, rejects when entry price has drifted too far from signal intent
- `signal_validator.py` — new public `validate_entry_drift()` method
- `main.py` — Step 8b: drift check after order type decision, before execution
- Execution timing: `latency_ms` in all pipeline summary outputs
- `TASKS.md` — P4/P5 backlog items (daily risk guard, position manager, management commands, etc.)

### Changed
- Re-enabled Rule 5 (entry distance check) — was commented out
- `config/settings.py` — added `max_entry_drift_pips` to SafetyConfig
- `.env.example` — added `MAX_ENTRY_DRIFT_PIPS`
- `ARCHITECTURE.md` — documented two-tier distance protection

### Fixed
- `.env` — fixed stale naming (`MAX_SPREAD_POINTS`→`MAX_SPREAD_PIPS`, `MAX_ENTRY_DISTANCE_POINTS`→`MAX_ENTRY_DISTANCE_PIPS`)
- `.env` — added missing Trade Execution + Runtime sections (was incomplete vs `.env.example`)

## 0.3.2 - 2026-03-14

### Fixed
- **CRITICAL**: `_validate_entry_distance` was comparing raw price difference against pip-based config — gate was effectively useless for XAUUSD (500 meant $500 instead of 50 pips = $5)

### Changed
- All distance/spread units standardized to **PIPS** (not points)
- `signal_validator.py` — rewritten with `pip_size` param, all thresholds in pips
- `config/settings.py` — `SafetyConfig`: renamed `max_spread_points`→`max_spread_pips` (default 5.0), `max_entry_distance_points`→`max_entry_distance_pips` (default 50.0)
- `.env.example` — renamed `MAX_SPREAD_POINTS`→`MAX_SPREAD_PIPS`, `MAX_ENTRY_DISTANCE_POINTS`→`MAX_ENTRY_DISTANCE_PIPS`, with XAUUSD pip explanations
- `main.py` — resolve `point`/`pip_size` BEFORE validation (was incorrectly after), pass `pip_size` to validator, convert spread points→pips
- `docs/RULES.md` — added §5a "Unit Consistency — Pips vs Points" rule

### ⚠️ Breaking: .env rename required
- `MAX_SPREAD_POINTS=50` → `MAX_SPREAD_PIPS=5.0`
- `MAX_ENTRY_DISTANCE_POINTS=500` → `MAX_ENTRY_DISTANCE_PIPS=50.0`

## 0.3.1 - 2026-03-14

### Changed
- Moved 8 hardcoded trade execution values to `.env`: `BOT_MAGIC_NUMBER`, `DEVIATION_POINTS`, `MARKET_TOLERANCE_POINTS`, `ORDER_MAX_RETRIES`, `ORDER_RETRY_DELAY_SECONDS`, `WATCHDOG_INTERVAL_SECONDS`, `WATCHDOG_MAX_REINIT`, `LIFECYCLE_CHECK_INTERVAL_SECONDS`
- `config/settings.py` — added `ExecutionConfig` dataclass
- `core/order_builder.py` — removed hardcoded `BOT_MAGIC_NUMBER=234000` and `DEFAULT_DEVIATION=20`, now from config
- `main.py` — wires all ExecutionConfig values into OrderBuilder, TradeExecutor, MT5Watchdog, OrderLifecycleManager
- `.env.example` — added Trade Execution section with ⚠️ CRITICAL warnings and explanations
- `README.md` — added CRITICAL warning section at top: price reference rule, market tolerance, deviation, risk sizing, all safety gates

## 0.3.0 - 2026-03-14

### Added
- Smart dry-run mode: `DRY_RUN=true` simulates execution with dynamic bid/ask derived from signal entry price
- Circuit breaker: `core/circuit_breaker.py` — CLOSED/OPEN/HALF_OPEN states, pause trading after N consecutive failures
- Telegram alerter: `core/telegram_alerter.py` — rate-limited critical alerts to admin chat
- Pipeline summary logging: one-line console output per signal with outcome
- Signal lifecycle events stored in DB: `signal_received`, `signal_parsed`, `signal_rejected`, `signal_submitted`, `signal_executed`, `signal_failed`
- Background storage cleanup: auto-delete records older than `STORAGE_RETENTION_DAYS`
- Startup self-check: MT5 account info, config summary, component status

### Changed
- `config/settings.py` — added `RuntimeConfig` (DRY_RUN, ALERT_COOLDOWN, CIRCUIT_BREAKER, STORAGE_RETENTION), `TELEGRAM_ADMIN_CHAT`, `SESSION_RESET_HOURS`
- `core/storage.py` — WAL mode, retry on OperationalError, `cleanup_old_records()` method
- `core/telegram_listener.py` — auto-reconnect with exponential backoff, proactive session reset every N hours
- `core/mt5_watchdog.py` — weekend/market-close detection, exponential backoff, alert callbacks
- `main.py` — global exception handling, circuit breaker integration, smart dry-run, pipeline summary, graceful shutdown

## 0.2.0 - 2026-03-14

### Added
- Telegram listener: `core/telegram_listener.py`
- Order builder: `core/order_builder.py` — BUY→ASK / SELL→BID price reference rule
- Trade executor: `core/trade_executor.py` — bounded retry, 35+ retcode mappings
- Order lifecycle manager: `core/order_lifecycle_manager.py`
- MT5 watchdog: `core/mt5_watchdog.py`
- Full pipeline wiring in `main.py`

### Changed
- `core/signal_validator.py` — spread gate, max trades gate, duplicate filter
- `requirements.txt` — pinned `numpy<2`

## 0.1.0 - 2026-03-14

### Added
- Project foundation and configuration
- Signal parser pipeline (7 modules)
- Signal validation, risk management, SQLite storage
- MessageEdited handler prototype, parser CLI, benchmark tool
