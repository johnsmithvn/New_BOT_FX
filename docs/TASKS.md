# TASKS

## Current Phase
- `P5 - Controlled Expansion (R6)`

## High Priority

### Exposure / Correlation Control
- [x] `core/exposure_guard.py` — MAX_SAME_SYMBOL_TRADES + MAX_CORRELATED_TRADES
- [x] Configurable correlation groups via `CORRELATION_GROUPS` env
- [x] Pipeline Step 2c: exposure guard check after daily risk guard

### Dynamic Deviation
- [x] `DYNAMIC_DEVIATION_MULTIPLIER` in OrderBuilder — auto-widen slippage during high spread
- [x] `compute_deviation()` method: `max(base, spread * multiplier)`

### Position Manager
- [x] `core/position_manager.py` — background poll loop
- [x] Breakeven: move SL to entry + lock when profit >= trigger
- [x] Trailing stop: trail SL at fixed pip distance
- [x] Partial close: close % of volume at TP1
- [x] Only manages bot's own positions (magic number filter)

### Signal Management Commands
- [x] `core/command_parser.py` — CLOSE ALL, CLOSE SYMBOL, CLOSE HALF, MOVE SL, BREAKEVEN
- [x] `core/command_executor.py` — execute commands against MT5
- [x] Pipeline Step 0: command intercept before signal parser

### Integration
- [x] `config/settings.py` — all P5 fields in SafetyConfig + ExecutionConfig
- [x] `main.py` — wire all new components, banner v0.5.0
- [x] `.env.example` — 10 new config keys

### Documentation
- [x] `ARCHITECTURE.md` — P5 module entries
- [x] `README.md` — v0.5.0, exposure control, position manager, commands sections
- [x] `CHANGELOG.md` — v0.5.0 entry
- [x] `PLAN.md` — P4 complete, P5 in progress

### P5 Bug Fixes (v0.5.1)
- [x] `core/exposure_guard.py` — use `TradeExecutor.get_position_symbols()` instead of raw `mt5.positions_get()`
- [x] `core/trade_executor.py` — add `get_position_symbols()` method
- [x] `core/order_builder.py` — `build_request()` must call `compute_deviation(spread_points)` instead of `self._base_deviation`
- [x] `main.py` — pass `spread_points` to `build_request()`
- [x] `CHANGELOG.md` — v0.5.1 entry

## Medium Priority
- [x] Signal Debug Messages — send raw, parsed, market, and decision data via Telegram
- [ ] Command response via Telegram — send command result back to admin chat
- [ ] Position manager Telegram alerts — notify on breakeven/trailing stop moves

## Completed (from previous phases)
- [x] All P0 tasks (documentation foundation)
- [x] All P1 tasks (signal parser pipeline, validation, risk manager, storage, tooling)
- [x] All P2 tasks (trade executor, order builder, Telegram listener, lifecycle manager, watchdog, pipeline wiring)
- [x] All P3 tasks (dry-run, circuit breaker, alerting, storage hardening, signal lifecycle DB, entry drift guard, execution metrics, ENV sync, session metrics, heartbeat log)
- [x] All P4 tasks (daily risk guard, startup position sync, VPS runbook, monitoring doc, log rotation validation, update procedure)
- [x] All P5 High Priority tasks (exposure guard, dynamic deviation, position manager, management commands)
- [x] All P5 Bug Fixes (exposure guard TradeExecutor delegation, dynamic deviation wiring)
