# telegram-mt5-bot

Automated Forex / CFD signal → MT5 execution bot with multi-channel support.

Listens to Telegram channels for trading signals, parses them, validates safety rules, executes orders on MetaTrader 5, and tracks trade outcomes with PnL reply messages.

---

## ⚠️ CRITICAL: Trading Logic You MUST Understand

> **This bot trades REAL MONEY. Misconfiguration can cause financial loss.**

### 🔴 Price Reference Rule (Order Type Decision)

The order type (MARKET / LIMIT / STOP) is determined by comparing the signal entry price against LIVE market prices:

| Side | Reference Price | Logic |
|------|----------------|-------|
| **BUY** | **ASK** | `entry < ASK` → BUY_LIMIT · `entry > ASK` → BUY_STOP · `entry ≈ ASK` → MARKET |
| **SELL** | **BID** | `entry > BID` → SELL_LIMIT · `entry < BID` → SELL_STOP · `entry ≈ BID` → MARKET |

> ⚠️ **BUY uses ASK, SELL uses BID.** Getting this wrong means wrong order type, wrong execution price.

### 🔴 Market Tolerance (`MARKET_TOLERANCE_POINTS`)

If `|entry - reference_price| ≤ MARKET_TOLERANCE_POINTS × point`, the order is treated as **MARKET** (immediate execution) instead of LIMIT/STOP.

- Default: `30.0` points (XAUUSD: 3 pips = $0.30)
- Setting too high → signals that should be pending become market orders
- Setting too low → signals near market price become pending when they should execute immediately

### 🔴 Deviation (`DEVIATION_POINTS`)

Maximum acceptable price slippage for MARKET orders. MT5 will reject the order if price moves more than this during execution.

- Default: `20` points
- Too low → frequent rejections during volatility
- Too high → poor fill prices

### 🔴 Risk Sizing

| Mode | Formula | Config |
|------|---------|--------|
| `FIXED_LOT` | Use `FIXED_LOT_SIZE` directly | `FIXED_LOT_SIZE=0.01` |
| `RISK_PERCENT` | `volume = (balance × risk%) / (SL_distance × pip_value)` | `RISK_PERCENT=1.0` |

Volume is always clamped to `[LOT_MIN, LOT_MAX]` and rounded to `LOT_STEP`.

### 🔴 Safety Gates (Validation Rules)

All distances are in **PIPS** (1 pip = 10 points for 5-digit brokers, XAUUSD: 1 pip = $0.10).

| Gate | Config Key | Default | Effect |
|------|-----------|---------|--------|
| Max spread | `MAX_SPREAD_PIPS` | 5.0 | Reject if current spread > 5 pips |
| Max open trades | `MAX_OPEN_TRADES` | 5 | Reject if open positions ≥ 5 |
| Signal age | `SIGNAL_AGE_TTL_SECONDS` | 60 | Reject if signal older than 60s |
| Entry distance | `MAX_ENTRY_DISTANCE_PIPS` | 50.0 | Reject if entry > 50 pips from market |
| Entry drift | `MAX_ENTRY_DRIFT_PIPS` | 10.0 | Reject MARKET if entry drifted > 10 pips |
| Pending TTL | `PENDING_ORDER_TTL_MINUTES` | 15 | Auto-cancel unfilled pending orders |
| Duplicate | fingerprint | — | SHA-256 hash, reject within TTL window |

### 🔴 Daily Risk Guard

Poll-based limits using MT5 closed deal history (`history_deals_get`). All default to 0 = disabled.

| Limit | Config Key | Default | Effect |
|-------|-----------|---------|--------|
| Daily trades | `MAX_DAILY_TRADES` | 0 | Pause after N closed trades per UTC day |
| Daily loss | `MAX_DAILY_LOSS` | 0.0 | Pause when cumulative loss exceeds USD limit |
| Consecutive losses | `MAX_CONSECUTIVE_LOSSES` | 5 | Pause after N consecutive losing trades |
| Poll interval | `DAILY_RISK_POLL_MINUTES` | 5 | How often to refresh from MT5 history |

When a limit is breached, a Telegram alert is sent and trading pauses until the next UTC day (or until a winning trade resets the consecutive counter).

