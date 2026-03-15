# TASKS

## Current Phase
- `P4 - Production Operations (R5)`

## High Priority

### VPS Deployment Runbook
- [x] Write `docs/DEPLOY.md` — Ubuntu VPS setup: Python venv, Wine + MT5, firewall, env config
- [x] Create `telegram-mt5-bot.service` systemd unit file with `Restart=always`

### Daily Risk Guard
- [x] Add `MAX_DAILY_TRADES`, `MAX_DAILY_LOSS`, `MAX_CONSECUTIVE_LOSSES` to config
- [x] Implement poll-based counter refresh using `mt5.history_deals_get()` in background task
- [x] Block new signal execution when any daily limit is hit (Step 2b in pipeline)
- [x] Send Telegram alert when limit triggered (via `on_limit_hit` callback)
- [x] Consecutive losses derived from deal history (leading loss streak, resets on winning deal)

### Startup Position Sync
- [x] On bot boot, query MT5 for existing open positions and pending orders
- [x] Log position sync summary on startup (`[STARTUP SYNC]`)
- [x] Warn if positions >= MAX_OPEN_TRADES (log + Telegram alert)

### Monitoring / Alerting Doc
- [x] Write `docs/MONITORING.md` — alert catalog (10 types), heartbeat interpretation, debug workflow, escalation playbook

### README — VPS Quick-Start
- [x] Add "Production Deployment" section to `README.md` referencing `DEPLOY.md`
- [x] Bump version to v0.4.0
- [x] Fix Safety Gates table (PIPS, not POINTS)
- [x] Add Daily Risk Guard section

## Medium Priority
- [ ] Log rotation validation — confirm loguru rotation works correctly in long-running process (≥ 7 days)
- [ ] Controlled update procedure — document graceful restart without losing state

## Backlog (P5 — Controlled Expansion)
- [ ] Position manager (breakeven, partial close, trailing stop)
- [ ] Signal management commands parser (`MOVE SL`, `CLOSE HALF`, `CLOSE NOW`)
- [ ] Exposure/correlation control (`MAX_CORRELATED_TRADES`)
- [ ] Dynamic deviation (DEVIATION = spread × multiplier)

## Completed (from previous phases)
- [x] All P0 tasks (documentation foundation)
- [x] All P1 tasks (signal parser pipeline, validation, risk manager, storage, tooling)
- [x] All P2 tasks (trade executor, order builder, Telegram listener, lifecycle manager, watchdog, pipeline wiring)
- [x] All P3 tasks (dry-run, circuit breaker, alerting, storage hardening, signal lifecycle DB, entry drift guard, execution metrics, ENV sync, session metrics, heartbeat log)
- [x] All P4 High Priority tasks (daily risk guard, startup position sync, VPS runbook, monitoring doc, README update)
