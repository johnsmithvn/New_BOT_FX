# Dashboard V2 — React SPA

Advanced analytics dashboard for Forex Bot, built with React 19 + Vite 6.

---

## Quick Start

```bash
# 1. Install dependencies (first time only)
npm install

# 2. Start V1 backend (provides API on port 8000)
python -m dashboard.dashboard     # from project root

# 3. Start V2 dev server
npm run dev                       # http://localhost:5173

# OR use the unified launcher:
python run.py v2                  # V2 only (still needs backend manually)
python run.py dash               # V1 + backend on port 8000
```

> **Bot không cần chạy.** Dashboard chỉ đọc database SQLite (`data/bot.db`). Bot ghi dữ liệu vào DB, dashboard đọc ra. Hoàn toàn độc lập.

---

## Architecture

```
dashboard-v2/
├── index.html               # HTML entry point
├── vite.config.js           # Vite config (proxy /api → :8000)
├── package.json             # Dependencies
├── public/
│   └── favicon.svg          # Gradient chart icon
└── src/
    ├── main.jsx             # React root + QueryClientProvider
    ├── App.jsx              # Router + Navbar + AnimatePresence
    ├── api/
    │   └── client.js        # Fetch wrapper + API key auth + DELETE support
    ├── hooks/
    │   └── useApi.js        # TanStack Query hooks (16 hooks)
    ├── components/
    │   ├── Navbar.jsx        # Top nav + status indicator
    │   ├── StatCard.jsx      # Animated KPI card
    │   ├── ChartCard.jsx     # Chart wrapper + loading skeleton
    │   ├── SparkCard.jsx     # KPI card + inline sparkline
    │   └── ConfirmModal.jsx  # Glassmorphism confirm popup (v0.16.0)
    ├── charts/
    │   ├── ChartPrimitives.jsx  # Premium tooltip + label renderers
    │   ├── EquityCurve.jsx      # Area chart + peak annotation
    │   ├── DailyPnlBars.jsx     # Bar chart + data labels
    │   └── WinLossDonut.jsx     # Interactive donut + glow
    ├── pages/
    │   ├── Overview.jsx      # Main dashboard + chart toggle (v0.16.1)
    │   ├── Analytics.jsx     # Advanced analytics
    │   ├── Channels.jsx      # Channel performance
    │   ├── Symbols.jsx       # Symbol breakdown
    │   ├── Trades.jsx        # Trade journal
    │   ├── Signals.jsx       # Signal lifecycle + detail modal (v0.16.0)
    │   └── Settings.jsx      # API key + connection
    ├── utils/
    │   └── format.js         # Currency formatting + channel name resolver
    └── styles/
        ├── global.css        # CSS variables, reset, fonts
        ├── layout.css        # Grid, responsive, nav, footer
        ├── components.css    # Cards, badges, buttons, tables
        └── charts.css        # Tooltip, label, chart styles
```

### Data Flow

```
SQLite (data/bot.db)
        │
        ▼
FastAPI Backend (port 8000)  ←── Dashboard V1 (Jinja2 pages)
        │
        ▼ (Vite proxy: /api/* → :8000)
React SPA (port 5173)
  └── TanStack Query (auto-refetch 30s)
      └── Recharts / Nivo (render)
```

### Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | 19.x | UI framework |
| `react-router-dom` | 7.x | Client-side routing |
| `recharts` | 3.x | Charts (bar, line, area, pie, radar, composed) |
| `@tanstack/react-query` | 5.x | Server state management, auto-refetch |
| `framer-motion` | 12.x | Page transitions, animations |
| `lucide-react` | 0.577+ | Icon library |
| `@nivo/core` | 0.99.x | Advanced charts (heatmap, treemap) |

---

## Pages & Features

### 1. Overview (`/`)

| Component | Chart Type | Ý Nghĩa |
|-----------|-----------|---------|
| **Stat Cards** (×4) | KPI cards | Net PnL, Win Rate, Total Trades, Active Positions |
| **Win Rate Gauge** | Radial bar | Gauge hiện % win rate + W/L counts (v0.16.1) |
| **Signal Breakdown** | Table card | Đếm signals theo status: executed/rejected/failed (v0.16.1) |
| **Equity Curve** | Area chart | Cumulative PnL over time — xu hướng tài khoản tăng/giảm |
| **Daily PnL + Cumulative** | Combo bar+line | PnL ngày (bars) + tích lũy (line) — thấy vi mô + vĩ mô |
| **Monthly Wins vs Losses** | Grouped bars | Tổng $ wins vs losses theo tháng (6 tháng gần nhất) |
| **PnL by Weekday** | Bar chart | PnL tổng hợp Mon–Fri — biết ngày nào profitable (v0.16.1) |
| **Win/Loss Donut** | Interactive donut | Tỷ lệ thắng/thua — hover glow + expand |
| **Top Channels** | Horizontal bars | So sánh PnL giữa các channel — channel nào hiệu quả |
| **Active Positions** | Table | Vị thế đang mở (symbol, side, tickets) |