### 🔴 Exposure Control

| Limit | Config Key | Default | Effect |
|-------|-----------|---------|--------|
| Same symbol | `MAX_SAME_SYMBOL_TRADES` | 0 | Reject if same symbol has N+ open |
| Correlated group | `MAX_CORRELATED_TRADES` | 0 | Reject if correlated group has N+ open |
| Groups | `CORRELATION_GROUPS` | (empty) | `XAUUSD:XAGUSD,EURUSD:GBPUSD:EURGBP` |

### 🔴 Position Manager

Background task (disabled by default) that manages open positions:

| Feature | Config Key | Default | Effect |
|---------|-----------|---------|--------|
| Breakeven | `BREAKEVEN_TRIGGER_PIPS` | 0 | Move SL to entry + lock when profit ≥ trigger |
| Lock pips | `BREAKEVEN_LOCK_PIPS` | 2.0 | Pips above entry to lock SL at |
| Trailing stop | `TRAILING_STOP_PIPS` | 0 | Trail SL at fixed pip distance |
| Partial close | `PARTIAL_CLOSE_PERCENT` | 0 | Close % of volume at TP1 |
| Poll interval | `POSITION_MANAGER_POLL_SECONDS` | 5 | Check frequency |

### 🔴 Management Commands

Send these as Telegram messages to manage open positions:

| Command | Effect |
|---------|--------|
| `CLOSE ALL` | Close all open positions |
| `CLOSE XAUUSD` | Close all positions for symbol |
| `CLOSE HALF` | Close 50% of each position |
| `MOVE SL 2025` | Move SL to price on all positions |
| `BREAKEVEN` | Move SL to entry on profitable positions |

### 🔴 Circuit Breaker

After `CIRCUIT_BREAKER_THRESHOLD` consecutive execution failures:
- **Trading pauses** automatically (OPEN state)
- After `CIRCUIT_BREAKER_COOLDOWN` seconds → probe with one trade
- Success → resume all trading · Failure → pause again

---

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd telegram-mt5-bot
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your credentials and settings

# 3. Multi-channel setup (optional)
cp config/channels.example.json config/channels.json
# Edit channels.json with per-channel rules

