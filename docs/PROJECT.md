# PROJECT

## Project Overview
- Name: `telegram-mt5-bot`
- Goal: Run a low-latency Python bot that reads Telegram trading signals and executes MT5 orders safely.
- Scope: Single-process runtime, signal-to-trade automation, operational reliability.

## Goals
- Parse common Telegram signal formats with high consistency.
- Map signal intent to correct MT5 market or pending order type.
- Execute orders with SL/TP and validation gates.
- Keep runtime stable for 24/7 operation with logs and retry controls.

## Observability Goals
The bot MUST allow operators to trace every signal through the system.

Operators must be able to determine:

- which signals were received
- which signals failed parsing
- which signals were rejected by safety rules
- which signals resulted in MT5 orders
- which orders failed execution

Signal trace must be possible using a unique signal fingerprint across logs and database records.

## Non-Goals
- User management and authentication UI.
- Payment, subscription, or billing workflows.
- Copy trading platform features.
- Advanced portfolio-level risk engine (beyond simple safety gates).

## Key Features
- Telegram listener for selected groups/channels.
- Rule-based parser pipeline (clean -> detect -> normalize).
- Symbol alias mapping (example: `GOLD` -> broker symbol).
- Order decision engine:
  - `BUY/SELL` market
  - `BUY_LIMIT/SELL_LIMIT`
  - `BUY_STOP/SELL_STOP`
- Validation gates:
  - SL/TP logic checks
  - spread threshold check
  - duplicate signal filter
  - max open trades gate
- MT5 execution with retry and result logging.
- Position sizing engine:
  - fixed lot
  - risk-per-trade percentage
  Maximum signal age protection
Correct Bid/Ask price reference for order decisions.
All detectors must be exception safe


BUY orders must use ASK price as reference.
SELL orders must use BID price as reference.

This prevents incorrect order type selection and avoids
unintended immediate executions due to spread.

## Users
- Primary: Solo or small-team discretionary traders using Telegram signal channels.
- Secondary: Developer/operators maintaining bot runtime on VPS.
- TODO: Define user roles if team operations expand.

## Tech Stack
- Language: Python 3.11+ (target)
- Telegram: `telethon`
- Trading terminal bridge: `MetaTrader5` Python package
- Config: `python-dotenv`
- Logging: `loguru`
- Local persistence: SQLite (`sqlite3`)

## Repository Structure
- Current:
  - `.codex/` skill and agent workflow helpers
  - `specs/telegram-mt5-bot/` existing product spec + plan drafts
- Target runtime structure:
  - `config/`
  - `core/`
  - `utils/`
  - `data/`
  - `logs/`
  - `docs/`
  - `main.py`
  - `requirements.txt`

## Success Criteria
- Parse and execute valid signals without manual intervention.
- Reject invalid/unsafe signals with explicit reason logs.
- Operate continuously with recoverable failure handling.

## Safety Guarantees

The bot MUST enforce the following protections before any order execution:

- Maximum spread threshold check
- Duplicate signal suppression
- SL/TP logical validation
- Maximum distance between entry and current price
- Maximum open trades gate
- Pending order expiration
- Signal age validation (reject signals older than configured TTL)
- Maximum signal age protection (example: 60 seconds)
Pending order expiration protection.

Signals should not remain active indefinitely.
Pending orders must expire after a configurable TTL
to prevent execution of stale signals.
These rules ensure that stale or malformed signals do not result in unintended trades.