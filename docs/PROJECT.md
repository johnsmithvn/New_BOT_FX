# PROJECT

## Project Overview
- Name: `telegram-mt5-bot`
- Version: `v0.22.3`
- Goal: Run a low-latency Python bot that reads Telegram trading signals and executes MT5 orders safely.
- Scope: Single-process runtime, signal-to-trade automation, operational reliability, channel-driven multi-order strategy, web analytics dashboard.

## Goals
- Parse common Telegram signal formats with high consistency.
- Map signal intent to correct MT5 market or pending order type.
- Execute orders with SL/TP and validation gates.
- Keep runtime stable for 24/7 operation with logs and retry controls.
- Manage open positions (breakeven, trailing stop, partial close).
- Accept management commands from Telegram (CLOSE, MOVE SL, BREAKEVEN).

## Observability Goals
The bot MUST allow operators to trace every signal through the system.

Operators must be able to determine:
- which signals were received
- which signals failed parsing
- which signals were rejected by safety rules
- which signals resulted in MT5 orders
- which orders failed execution
- which management commands were executed

Signal trace must be possible using a unique signal fingerprint across logs and database records.

## Non-Goals
- User management and authentication UI.
- Payment, subscription, or billing workflows.
- Copy trading platform features.
- Advanced portfolio-level risk engine (beyond simple safety gates).

## Key Features
- Telegram listener for selected groups/channels (Telethon user session).
- Rule-based parser pipeline (clean → detect → normalize).
- Symbol alias mapping (example: `GOLD` → broker symbol).
- Management command parser (CLOSE ALL, CLOSE SYMBOL, CLOSE HALF, MOVE SL, BREAKEVEN).
- Order decision engine:
  - `BUY/SELL` market
  - `BUY_LIMIT/SELL_LIMIT`
  - `BUY_STOP/SELL_STOP`
- Dynamic deviation: auto-widen slippage with spread (`DYNAMIC_DEVIATION_MULTIPLIER`).
- Validation gates:
  - SL/TP logic checks
  - Spread threshold check
  - Duplicate signal filter
  - Max open trades gate
  - Entry distance + entry drift protection (two-tier)
  - Signal age TTL
- Exposure control:
  - Per-symbol position limit (`MAX_SAME_SYMBOL_TRADES`)
  - Correlation group limit (`MAX_CORRELATED_TRADES`)
- Daily risk guard:
  - Max daily trades / daily loss / consecutive losses
  - Poll-based from MT5 deal history
- Position manager (background):
  - Breakeven SL move
  - Trailing stop
  - Partial close at TP1
- MT5 execution with retry and result logging.
- Position sizing engine: fixed lot or risk-per-trade percentage.
- Circuit breaker: pause trading after consecutive execution failures.
- Telegram alerting: rate-limited admin notifications.
- BUY orders use ASK price as reference; SELL orders use BID price.
- Channel-driven strategy (v0.9.0):
  - Per-channel entry strategy: single, range (multi-order), scale_in
  - Volume splitting: equal, pyramid, risk_based
  - Signal state machine: PENDING → PARTIAL → COMPLETED → EXPIRED
  - Background price-cross re-entry monitor with debounce
  - Order fingerprint v2: `base_fp:L{N}` for multi-order linking
- Smart signal group management (v0.10.0):
  - Every signal = 1 managed order group
  - Group trailing SL, zone SL, multi-source SL calculation
  - Selective close via reply (highest/lowest entry, oldest)
  - Auto-breakeven after partial group close
  - DB persistence for restart recovery
- Reply actions expanded (v0.19.0):
  - SECURE_PROFIT (`+N pip`) — close worst entry + BE remaining
  - CANCEL — cancel pending orders for signal
  - CLOSE_PROFIT — close profitable entries only
- Pipeline guards (v0.19.0–v0.22.1):
  - G1: Min SL distance guard
  - G2: Default SL from zone (auto-generate)
  - G7: Max re-entry distance guard
  - G8: Force MARKET for re-entries
  - G11: SL breach cancel (cancel pending on SL hit)
  - SL buffer (nới rộng SL tránh spike)
  - Max SL distance cap
- Peak profit tracking per signal group (v0.22.0)
- Market snapshot at entry: volume, bid, ask stored per order (v0.22.1)
- `per_entry` volume split: each plan gets full lot size (v0.19.0)
- `SYMBOL_SUFFIX` for broker-specific symbol mapping (v0.21.0)
- Health check endpoint on port 8080 (`/health`) (v0.14.0)
- Dashboard V1: FastAPI + Jinja2 (3 pages, 7 API endpoints) (v0.12.0)
- Dashboard V2: React SPA (7 pages, 20 API endpoints, signal lifecycle, cascade delete) (v0.15.0–v0.16.2)
- Unified launcher `run.py` (bot/dash/v2/combo modes) (v0.14.0)

## Users
- Primary: Solo or small-team discretionary traders using Telegram signal channels.
- Secondary: Developer/operators maintaining bot runtime on VPS.

## Tech Stack
- Language: Python 3.11+ (target)
- Telegram: `telethon`
- Trading terminal bridge: `MetaTrader5` Python package
- Config: `python-dotenv`
- Logging: `loguru`
- Dashboard V1: `fastapi`, `jinja2`, `chart.js`
- Dashboard V2: `react`, `vite`, `recharts`, `tanstack-query`, `framer-motion`
- Local persistence: SQLite (`sqlite3`) — 7 schema migrations (V1–V7)

## Repository Structure
- `config/` — settings loader
- `core/` — all business logic modules
- `utils/` — logger, symbol mapper
- `data/` — SQLite database (runtime)
- `logs/` — structured JSON logs (runtime)
- `docs/` — all documentation
- `deploy/` — systemd service file
- `tools/` — CLI debug utilities
- `dashboard/` — FastAPI backend (V1 Jinja2 + V2 REST API)
- `dashboard-v2/` — React SPA (Vite + Recharts + TanStack Query)
- `tests/` — Unit tests (pytest + Vitest)
- `main.py` — entry point
- `run.py` — unified launcher (bot, dashboard, combos)
- `requirements.txt` — dependencies

## Success Criteria
- Parse and execute valid signals without manual intervention.
- Reject invalid/unsafe signals with explicit reason logs.
- Operate continuously with recoverable failure handling.

## Safety Guarantees

The bot enforces the following protections before any order execution:
- Maximum spread threshold check
- Duplicate signal suppression
- SL/TP logical validation
- Entry distance protection (max entry distance + entry drift for market orders)
- Maximum open trades gate
- Pending order expiration (configurable TTL)
- Signal age validation (reject signals older than configured TTL)
- Circuit breaker (pause after consecutive failures)
- Daily risk limits (trades, loss, consecutive losses)
- Exposure limits (per-symbol, per-correlation-group)