# Monitoring & Alerting

Operational monitoring for telegram-mt5-bot in production.

---

## Alert Catalog

All alerts are sent to `TELEGRAM_ADMIN_CHAT` via the Telegram Alerter. Each alert type has an independent cooldown (`ALERT_COOLDOWN_SECONDS`, default 300s) to prevent spam.

| Alert Key | Severity | Trigger | Message |
|-----------|----------|---------|---------|
| `circuit_breaker_open` | 🔴 Critical | N consecutive execution failures | Trading paused automatically |
| `circuit_breaker_close` | 🟢 Info | Successful probe after cooldown | Trading resumed |
| `mt5_connection_lost` | ⚠️ Warning | MT5 watchdog detects disconnect | Attempting reinitialization |
| `mt5_reinit_exhausted` | 🔴 Critical | All reconnect retries failed | **Manual intervention required** |
| `daily_trades_limit` | ⛔ Block | `daily_trades >= MAX_DAILY_TRADES` | Trading paused until midnight UTC |
| `daily_loss_limit` | ⛔ Block | `daily_loss >= MAX_DAILY_LOSS` | Trading paused until midnight UTC |
| `consecutive_loss_limit` | ⛔ Block | `consec_losses >= MAX_CONSECUTIVE_LOSSES` | Trading paused until a winning trade |
| `startup_position_warning` | ⚠️ Warning | Boot with positions >= MAX_OPEN_TRADES | Bot will refuse new signals |
| `bot_started` | 🟢 Info | Bot startup complete | Pipeline active |
| `bot_stopped` | 🔴 Info | Graceful shutdown | — |
| `trade_tracked` | 🟢 Info | Trade outcome detected from MT5 deals | PnL reply sent (v0.6.0) |
| `trade_tracker_partial_throttled` | ⚠️ Info | Partial close reply skipped | Within 60s cooldown (v0.7.0) |
| `edit_decision` | ⚠️ Info | Edited signal processed | CANCEL_ORDER / IGNORE (v0.7.0) |
| `command_response` | 📋 Info | Management command executed | Response sent to source chat + admin (v0.7.1) |
| `breakeven_alert` | 🔒 Info | SL moved to breakeven | Throttled per-ticket 60s (v0.7.1) |
| `trailing_alert` | 📐 Info | Trailing SL moved ≥5 pips | Throttled per-ticket 60s + delta (v0.7.1) |
| `partial_close_alert` | ✂️ Info | Volume partially closed | Throttled per-ticket 60s (v0.7.1) |

---

## Heartbeat

Emitted every `HEARTBEAT_INTERVAL_MINUTES` (default 30, set 0 to disable).

```
[HEARTBEAT] uptime=120m  parsed=15  executed=8  rejected=5  failed=2
            avg_latency=45ms  max_latency=120ms
            open_positions=3  pending_orders=1
            mt5=OK  telegram=OK
            daily_trades=8  daily_loss=$25.50  consec_losses=1
             [Gold_Signals] p=10 e=6 r=3 f=1
             [VIP_Channel]  p=5  e=2 r=2 f=1
```

> Per-channel breakdown appears automatically when 2+ channels are active (v0.7.0).

### Reading the Heartbeat

| Field | Healthy | Investigate |
|-------|---------|-------------|
| `mt5` | `OK` | `FAIL` or `ERR` — MT5 disconnected |
| `telegram` | `OK` | `FAIL` — Telegram session issue |
| `failed` | 0 | >0 increasing — execution problems |
| `avg_latency` | <200ms | >500ms — MT5 or network slowdown |
| `open_positions` | <MAX_OPEN_TRADES | = MAX_OPEN_TRADES — at capacity |
| `consec_losses` | <MAX_CONSECUTIVE_LOSSES | Approaching limit — review strategy |

---

## Debug Workflow

### Signal Not Executing

1. **Check heartbeat** — is bot running? Is MT5 connected?
2. **Check circuit breaker** — look for `circuit_breaker_open` in logs
3. **Check daily guard** — look for `daily_risk_guard_blocked` in logs
4. **Check signal log** — search by fingerprint in `logs/bot.log`:
   ```bash
   grep "fp=<first-12-chars>" logs/bot.log
   ```
5. **Check rejection reason** — look for `signal_rejected` events:
   ```bash
   grep "validation_rejected" logs/bot.log | tail -5
   ```

### MT5 Connection Issues

1. Check MT5 terminal is running: `ps aux | grep terminal`
2. Check Wine display: `echo $DISPLAY` (should be `:0`)
3. Check Xvfb: `ps aux | grep Xvfb`
4. Manual test: `wine "/path/to/terminal64.exe"` (from Xvfb display)
5. Check broker server status on their website

### Telegram Session Issues

1. Delete session file and re-authenticate:
   ```bash
   rm forex_bot.session
   python main.py  # enter OTP
   ```
2. Check `SESSION_RESET_HOURS` — lower value if frequent disconnects

---

## Escalation Playbook

| Situation | Action |
|-----------|--------|
| `mt5_reinit_exhausted` alert | SSH in, check Wine/MT5 process, restart if needed |
| Circuit breaker keeps opening | Review recent execution errors, check broker status |
| Daily loss limit hit early | Review signal source quality, consider lowering lot size |
| Bot not responding to signals | Check `systemctl status`, restart service |
| Session file corrupted | Stop bot, delete `.session` file, restart and re-auth |
| Database errors | Stop bot, backup DB, delete if corrupted, restart |

---

## Log Files

| File | Content |
|------|---------|
| `logs/bot.log` | Structured application logs (rotated at `LOG_ROTATION`) |
| `journalctl -u telegram-mt5-bot` | Systemd stdout/stderr |
| `data/bot.db` | SQLite: signals, orders, events (audit trail) |

### Useful Log Queries

```bash
# Last 5 executed signals
grep "signal_executed" logs/bot.log | tail -5

# All rejections today
grep "signal_rejected" logs/bot.log | grep "$(date +%Y-%m-%d)"

# Daily guard polls
grep "daily_risk_guard_polled" logs/bot.log | tail -5

# Circuit breaker events
grep "circuit_breaker" logs/bot.log

# Trade tracker outcomes
grep "trade_tracked" logs/bot.log | tail -5

# Message edit decisions
grep "edit_decision" logs/bot.log | tail -5
```

---

## Log Rotation Validation

Loguru manages log rotation internally — no external `logrotate` needed.

| Setting | Value | Behavior |
|---------|-------|----------|
| `LOG_ROTATION` | `"10 MB"` (default) | Rotates when file exceeds 10 MB |
| `retention` | `"30 days"` (hardcoded) | Deletes rotated files older than 30 days |
| Thread safety | Built-in | Rotation is atomic; no data loss during rotation |
| Long-running | ✅ Validated | loguru uses `os.rename()` internally — safe for processes running weeks/months |

**What happens during rotation:**
1. Current `bot.log` reaches size limit
2. loguru renames it to `bot.log.YYYY-MM-DD_HH-MM-SS`
3. New empty `bot.log` is created
4. Writing continues without interruption
5. Files older than 30 days are auto-deleted

**No action required** — rotation is fully automatic. Monitor disk usage if `LOG_ROTATION` is set very high or `retention` exceeds available disk.