> **Chart Toggle** (v0.16.1): Nút "Customize" góc phải header → dropdown cho phép ẩn/hiện 9 chart cards. Setting lưu vào localStorage.

### 2. Analytics (`/analytics`)

| Component | Chart Type | Ý Nghĩa |
|-----------|-----------|---------|
| **Weekly Win vs Loss** | Stacked bar + line | Wins/Losses theo tuần + Net PnL line |
| **PnL Distribution** | Histogram | Phân phối lãi/lỗ — phát hiện "fat tail" risk |
| **Max Drawdown** | Area chart | Sụt giảm từ peak — chỉ số rủi ro quan trọng nhất |
| **Trading Activity** | Combo bar + line | Số trades/ngày + tích lũy — volume analysis |
| **Symbol Comparison** | Butterfly bars | Wins vs Losses per symbol — biết symbol nào trade tốt |

### 3. Channels (`/channels`)

| Component | Ý Nghĩa |
|-----------|---------|
| **Comparison Chart** | Horizontal bars so sánh Total PnL giữa channels |
| **Channel Cards** | Cards tương tác: PnL, Win Rate progress bar, W/L, Avg PnL |
| **Daily PnL Drill-down** | Click card → line chart PnL 30 ngày riêng cho channel đó |

### 4. Symbols (`/symbols`)

| Component | Ý Nghĩa |
|-----------|---------|
| **Performance Table** | Bảng đầy đủ: symbol, trades, win rate (progress bar), PnL, avg PnL |
| **PnL Ranking** | Horizontal bars xếp hạng symbol theo tổng PnL |
| **Top 5 Radar** | Radar chart đa chiều: Win Rate + Activity cho top 5 symbol |

### 5. Trades (`/trades`)

| Component | Ý Nghĩa |
|-----------|---------|
| **Multi-Filter** | Lọc theo: Channel, Symbol, Date range, Outcome (Win/Loss) |
| **Summary Bar** | Tổng trades, Total PnL, Avg PnL cho kết quả đã lọc |
| **Trade Table** | Bảng: time, symbol, side, entry, close, volume, PnL, commission |
| **Pagination** | 20 trades/trang, Prev/Next |
| **CSV Export** | Tải file CSV toàn bộ trades (theo filter) |

### 6. Signals (`/signals`) — v0.16.0

| Component | Ý Nghĩa |
|-----------|---------|
| **Signal Table** | Bảng expandable — mỗi dòng = 1 signal, click `>` xem orders con |
| **Filters** | Channel, Symbol, Status (executed/rejected/failed), Date range |
| **Detail Modal** | Click 👁 → popup raw text, parsed result, timeline, orders, trades |
| **Cascade Delete** | Click 🗑 → xóa signal + ALL orders + trades liên quan |
| **Order Delete** | Xóa riêng 1 order trong detail modal |
| **ConfirmModal** | Popup glassmorphism confirm trước khi xóa (type-to-confirm) |
| **Pagination** | 20 signals/trang |

### 7. Settings (`/settings`)

| Component | Ý Nghĩa |
|-----------|---------|
| **Connection Status** | Live/Offline indicator — API có kết nối không |
| **API Key** | Nhập/thay đổi API key (gửi qua `X-API-Key` header) |
| **About** | Version info, tech stack |

---

## Design System

### Theme
- **Mode**: Dark only
- **Background**: `#0a0e1a` (primary), `rgba(15,23,42,0.6)` (cards)
- **Glassmorphism**: `backdrop-filter: blur(12px)` + subtle border
- **Accents**: Green (`#22c55e`), Red (`#ef4444`), Blue (`#3b82f6`), Purple (`#8b5cf6`), Amber (`#f59e0b`)

### Typography
- **Body**: Inter (Google Fonts)
- **Numbers/Code**: JetBrains Mono (monospace)

### Premium Tooltip (`ChartPrimitives.jsx`)
- Glassmorphism background (`rgba(15,23,42,0.95)` + blur)
- Color-coded values: green = profit, red = loss
- Monospace font for numbers
- Color dots for multi-series
- Optional total row