# 4. Run
python main.py
```

## Production Deployment

For VPS deployment with systemd, see [docs/DEPLOY.md](docs/DEPLOY.md).

For monitoring, alerts, and troubleshooting, see [docs/MONITORING.md](docs/MONITORING.md).

## Configuration

All values are in `.env`. Copy from `.env.example` for the full list with explanations.

### Required Credentials
| Key | Description |
|-----|-------------|
| `TELEGRAM_API_ID` | Telegram API ID from my.telegram.org |
| `TELEGRAM_API_HASH` | Telegram API hash |
| `TELEGRAM_PHONE` | Your phone in international format: `+84327279393` |
| `TELEGRAM_SOURCE_CHATS` | Comma-separated chat IDs or usernames to monitor |
| `MT5_LOGIN` | MetaTrader 5 login number |
| `MT5_PASSWORD` | MT5 password |
| `MT5_SERVER` | MT5 broker server name |

### Critical Trade Execution Settings
| Key | Default | Description |
|-----|---------|-------------|
| `BOT_MAGIC_NUMBER` | `234000` | Unique ID to tag bot orders in MT5 |
| `DEVIATION_POINTS` | `20` | Max price slippage for market orders |
| `MARKET_TOLERANCE_POINTS` | `30.0` | Entry-vs-price threshold for market/pending decision |
| `ORDER_MAX_RETRIES` | `3` | Retry count for failed `order_send` calls |
| `ORDER_RETRY_DELAY_SECONDS` | `1.0` | Base delay between retries (exponential) |

### Dry Run Mode
```env
DRY_RUN=true
```
Simulates execution without sending real orders. **Bid/Ask prices are dynamically derived from the signal entry** to maintain correct validation and order type logic.

## Project Structure

```
├── main.py                      # Entry point, pipeline orchestration
├── config/
│   ├── settings.py              # Typed config from .env
│   ├── channels.json            # Per-channel rules (created from .example)
│   └── channels.example.json    # Channel config template
├── core/
│   ├── models.py                # Data contracts (ParsedSignal, ExecutionResult, etc.)
│   ├── signal_parser/           # 7-module parser pipeline
│   ├── signal_validator.py      # Safety gates (spread, age, distance, duplicates)
│   ├── risk_manager.py          # Position sizing
│   ├── order_builder.py         # Order type decision + MT5 request builder
│   ├── trade_executor.py        # MT5 connection + bounded retry execution
│   ├── storage.py               # SQLite persistence (WAL mode, versioned migrations)
│   ├── telegram_listener.py     # Telethon listener + auto-reconnect
│   ├── telegram_alerter.py      # Rate-limited admin alerts + reply threading
│   ├── circuit_breaker.py       # CLOSED/OPEN/HALF_OPEN trade safety
│   ├── daily_risk_guard.py      # Poll-based daily risk limits (MT5 deal history)
│   ├── exposure_guard.py        # Per-symbol + correlation group limits
│   ├── position_manager.py      # Breakeven, trailing stop, partial close (per-channel)
│   ├── channel_manager.py       # Per-channel rule configuration
│   ├── trade_tracker.py         # Background deal polling, PnL tracking, reply messages
│   ├── command_parser.py        # Management command parser
│   ├── command_executor.py      # Execute management commands vs MT5
│   ├── order_lifecycle_manager.py # Pending order TTL expiration
│   ├── mt5_watchdog.py          # Connection health monitor
│   └── message_update_handler.py # MessageEdited handling
├── utils/
│   ├── logger.py                # Structured JSON logging
│   └── symbol_mapper.py         # Symbol alias resolution
├── tools/
│   ├── parse_cli.py             # Parser debug CLI
│   └── benchmark.py             # Performance benchmark
├── deploy/
│   └── telegram-mt5-bot.service # Systemd unit file
├── docs/                        # Architecture, plan, tasks, operations
│   ├── DEPLOY.md                # VPS deployment runbook
│   └── MONITORING.md            # Alert catalog + debug workflow
└── .env.example                 # All configuration keys with docs
```

## Pipeline Flow

```
Telegram NewMessage
  → signal_parser.parse()
  → circuit_breaker.is_trading_allowed
  → daily_risk_guard.is_trading_allowed
  → exposure_guard.is_allowed(symbol)
  → storage.is_duplicate()
  → signal_validator.validate(price, spread, positions, age, distance)
  → risk_manager.calculate_volume()
  → order_builder.decide_order_type() + build_request()
  → validator.validate_entry_drift() [MARKET orders only]
  → trade_executor.execute() [or DRY_RUN simulate]
  → storage.store_signal() + store_order() + store_event(channel_id)
```

### Background Tasks
```
TradeTracker: poll MT5 history_deals_get()
  → match deal → DB order (ticket / position_ticket)
  → store_trade() → reply_to_message() (PnL under original signal)
  → partial close throttle (60s cooldown)

PositionManager: poll open positions
  → per-channel rules from channels.json
  → breakeven / trailing stop / partial close

Heartbeat: per-channel metrics breakdown
```

## Signal Lifecycle Events (DB Tracing)

Every signal is traced through the `events` table:
```
signal_received → signal_parsed → signal_submitted → signal_executed
                                → signal_rejected (with reason)
                                → signal_failed (with retcode)
```

## Multi-Channel Setup

To process signals from multiple Telegram channels with per-channel rules:

1. Copy the template:
   ```bash
   cp config/channels.example.json config/channels.json
   ```

2. Edit `config/channels.json` — set per-channel rules (breakeven, trailing stop, partial close).
   Channels not listed fall back to the `"default"` section or global `.env` values.

3. **Trade Outcome Tracking** — set `TRADE_TRACKER_POLL_SECONDS` in `.env` (default 0 = disabled):
   ```env
   TRADE_TRACKER_POLL_SECONDS=30
   ```
   When enabled, the bot polls MT5 deal history, tracks PnL, and replies under the original Telegram signal.

## Version History

See [CHANGELOG.md](CHANGELOG.md) for full version history.

Current: **v0.7.1**

