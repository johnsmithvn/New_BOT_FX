# PROJECT

## Project Overview
- Name: `telegram-mt5-bot`
- Version: `v0.5.1`
- Goal: Run a low-latency Python bot that reads Telegram trading signals and executes MT5 orders safely.
- Scope: Single-process runtime, signal-to-trade automation, operational reliability.

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

## Users
- Primary: Solo or small-team discretionary traders using Telegram signal channels.
- Secondary: Developer/operators maintaining bot runtime on VPS.

## Tech Stack
- Language: Python 3.11+ (target)
- Telegram: `telethon`
- Trading terminal bridge: `MetaTrader5` Python package
- Config: `python-dotenv`
- Logging: `loguru`
- Local persistence: SQLite (`sqlite3`)

## Repository Structure
- `config/` — settings loader
- `core/` — all business logic modules
- `utils/` — logger, symbol mapper
- `data/` — SQLite database (runtime)
- `logs/` — structured JSON logs (runtime)
- `docs/` — all documentation
- `deploy/` — systemd service file
- `tools/` — CLI debug utilities
- `main.py` — entry point
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