### Chart Interactions
- **Donut**: Hover → sector expand + outer glow ring
- **Bars**: Data labels showing `$X.X` on each bar
- **Equity**: Peak annotation reference line
- **Drawdown**: Max drawdown annotation
- **Active dots**: Glow effect on hover

---

## API Endpoints (Shared with V1)

| Endpoint | Method | Response |
|----------|--------|----------|
| `/api/overview` | GET | `{net_pnl, win_rate, wins, losses, total_trades, ...}` |
| `/api/daily-pnl?days=N` | GET | `[{date, net_pnl, trades}]` |
| `/api/equity-curve?days=N` | GET | `[{date, cumulative_pnl}]` |
| `/api/channels` | GET | `[{channel_id, channel_name, total_pnl, ...}]` |
| `/api/symbol-stats` | GET | `[{symbol, total_pnl, avg_pnl, wins, losses, win_rate}]` |
| `/api/trades?page=&per_page=&...` | GET | `{trades: [...], total, page, per_page}` |
| `/api/active` | GET | `[{symbol, side, tickets, channel_name}]` |
| `/api/channel-list` | GET | `[{id, name}]` |
| `/api/export/csv` | GET | CSV file download |
| `/api/signals?page=&per_page=&...` | GET | `{signals: [...], total, page, per_page}` (v0.16.0) |
| `/api/signals/{fingerprint}` | GET | `{signal, orders, trades, events, groups}` (v0.16.0) |
| `/api/signals/{fingerprint}` | DELETE | Cascade delete signal + all related data (v0.16.0) |
| `/api/orders/{order_id}` | DELETE | Delete individual order (v0.16.0) |
| `/api/trades/{trade_id}` | DELETE | Delete individual trade (v0.16.0) |
| `/api/data/counts` | GET | Row counts per table (v0.16.0) |
| `/api/data/all` | DELETE | Clear all data tables (v0.16.0) |
| `/api/data/{table}` | DELETE | Clear specific table (v0.16.0) |

Auto-refetch: TanStack Query polls every 30 seconds.

---

## Build & Deploy

```bash
# Development
npm run dev              # Vite dev server + HMR

# Production build
npm run build            # Output: dist/ (static files)
npx vite preview         # Preview production build locally

# Production deploy
# Serve dist/ with any static file server (Nginx, Caddy, etc.)
# Set VITE_API_URL env var to point to your FastAPI backend
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------:|
| `VITE_API_URL` | `http://localhost:8000` | Backend origin/base URL (no `/api` suffix) |

> **Note:** Set `VITE_API_URL` to the backend origin (e.g., `http://localhost:8000`), *not* to `/api`.
> The client internally calls `${VITE_API_URL}/api/...`, so `VITE_API_URL=/api` would produce `/api/api/...`.

---

## Roadmap

### Completed ✅
- [x] Project scaffold (Vite + React 19)
- [x] Design system (dark glassmorphism, 4 CSS files)
- [x] API client + 16 TanStack Query hooks
- [x] 7 pages with 20+ chart types
- [x] Premium tooltip system
- [x] Framer Motion page transitions
- [x] Interactive donut with glow
- [x] Combo charts (bar + line overlay)
- [x] Build verification (2775 modules, 249kB gzip)
- [x] Signal Lifecycle page — expandable table + detail modal (v0.16.0)
- [x] Cascade delete — signals, orders, trades (v0.16.0)
- [x] ConfirmModal — shared glassmorphism popup (v0.16.0)
- [x] Win Rate Gauge — radial bar (v0.16.1)
- [x] Signal Breakdown — table card (v0.16.1)
- [x] PnL by Weekday — bar chart Mon–Fri (v0.16.1)
- [x] Chart Toggle — Customize dropdown + localStorage persistence (v0.16.1)

### Planned 🔮
- [ ] Real-time WebSocket updates (replace polling)
- [ ] PnL Heatmap (calendar view — which days are profitable)
- [ ] Treemap chart (proportional symbol allocation)
- [ ] Dark/Light theme toggle
- [ ] Notification center (alerts from bot)
- [ ] Mobile responsive improvements
- [ ] PWA support (installable on phone)
- [ ] Custom date range for all charts
- [ ] Performance comparison: period vs period
- [ ] Data management UI in Settings page (clear tables)

---

## Version

**Current: v0.16.1**

See [CHANGELOG.md](../CHANGELOG.md) for full history.
