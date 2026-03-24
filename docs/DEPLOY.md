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

## Architecture on Linux

```
┌─────────────────────────────────────────────────┐
│  Ubuntu 22.04 VPS                               │
│                                                 │
│  ┌──────────────────┐   rpyc (port 18812)       │
│  │  Bot (Python)    │◄──────────────────────┐   │
│  │  main.py         │                       │   │
│  │  mt5_bridge.py   │                       │   │
│  └──────────────────┘                       │   │
│                                             │   │
│  ┌──────────────────────────────────────┐   │   │
│  │  Wine Environment                    │   │   │
│  │  ┌──────────────┐  ┌──────────────┐  │   │   │
│  │  │  MT5 Terminal │  │  Python.exe  │──┘   │   │
│  │  │  (terminal64) │  │  mt5linux    │      │   │
│  │  └──────────────┘  │  rpyc server │      │   │
│  │                    └──────────────┘      │   │
│  └──────────────────────────────────────┘   │   │
│                                             │   │
│  Xvfb :99 (virtual display)                │   │
└─────────────────────────────────────────────────┘
```

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

> **⚠️ Wine Version:** If `winehq-stable` installs Wine 11+ and MT5 shows "debugger detected" error, downgrade to Wine 10.0:
> ```bash
> sudo apt install winehq-stable=10.0.0.0~jammy-1 \
>   wine-stable=10.0.0.0~jammy-1 \
>   wine-stable-amd64=10.0.0.0~jammy-1 \
>   wine-stable-i386=10.0.0.0~jammy-1
> ```

## 2. Create Bot User

```bash
sudo useradd -m -s /bin/bash botuser
sudo su - botuser
```

## 3. Install MT5 via Wine

```bash
# Start virtual display
Xvfb :99 -screen 0 1024x768x16 &
export DISPLAY=:99

# Download and install MT5
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
wine mt5setup.exe

# After install, MT5 path is typically:
# ~/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe
```

> **First-time login:** Run MT5 interactively once (via VNC or X forwarding) to accept the broker agreement and cache credentials.

## 4. Install Python inside Wine (for rpyc bridge)

```bash
export DISPLAY=:99

# Download Windows Python 3.11
wget https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

# Install Python in Wine (make sure to check "Add to PATH")
wine python-3.11.9-amd64.exe /quiet InstallAllUsers=1 PrependPath=1

# Verify
wine python --version

# Install MetaTrader5 + mt5linux inside Wine Python
wine python -m pip install MetaTrader5 mt5linux
```

## 5. Setup rpyc Bridge Server

The rpyc bridge allows native Linux Python to communicate with the MT5 terminal running inside Wine.

```bash
# Test the bridge manually first:
export DISPLAY=:99

# Terminal 1: start rpyc server (inside Wine)
wine python -m mt5linux
# Output should show: "rpyc server started on port 18812"

# Terminal 2: test connection from Linux Python
python3.11 -c "
from mt5linux import MetaTrader5
mt5 = MetaTrader5(host='localhost', port=18812)
mt5.initialize()
print(mt5.account_info())
mt5.shutdown()
"
```

## 6. Deploy Bot

```bash
cd /opt
sudo git clone <repo-url> telegram-mt5-bot
sudo chown -R botuser:botuser telegram-mt5-bot
cd telegram-mt5-bot

# Python environment (Linux native)
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# On Linux, this installs mt5linux automatically (platform-conditional)

# Configuration
cp .env.example .env
nano .env  # fill in all credentials

# Multi-channel rules (optional)
cp config/channels.example.json config/channels.json
nano config/channels.json
```

### Critical `.env` Values (Linux)

```env
# MT5_PATH is NOT needed on Linux (bridge connects via rpyc)
# MT5_RPYC_HOST=localhost   # default
# MT5_RPYC_PORT=18812       # default
DRY_RUN=true          # START with dry-run to validate pipeline
TELEGRAM_ADMIN_CHAT=  # your personal chat ID for alerts
TRADE_TRACKER_POLL_SECONDS=30
```

## 7. First-Run: Telegram Session Auth

```bash
source venv/bin/activate
python main.py
# Enter the OTP code sent to your Telegram
# Session file is saved for future runs
# Ctrl+C after confirming "Bot is running"
```

## 8. Systemd Services

Two services are needed on Linux:

1. **mt5-rpyc-server** — runs Wine + MT5 + rpyc bridge
2. **telegram-mt5-bot** — runs the bot (depends on rpyc server)

```bash
# Install both services
sudo cp deploy/mt5-rpyc-server.service /etc/systemd/system/
sudo cp deploy/telegram-mt5-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable mt5-rpyc-server
sudo systemctl enable telegram-mt5-bot

sudo systemctl start mt5-rpyc-server
# Wait a few seconds for MT5 to initialize
sleep 10
sudo systemctl start telegram-mt5-bot

# Verify
sudo systemctl status mt5-rpyc-server
sudo systemctl status telegram-mt5-bot
sudo journalctl -u telegram-mt5-bot -f
```

## 9. Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw enable

# No inbound ports needed — bot only makes outbound connections
# rpyc runs on localhost only (not exposed)
```

---

## Maintenance

### Viewing Logs

```bash
# Bot logs
sudo journalctl -u telegram-mt5-bot -n 100 --no-pager

# rpyc bridge logs
sudo journalctl -u mt5-rpyc-server -n 50 --no-pager

# Application log
tail -f /opt/telegram-mt5-bot/logs/bot.log
```

### Graceful Restart

```bash
# Restart bot only (rpyc bridge stays running)
sudo systemctl restart telegram-mt5-bot

# Restart everything (if MT5 is stuck)
sudo systemctl restart mt5-rpyc-server
sleep 10
sudo systemctl restart telegram-mt5-bot
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

# Start (rpyc bridge usually doesn't need restart)
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
| rpyc connection | mt5_bridge.py | ✅ Auto-reconnects |

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
cp /opt/telegram-mt5-bot/data/bot.db /opt/telegram-mt5-bot/data/bot.db.bak

# Auto-cleanup: records older than STORAGE_RETENTION_DAYS are purged daily
```

### Log Rotation

Loguru handles rotation via `LOG_ROTATION` config (default: `10 MB`). No external logrotate configuration needed. See [MONITORING.md](MONITORING.md#log-rotation-validation) for validation details.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `MT5 initialization failed` | Wine/MT5 not running, rpyc server down | Check `systemctl status mt5-rpyc-server` |
| `rpyc connection refused` | rpyc server not started or crashed | Restart: `sudo systemctl restart mt5-rpyc-server` |
| `debugger has been found` | Wine 11+ triggers MT5 anti-debug | Downgrade to Wine 10.0 (see step 1) |
| `ValueError: invalid message type: 18` | rpyc version mismatch | Match rpyc versions in Wine and Linux Python |
| `Session expired` | Telegram session invalidated | Delete `forex_bot.session`, restart, re-auth |
| Bot starts but no signals | Wrong `TELEGRAM_SOURCE_CHATS` | Verify chat IDs with `tools/parse_cli.py` |
| `CIRCUIT BREAKER OPENED` | Multiple execution failures | Check MT5 terminal status, broker connection |
| MT5 display issues | Missing Xvfb | Verify `Xvfb :99` is running |
