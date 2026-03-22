# Dashboard Documentation

## Architecture

```
┌──────────────────────────────┐
│        Vercel (Optional)      │
│   Static Frontend (HTML/JS)   │
│   Calls VPS API via HTTPS     │
└──────────┬───────────────────┘
           │  /api/* + X-API-Key
           ▼
┌──────────────────────────────┐
│         VPS Server            │
│  ┌────────────────────────┐  │
│  │   FastAPI (dashboard.py)│  │
│  │   - CORS middleware     │  │
│  │   - API key auth        │  │
│  │   - Jinja2 templates    │  │
│  │   - Static files        │  │
│  └────────┬───────────────┘  │
│           │ read-only         │
│  ┌────────▼───────────────┐  │
│  │   SQLite (data/bot.db)  │  │
│  │   Written by Forex Bot  │  │
│  └────────────────────────┘  │
│                               │
│  ┌────────────────────────┐  │
│  │   Forex Bot (main.py)   │  │
│  │   Writes trades/signals │  │
│  └────────────────────────┘  │
└──────────────────────────────┘
```

### Key Principles
- **Read-only DB access** — dashboard never writes to SQLite
- **Separate process** — restart dashboard ≠ restart bot
- **Stateless API** — all data from DB, no in-memory state
- **Auto-refresh** — frontend polls API every 30 seconds

### Data Flow
```
Bot writes → SQLite → Dashboard reads → API JSON → Frontend renders
```

---

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Backend** | FastAPI | ≥0.110.0 | REST API + page routing |
| **Server** | Uvicorn | ≥0.27.0 | ASGI server |
| **Templates** | Jinja2 | ≥3.1.0 | Server-side HTML rendering |
| **Database** | SQLite | Built-in | Read-only via `?mode=ro` URI |
| **Charts** | Chart.js | 4.4.0 | CDN-loaded, no build step |
| **Fonts** | Google Inter | -- | CDN-loaded |
| **Styling** | Vanilla CSS | -- | Dark theme, glassmorphism |

---

## File Structure

```
dashboard/
├── __init__.py
├── dashboard.py              # FastAPI app entry point
├── api/
│   ├── __init__.py
│   └── routes.py             # 7 REST API endpoints
├── db/
│   ├── __init__.py
│   └── queries.py            # DashboardDB — all SQL queries
├── templates/
│   ├── base.html             # Layout (nav, footer, scripts)
│   ├── overview.html         # Main dashboard page
│   ├── channels.html         # Per-channel performance
│   └── trades.html           # Trade history + filters
├── static/
│   ├── style.css             # Dark theme CSS (~500 LOC)
│   └── charts.js             # API client, Chart.js helpers
└── docs/
    └── DASHBOARD.md           # This file
```

---

## Pages & Logic

### Page 1: Overview (`/`)
| Section | Data Source | API |
|---------|-----------|-----|
| 4 stat cards (Net PnL, Win Rate, Trades, Active) | `trades` + `signal_groups` | `/api/overview` |
| Daily PnL bar chart (7/30/90 days) | `trades` grouped by date | `/api/daily-pnl?days=N` |
| Top Channels horizontal bar | `trades` grouped by channel | `/api/channels` |
| Recent Trades table (8 rows) | `trades` joined `signals` | `/api/trades?per_page=8` |
| Active Positions table | `signal_groups` where active | `/api/active` |

### Page 2: Channels (`/channels`)
| Section | Data Source | API |
|---------|-----------|-----|
| Channel cards (PnL, win/loss, avg) | `trades` grouped by channel | `/api/channels` |
| Win/loss progress bar | Calculated from wins/total | -- |
| Comparison bar chart | Same as cards | `/api/channels` |

### Page 3: Trades (`/trades`)
| Section | Data Source | API |
|---------|-----------|-----|
| Filter bar (date, channel, symbol, outcome) | `signals` + `trades` | `/api/channel-list`, `/api/symbols` |
| Summary bar (count, total PnL, avg) | Aggregated from filter | `/api/trades?...` |
| Data table (10 columns, paginated) | `trades` joined `signals` | `/api/trades?page=N` |

---

## API Reference

| Method | Endpoint | Params | Returns |
|--------|----------|--------|---------|
| GET | `/api/overview` | — | `{total_trades, net_pnl, win_rate, avg_pnl, active_groups, ...}` |
| GET | `/api/daily-pnl` | `days` (1-365, default 30) | `[{date, pnl, net_pnl, trades}]` |
| GET | `/api/channels` | — | `[{channel_id, total_pnl, wins, losses, avg_pnl, ...}]` |
| GET | `/api/channels/{id}/daily-pnl` | `days` | `[{date, pnl, trades}]` |
| GET | `/api/trades` | `channel, symbol, from, to, outcome, page, per_page` | `{trades: [...], total, page, total_pnl, avg_pnl}` |
| GET | `/api/active` | — | `[{fingerprint, symbol, side, tickets, entry_prices, ...}]` |
| GET | `/api/symbols` | — | `["XAUUSD", "EURUSD", ...]` |
| GET | `/api/channel-list` | — | `[{id, name}]` |

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Bot's SQLite database (`data/bot.db`)

### Install Dependencies
```bash
pip install fastapi uvicorn jinja2
# or
pip install -r requirements.txt
```

### Run Locally
```bash
# From project root
python -m dashboard.dashboard

# Custom port
DASHBOARD_PORT=3000 python -m dashboard.dashboard
```

### Run on VPS
```bash
# With API key protection
DASHBOARD_DB_PATH=/path/to/data/bot.db \
DASHBOARD_API_KEY=your_secret_key \
DASHBOARD_HOST=0.0.0.0 \
DASHBOARD_PORT=8000 \
python -m dashboard.dashboard
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_DB_PATH` | `data/bot.db` | Path to SQLite database |
| `DASHBOARD_API_KEY` | _(empty)_ | API key for `/api/*` (empty = no auth) |
| `DASHBOARD_PORT` | `8000` | Server port |
| `DASHBOARD_HOST` | `0.0.0.0` | Bind address |

### Deploy Frontend to Vercel (Optional)
1. Copy `dashboard/templates/` and `dashboard/static/` to a Vercel project
2. Convert Jinja2 templates to static HTML
3. Update `charts.js` API base URL to your VPS IP:
   ```javascript
   // In charts.js, change fetch URL:
   fetch(`https://your-vps-ip:8000/api${endpoint}`, { headers })
   ```
4. Set API key in Vercel env vars

### Reverse Proxy (Nginx)
```nginx
server {
    listen 443 ssl;
    server_name dashboard.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Roadmap

### Current (v0.12.0)
- [x] Overview page (stat cards, PnL chart, recent trades)
- [x] Channel performance page (cards, comparison chart)
- [x] Trade history page (filters, pagination)
- [x] API key authentication
- [x] CORS support
- [x] Auto-refresh 30s

### Planned
- [ ] Channel name mapping (ID → human name from `channels.yml`)
- [ ] Symbol-level analytics page
- [ ] Export trades to CSV
- [ ] WebSocket live updates (replace polling)
- [ ] Monthly/weekly summary reports
- [ ] Chart: equity curve (cumulative PnL over time)
- [ ] Chart: win rate by symbol
- [ ] Dark/light theme toggle
- [ ] Basic auth (username + password)

### Future Consideration
- [ ] Migrate to PostgreSQL for multi-user access
- [ ] Dockerize dashboard for easy deployment
- [ ] Mobile-responsive PWA
