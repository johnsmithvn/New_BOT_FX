# TASKS

## Current Phase
- `P4 - Production Operations (R5)`

## High Priority

### VPS Deployment Runbook
- [ ] Write `docs/DEPLOY.md` — Ubuntu VPS setup: Python venv, Wine + MT5, firewall, env config
- [ ] Create `telegram-mt5-bot.service` systemd unit file with `Restart=always`

### Daily Risk Guard
- [ ] Add `MAX_DAILY_TRADES`, `MAX_DAILY_LOSS`, `MAX_CONSECUTIVE_LOSSES` to config
- [ ] Implement daily counter reset at midnight UTC in background task
- [ ] Block new signal execution when any daily limit is hit
- [ ] Send Telegram alert when limit triggered
- [ ] Reset consecutive losses counter on each successful trade

### Startup Position Sync
- [ ] On bot boot, query MT5 for existing open positions and pending orders
- [ ] Populate `order_lifecycle_manager` with existing pending order tickets + timestamps
- [ ] Log position sync summary on startup

### Monitoring / Alerting Doc
- [ ] Write `docs/MONITORING.md` — what alerts exist, cooldowns, escalation path

### README — VPS Quick-Start
- [ ] Add "Production Deployment" section to `README.md` referencing `DEPLOY.md`

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
