# VPS Deployment Runbook

Ubuntu VPS setup for running telegram-mt5-bot in production.

---

## Prerequisites

| Component | Minimum |
|-----------|---------|
| OS | Ubuntu 22.04 LTS (x86_64) |
| RAM | 2 GB |
| Disk | 10 GB |
| Python | 3.11+ |
| Network | Outbound TCP (Telegram API + MT5 broker) |

---

## 1. System Setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git wget

# Wine (for MT5 terminal)
sudo dpkg --add-architecture i386
sudo mkdir -pm755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources
sudo apt update
sudo apt install -y --install-recommends winehq-stable

# Virtual display for MT5 (headless server)
sudo apt install -y xvfb
```

## 2. Create Bot User

```bash
sudo useradd -m -s /bin/bash botuser
sudo su - botuser
```

## 3. Install MT5 via Wine

```bash
# Start virtual display
Xvfb :0 -screen 0 1024x768x24 &
export DISPLAY=:0

# Download and install MT5
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
wine mt5setup.exe

# After install, MT5 path is typically:
# ~/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe
```

> **First-time login:** Run MT5 interactively once to accept the broker agreement and cache credentials. After that, the bot can start MT5 headlessly.

## 4. Deploy Bot

```bash
cd /opt
sudo git clone <repo-url> telegram-mt5-bot
sudo chown -R botuser:botuser telegram-mt5-bot
cd telegram-mt5-bot

# Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
nano .env  # fill in all credentials
```

### Critical `.env` Values

```env
MT5_PATH=/home/botuser/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe
DRY_RUN=true          # START with dry-run to validate pipeline
TELEGRAM_ADMIN_CHAT=  # your personal chat ID for alerts
```

## 5. First-Run: Telegram Session Auth

```bash
# Run interactively first time to complete Telegram OTP
source venv/bin/activate
python main.py

# Enter the OTP code sent to your Telegram
# Session file is saved for future runs
# Ctrl+C after confirming "Bot is running"
```

## 6. Systemd Service

```bash
sudo cp deploy/telegram-mt5-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-mt5-bot
sudo systemctl start telegram-mt5-bot

# Verify
sudo systemctl status telegram-mt5-bot
sudo journalctl -u telegram-mt5-bot -f
```

## 7. Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw enable

# No inbound ports needed — bot only makes outbound connections
```

---

## Maintenance

### Viewing Logs

```bash
# Systemd journal
sudo journalctl -u telegram-mt5-bot -n 100 --no-pager

# Application log
tail -f /opt/telegram-mt5-bot/logs/bot.log
```

### Graceful Restart

```bash
sudo systemctl restart telegram-mt5-bot

# Bot sends shutdown alert, then startup alert via Telegram
# Open positions are NOT affected — they live in MT5
```

### Updating the Bot

#### Pre-Update Checklist

1. Check no critical positions are about to hit TP/SL
2. Note current open positions and pending orders
3. Back up the database: `cp data/bot.db data/bot.db.pre-update`

#### Update Procedure

```bash
cd /opt/telegram-mt5-bot
sudo systemctl stop telegram-mt5-bot

# Backup state
cp data/bot.db data/bot.db.pre-update
cp .env .env.pre-update

# Pull and install
git pull
source venv/bin/activate
pip install -r requirements.txt  # if deps changed

# Verify new version compiles
python -m py_compile main.py

# Start
sudo systemctl start telegram-mt5-bot
sudo journalctl -u telegram-mt5-bot -f  # watch for errors
```

#### State Preservation

| State | Location | Survives restart? |
|-------|----------|-------------------|
| Open MT5 positions | MT5 terminal (broker) | ✅ Independent of bot |
| Pending MT5 orders | MT5 terminal (broker) | ✅ Independent of bot |
| Telegram session | `forex_bot.session` | ✅ File on disk |
| Signal history | `data/bot.db` | ✅ SQLite file |
| In-memory metrics | `_SessionMetrics` | ❌ Reset on restart |
| Daily risk counters | Polled from MT5 | ✅ Re-polled on startup |

#### Rollback

```bash
sudo systemctl stop telegram-mt5-bot
git checkout <previous-tag-or-commit>
cp data/bot.db.pre-update data/bot.db  # if DB schema changed
cp .env.pre-update .env                # if .env format changed
sudo systemctl start telegram-mt5-bot
```

### Database Backup

```bash
# SQLite DB location
cp /opt/telegram-mt5-bot/data/bot.db /opt/telegram-mt5-bot/data/bot.db.bak

# Auto-cleanup: records older than STORAGE_RETENTION_DAYS are purged daily
```

### Log Rotation

Loguru handles rotation via `LOG_ROTATION` config (default: `10 MB`). No external logrotate configuration needed. See [MONITORING.md](MONITORING.md#log-rotation-validation) for validation details.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `MT5 initialization failed` | Wine/MT5 not running, wrong credentials | Check `MT5_PATH`, run MT5 via Wine manually first |
| `Session expired` | Telegram session invalidated | Delete `forex_bot.session`, restart, re-auth |
| Bot starts but no signals | Wrong `TELEGRAM_SOURCE_CHATS` | Verify chat IDs with `tools/parse_cli.py` |
| `CIRCUIT BREAKER OPENED` | Multiple execution failures | Check MT5 terminal status, broker connection |
| High memory usage | Long-running session with many signals | Restart bot, check `STORAGE_RETENTION_DAYS` |

