# Dashboard Features — V1 & V2 Complete Reference

Tổng hợp toàn bộ UI/UX, chức năng, và ý nghĩa từng biểu đồ cho cả hai version dashboard.

---

## 📋 Tổng Quan Kiến Trúc

| | **V1 — FastAPI + Jinja2** | **V2 — React SPA** |
|---|---|---|
| **Tech** | Chart.js, vanilla JS, server-side rendering | Recharts, React 19, Vite 6, TanStack Query |
| **Port** | `http://localhost:8000` | `http://localhost:5173` |
| **Chạy** | `python -m dashboard.dashboard` | `cd dashboard-v2 && npm run dev` |
| **Số trang** | 3 (Overview, Channels, Trades) | 7 (Overview, Analytics, Channels, Symbols, Trades, **Signals**, Settings) |
| **Backend** | FastAPI (chung) | Reuse API V1, proxy qua Vite |
| **Auto-refresh** | 30 giây | 30 giây (TanStack Query) |
| **Design** | Dark mode, neon accents | Dark glassmorphism, gradient accents, micro-animations |
| **Write ops** | ❌ Read-only | ✅ DELETE (signals, orders, trades, clear data) |

> V1 = read-only. V2 hỗ trợ **delete operations** (v0.16.0) qua REST API với CORS allow DELETE.

---

## 📊 API Endpoints (Dùng Chung)

| Endpoint | Mô Tả | Dữ Liệu Trả Về |
|----------|--------|-----------------|
| `/api/overview` | Thống kê tổng hợp | `net_pnl`, `win_rate`, `wins`, `losses`, `total_trades`, `active_groups`, `avg_pnl`, `total_commission` |
| `/api/daily-pnl?days=N` | PnL theo ngày | `[{date, net_pnl, trades}]` |
| `/api/equity-curve?days=N` | Đường cong vốn tích lũy | `[{date, cumulative_pnl}]` |
| `/api/channels` | Hiệu suất theo channel | `[{channel_id, channel_name, total_pnl, wins, losses, total_trades, avg_pnl, win_rate}]` |
| `/api/symbol-stats` | Hiệu suất theo symbol | `[{symbol, total_pnl, avg_pnl, wins, losses, total_trades, win_rate}]` |
| `/api/trades?page=&per_page=&...` | Lịch sử giao dịch (phân trang) | `{trades: [...], total, page, per_page, total_pnl, avg_pnl}` |
| `/api/active` | Vị thế đang mở | `[{symbol, side, tickets, channel_name}]` |
| `/api/channel-list` | Danh sách channel ID + tên | `[{id, name}]` |
| `/api/export/csv` | Xuất CSV | File CSV download |
| `/api/signals?page=&per_page=&...` | Signals phân trang (v0.16.0) | `{signals: [...], total, page, per_page}` |
| `/api/signals/{fingerprint}` | Signal lifecycle detail (v0.16.0) | `{signal, orders, trades, events, groups}` |
| `DELETE /api/signals/{fingerprint}` | Cascade delete signal (v0.16.0) | `{deleted: {signals, orders, trades, events}}` |
| `DELETE /api/orders/{order_id}` | Xóa 1 order (v0.16.0) | `{deleted: true}` |
| `DELETE /api/trades/{trade_id}` | Xóa 1 trade (v0.16.0) | `{deleted: true}` |
| `GET /api/data/counts` | Đếm rows per table (v0.16.0) | `{signals: N, orders: N, ...}` |
| `DELETE /api/data/all` | Xóa toàn bộ data (v0.16.0) | `{cleared: [...tables]}` |
| `DELETE /api/data/{table}` | Xóa 1 bảng (v0.16.0) | `{cleared: table_name}` |
| `GET /api/signal-status-counts` | Signal status counts (v0.16.2) | `{executed: N, rejected: N, failed: N, received: N}` |

---

## 🔷 TRANG OVERVIEW

### Stat Cards (V1 + V2)
4 thẻ thống kê chính, hiển thị số liệu real-time:

| Thẻ | Ý Nghĩa | Chi Tiết |
|-----|---------|----------|
| **Net PnL** | Tổng lợi nhuận/lỗ ròng | = Gross PnL − Commission. Xanh = lãi, Đỏ = lỗ. Sub-text hiện Gross PnL và Commission riêng |
| **Win Rate** | Tỷ lệ thắng | = Wins ÷ Total × 100%. Sub-text: "5W / 3L" (số lệnh thắng / thua) |
| **Total Trades** | Tổng số lệnh đã đóng | Chỉ đếm lệnh đã close (có PnL). Sub-text: Average PnL per trade |
| **Active Positions** | Số nhóm vị thế đang mở | Mỗi "group" = 1 symbol + 1 direction từ 1 signal. Sub-text: tổng signals nhận được |

### Equity Curve — Đường Cong Vốn (V1 + V2)
- **Loại biểu đồ**: Area chart (đường + fill gradient)
- **Ý nghĩa**: Hiển thị cumulative PnL theo thời gian — cho thấy xu hướng tổng thể tài khoản đang tăng hay giảm
- **Cách đọc**:
  - Đường đi lên → tài khoản đang lãi
  - Đường đi xuống → tài khoản đang lỗ
  - Gradient xanh (lãi) hoặc đỏ (lỗ) tùy giá trị cuối
- **V2 nâng cao**: Peak annotation (đường nét đứt chỉ đỉnh cao nhất), active dot có glow khi hover
- **Period**: 30D / 90D / 1Y

### Daily PnL — Lãi/Lỗ Theo Ngày (V1 + V2)
- **Loại biểu đồ**: Bar chart (cột đứng)
- **Ý nghĩa**: Mỗi cột = PnL ròng trong 1 ngày. Giúp nhận ra ngày nào lãi, ngày nào lỗ
- **Cách đọc**:
  - Cột xanh = ngày lãi, cột đỏ = ngày lỗ
  - Chiều cao cột = magnitude lãi/lỗ
  - Cột cao liên tục → chiến lược đang hiệu quả
- **V2 nâng cao**: Data label giá trị (`$-0.1`) trực tiếp trên mỗi cột, premium tooltip
- **Period**: 7D / 30D / 90D

### 🆕 Daily PnL + Cumulative Trend — Biểu Đồ Kết Hợp (V2 Only)
- **Loại biểu đồ**: Combo chart (Bar + Line overlay)
- **Ý nghĩa**: Kết hợp 2 chiều data — PnL ngày (bars) VÀ tích lũy (line) trên cùng 1 biểu đồ
- **Cách đọc**:
  - Thanh xanh/đỏ = PnL hàng ngày (trục Y trái)
  - Đường tím = Cumulative PnL (trục Y phải)
  - Nếu đường tím đi lên nhưng cột đỏ xuất hiện → những ngày lỗ nhỏ, không ảnh hưởng trend
  - Nếu đường tím đi xuống dù có cột xanh → lỗ lớn ở ngày khác "ăn mất" lãi
- **Giá trị**: Đây là biểu đồ quan trọng nhất cho trader — thấy cả vi mô (ngày) và vĩ mô (trend) cùng lúc

### 🆕 Win Rate Gauge — Đồng Hồ Tỷ Lệ Thắng (V2 v0.16.1)
- **Loại biểu đồ**: Radial bar chart (vòng cung) + số % ở giữa
- **Ý nghĩa**: Hiển thị trực quan tỷ lệ thắng dạng gauge — nhìn nhanh hơn text
- **Cách đọc**:
  - Vòng cung xanh = % thắng (≥ 50% = xanh, < 50% = đỏ)
  - Số giữa = win rate %
  - Dưới: Wins (xanh) / Losses (đỏ)
- **Style**: Inspired by PLECTO MRR Growth gauge

### 🆕 Signal Breakdown — Phân Loại Tín Hiệu (V2 v0.16.1)
- **Loại**: Table card (không phải biểu đồ — dạng bảng)
- **Ý nghĩa**: Đếm số lượng signal theo từng status
- **Các status**:
  | Type | Icon | Ý nghĩa |
  |------|------|----------|
  | Executed | ✅ | Signal đã tạo được order thành công |
  | Rejected | 🚫 | Signal bị từ chối (entry quá xa, spread cao, ...) |
  | Failed | ❌ | Signal parse thành công nhưng MT5 execution thất bại |
  | Received | 📩 | Signal mới nhận, chưa xử lý |
  | Duplicate | 📋 | Signal trùng lặp (đã có fingerprint) |
  | Active | 🔄 | Signal đang được theo dõi (range/scale_in chưa complete) |
- **Style**: Inspired by PLECTO MRR Breakdown table — mỗi dòng có icon + count badge màu

### 🆕 PnL by Weekday — Lãi/Lỗ Theo Ngày Trong Tuần (V2 v0.16.1)
- **Loại biểu đồ**: Bar chart (5 cột: Mon–Fri)
- **Ý nghĩa**: Tổng hợp PnL theo ngày trong tuần — phát hiện ngày nào thường lãi/lỗ
- **Cách đọc**:
  - Cột xanh = ngày thường lãi, cột đỏ = ngày thường lỗ
  - Data label giá trị trên đầu mỗi cột
  - Ví dụ: Friday thường đỏ → tránh trade chiều thứ 6
- **Ứng dụng**: Time-of-week analysis — quyết định nên trade ngày nào

### 🆕 Chart Toggle — Tùy Chỉnh Biểu Đồ (V2 v0.16.1)
- **Nút "Customize"** ở góc phải header trang Overview
- **Chức năng**: Click → dropdown 9 chart cards, toggle Eye/EyeOff để ẩn/hiện
- **Persistence**: State lưu vào `localStorage` — refresh trang vẫn giữ setting
- **9 chart có thể toggle**:
  1. Equity Curve
  2. Daily PnL + Cumulative
  3. Monthly Wins vs Losses
  4. Win / Loss Ratio
  5. Top Channels
  6. Active Positions
  7. Signal Breakdown
  8. Win Rate Gauge
  9. PnL by Weekday

### Top Channels — Xếp Hạng Channel (V1 + V2)
- **Loại biểu đồ**: Horizontal bar chart
- **Ý nghĩa**: So sánh hiệu suất các channel tín hiệu — channel nào đang kiếm tiền, channel nào lỗ
- **Cách đọc**:
  - Thanh xanh dài = channel có lãi nhiều
  - Thanh đỏ = channel gây lỗ → cân nhắc tắt channel đó
  - V2: giá trị `$X.X` label bên phải mỗi thanh
- **Ứng dụng**: Quyết định giữ / bỏ channel nào dựa trên PnL thực tế

### Win Rate by Symbol (V1 Only)
- **Loại biểu đồ**: Horizontal bar chart
- **Ý nghĩa**: Tỷ lệ thắng của từng symbol (XAUUSD, EURUSD, ...)
- **Cách đọc**:
  - Xanh ≥ 60% → hiệu quả tốt
  - Vàng 45-60% → trung bình
  - Đỏ < 45% → kém → cân nhắc loại trừ symbol
- **V2 thay thế bằng**: WinLossDonut + Symbol Radar (đa chiều hơn)

### Win / Loss Ratio — Donut Chart (V2 Only)
- **Loại biểu đồ**: Donut (vòng tròn rỗng giữa)
- **Ý nghĩa**: Tỷ lệ thắng/thua tổng quan bằng hình ảnh
- **Cách đọc**:
  - Phần xanh = wins, phần đỏ = losses
  - Số giữa = win rate %
  - Legend: "5W (62%) / 3L (38%)"
- **Tương tác V2**: Hover vào sector → expand + glow effect + outer ring indicator + label tên sector

### Recent Trades Table (V1 Only)
- Bảng 8 lệnh giao dịch gần nhất
- Cột: Time, Symbol, Side (BUY/SELL badge), PnL

### Active Positions Table (V1 + V2)
- Danh sách vị thế đang mở (chưa đóng)
- Cột: Symbol, Side, Số ticket, Channel
- Ý nghĩa: Biết hiện tại bot đang giữ những vị thế nào

### 🆕 Monthly Wins vs Losses (V2 Only)
- **Loại biểu đồ**: Grouped bar chart
- **Ý nghĩa**: So sánh tổng $ wins vs tổng $ losses mỗi tháng (tối đa 6 tháng gần nhất)
- **Cách đọc**:
  - Cột xanh = total wins, cột đỏ = total losses
  - Data label giá trị trên đầu mỗi cột
  - Tháng nào cột xanh cao hơn đỏ → tháng đó profitable

---

## 📈 TRANG ANALYTICS (V2 Only)

### Weekly Win vs Loss (Stacked Bar + Line)
- **Loại biểu đồ**: Stacked bar chart + line overlay
- **Ý nghĩa**: Tổng hợp wins vs losses theo TUẦN, kèm net PnL line
- **Cách đọc**:
  - Thanh xanh dưới = tổng $ lãi trong tuần
  - Thanh đỏ trên (stacked) = tổng $ lỗ trong tuần
  - Đường vàng = Net PnL tuần (lãi − lỗ)
  - Nếu thanh đỏ thường xuyên cao hơn xanh → chiến lược có vấn đề
- **Ứng dụng**: Nhìn nhanh xu hướng hiệu suất theo tuần

### PnL Distribution — Phân Phối Lãi/Lỗ
- **Loại biểu đồ**: Histogram (biểu đồ phân phối)
- **Ý nghĩa**: Phân nhóm các ngày giao dịch theo mức PnL ($) — xem PnL phổ biến nhất rơi vào khoảng nào
- **Cách đọc**:
  - Trục X = khoảng PnL (ví dụ: -$100 đến +$100)
  - Trục Y = số ngày rơi vào khoảng đó
  - Data label trên mỗi cột = "3 days"
  - Phân bố lệch phải (dương) → chiến lược tốt
  - Phân bố lệch trái (âm) → cần review lại
  - Đuôi dài bên trái → có những ngày lỗ nặng bất thường
- **Ứng dụng**: Phát hiện phân bố rủi ro — có "fat tail" (lỗ lớn bất ngờ) không?

### Max Drawdown — Sụt Giảm Tối Đa
- **Loại biểu đồ**: Area chart (luôn ≤ 0%)
- **Ý nghĩa**: Đo mức sụt giảm từ đỉnh equity tới hiện tại — chỉ số rủi ro quan trọng nhất
- **Cách đọc**:
  - Trục Y = % giảm từ peak (luôn âm hoặc 0)
  - Đường gần 0% → ổn định, ít rủi ro
  - Đường sâu (ví dụ -20%) → rủi ro lớn, capital bị giảm mạnh
  - Đường nét đứt đỏ = Max drawdown (mức sụt giảm lớn nhất từ trước đến nay)
- **Công thức**: `drawdown = (equity_hiện_tại − peak_equity) / peak_equity × 100%`
- **Ứng dụng**: Investor dùng metric này để đánh giá rủi ro. Max DD > 30% thường không chấp nhận được

### Trading Activity — Hoạt Động Giao Dịch
- **Loại biểu đồ**: Combo (Bar + cumulative Line)
- **Ý nghĩa**: Số lệnh giao dịch mỗi ngày + tổng tích lũy
- **Cách đọc**:
  - Cột xanh = số trades trong ngày
  - Đường cyan = tổng trades tích lũy (đường luôn đi lên)
  - Ngày không có cột → bot không giao dịch (cuối tuần, không có signal)
  - Tần suất cao → bot nhận nhiều signal
- **Ứng dụng**: Đánh giá volume giao dịch, phát hiện ngày bất thường (quá nhiều/quá ít)

### Symbol Win/Loss Comparison — So Sánh Theo Symbol
- **Loại biểu đồ**: Butterfly / Diverging horizontal bar chart
- **Ý nghĩa**: So sánh trực quan số lệnh thắng vs thua cho từng symbol
- **Cách đọc**:
  - Thanh xanh bên phải = số wins của symbol
  - Thanh đỏ bên trái = số losses của symbol
  - Label: "5" (wins), "3" (losses)
  - Symbol có thanh xanh >> đỏ → chiến lược phù hợp symbol đó
  - Symbol có thanh đỏ >> xanh → cân nhắc blacklist symbol
- **Ứng dụng**: Quyết định symbol nào nên trade, symbol nào nên loại bỏ

---

## 📡 TRANG CHANNELS

### Channel Cards (V1 + V2)
- **Mỗi card hiện**: Tên channel, Total PnL (badge xanh/đỏ), Trades, Win Rate, W/L, Avg PnL
- **Win Rate Bar**: Thanh progress bar — phần xanh = % thắng, phần đỏ = % thua
- **Ý nghĩa**: Tổng quan nhanh hiệu suất từng nguồn tín hiệu
- **V2 tương tác**: Click card → highlight + load Daily PnL riêng cho channel đó

### Channel Comparison Chart (V1 + V2)
- **Loại biểu đồ**: Horizontal bar chart
- **Ý nghĩa**: So sánh trực tiếp Total PnL giữa các channel
- **V2 nâng cao**: Data label giá trị bên phải mỗi thanh, premium tooltip

### 🆕 Channel Daily PnL Drill-down (V2 Only)
- **Loại biểu đồ**: Line chart
- **Kích hoạt**: Click vào 1 channel card
- **Ý nghĩa**: PnL 30 ngày gần nhất CHỈ cho channel được chọn
- **Cách đọc**: Đường đi lên = channel đang lãi trong khoảng thời gian gần
- **Ứng dụng**: Phân tích sâu — channel A tổng thể lãi nhưng 30 ngày gần đây có lỗ không?

---

## 💱 TRANG SYMBOLS (V2 Only)

### Symbol Performance Table
- **Cột**: Symbol, Trades, Win Rate (progress bar), Total PnL, Avg PnL, W/L
- **Win Rate visual**: Progress bar mini bên trong ô bảng
- **PnL color**: Xanh = lãi, đỏ = lỗ
- **Ý nghĩa**: Bảng toàn diện hiệu suất từng cặp tiền/chỉ số

### Symbol PnL Ranking
- **Loại biểu đồ**: Horizontal bar chart (labeled)
- **Ý nghĩa**: Xếp hạng symbol theo Total PnL
- **Cách đọc**: Symbol trên cùng = lãi nhiều nhất. Thanh đỏ = symbol gây lỗ
- **Label**: Giá trị `$X.X` bên phải mỗi thanh

### Top 5 Symbol Radar
- **Loại biểu đồ**: Radar chart (hình mạng nhện)
- **Ý nghĩa**: So sánh ĐA CHIỀU 2 tiêu chí cho top 5 symbol:
  - **Win Rate** (xanh): Tỷ lệ thắng (0-100%)
  - **Activity** (xanh dương): Số trades (normalized 0-100)
- **Cách đọc**:
  - Diện tích phủ rộng → symbol vừa có win rate cao vừa trade nhiều → tốt
  - Radar lệch 1 phía → symbol chỉ mạnh 1 mặt
  - XAUUSD phủ rộng hơn EURUSD → XAUUSD hiệu quả toàn diện hơn

---

## 📓 TRANG TRADES — Trade Journal

### Filter Bar (V1 + V2)
| Filter | Ý Nghĩa |
|--------|---------|
| **From / To** | Khoảng thời gian (date picker) |
| **Channel** | Lọc theo channel cụ thể (dropdown) |
| **Symbol** | Lọc theo symbol (text input, ví dụ "XAUUSD") |
| **Outcome** | Win / Loss / All |

### Summary Bar (V1 + V2)
- **Showing**: Tổng số trades khớp filter
- **Total PnL**: Tổng lợi nhuận/lỗ của trades đã filter
- **Avg PnL**: PnL trung bình mỗi trade

### Trade Table (V1 + V2)
| Cột | Ý Nghĩa |
|-----|---------|
| **Close Time** | Thời gian đóng lệnh |
| **Symbol** | Cặp tiền / chỉ số (XAUUSD, EURUSD, ...) |
| **Side** | BUY (badge xanh) hoặc SELL (badge đỏ) |
| **Entry** | Giá vào lệnh |
| **Close** | Giá đóng lệnh |
| **Volume** | Khối lượng (lot) |
| **PnL** | Lợi nhuận/lỗ — xanh = lãi, đỏ = lỗ |
| **Commission** | Phí giao dịch (thường âm) |
| **Channel** | Nguồn tín hiệu |
| **Reason** | Lý do đóng (SL, TP, Manual, Signal Reply) |

### CSV Export (V1 + V2)
- Nhấn nút **📥 CSV** → tải file Excel chứa toàn bộ trades (theo filter hiện tại)
- Dùng để: Phân tích ngoài dashboard, báo cáo thuế, backtest review

### Phân trang
- 50 trades/trang (V1) hoặc 20 trades/trang (V2)
- Nút Prev/Next + số trang

---

## 🔗 TRANG SIGNALS — Signal Lifecycle (V2 v0.16.0)

### Signal Table (Expandable)
- **Mỗi dòng = 1 signal** (grouped by fingerprint)
- **Cột chính**:
  | Cột | Ý Nghĩa |
  |-----|---------|
  | **Time** | Thời gian nhận signal |
  | **Symbol** | Cặp tiền (XAUUSD, ...) |
  | **Side** | BUY (badge xanh) / SELL (badge đỏ) |
  | **Status** | `executed` (xanh) / `rejected` (vàng) / `failed` (đỏ) |
  | **Orders** | Số order thành công / tổng |
  | **PnL** | Tổng PnL (nếu có trades) |
  | **Channel** | Tên channel hoặc ID |
  | **Actions** | 👁 Detail modal, 🗑 Cascade delete |

- **Expand row** (click vào `>`): Hiện danh sách orders con với ticket, type, price, SL/TP
- **Filter bar**: Channel, Symbol, Status, Date range
- **Phân trang**: 20 signals/trang

### Signal Detail Modal (`SignalDetailModal`)
- **Raw Text**: Text gốc từ Telegram
- **Parsed Result**: Symbol, Side, Entry, SL, TP đã parse
- **Timeline**: Ordered events (received → parsed → executed/rejected)
- **Orders**: Table chi tiết orders + trades liên quan
- **Groups**: Signal group info (nếu là range/scale_in)

### Delete Operations
- **Delete Signal**: Cascade xóa signal + ALL orders + trades + events liên quan
- **Delete Order**: Xóa riêng 1 order (có confirm modal)
- **ConfirmModal**: Popup glassmorphism, type-to-confirm cho destructive actions

---

## ⚙️ TRANG SETTINGS (V2 Only)

| Mục | Ý Nghĩa |
|-----|---------|
| **Connection Status** | Hiện trạng kết nối API (● Live = xanh, ● Offline = đỏ) |
| **API Key** | Nhập/thay đổi dashboard API key (bảo mật, gửi qua header `X-API-Key`) |
| **About** | Thông tin version (v0.16.6), tech stack |

---

## 🎨 Design System

### V1
- Dark background (`#0a0e1a`)
- Neon green/red accents
- Chart.js charts, server-rendered
- Basic hover tooltips

### V2
- **Glassmorphism**: Card background `rgba(15,23,42,0.6)` + `backdrop-filter: blur(12px)` + border `rgba(148,163,184,0.08)`
- **Premium Tooltips**: Dark semi-transparent, rounded 10px, monospace font, color-coded values (xanh/đỏ), color dots cho multi-series
- **Donut Interaction**: Hover → sector expand + outer ring + glow effect (`drop-shadow`)
- **Data Labels**: Giá trị hiện trực tiếp trên bars, không cần hover
- **Typography**: Inter (body) + JetBrains Mono (numbers)
- **Animations**: Framer Motion page transitions, Recharts animate 600-1000ms
- **Responsive**: CSS Grid responsive cho desktop + tablet

---

## 🔄 Auto-Refresh

Cả V1 và V2 đều tự động refresh data mỗi **30 giây**:
- V1: `setInterval(refreshAll, 30000)`
- V2: TanStack Query `refetchInterval: 30_000`

Không cần manual refresh — dashboard luôn cập nhật.

---

## 📝 So Sánh V1 vs V2

| Feature | V1 | V2 |
|---------|:--:|:--:|
| Stat cards | ✅ | ✅ |
| Equity curve | ✅ | ✅ + peak annotation |
| Daily PnL bars | ✅ | ✅ + data labels |
| Combo bar + line | ❌ | ✅ |
| Win/Loss donut | ❌ | ✅ + interactive glow |
| Win Rate Gauge | ❌ | ✅ (v0.16.1) |
| Signal Breakdown table | ❌ | ✅ (v0.16.1) |
| PnL by Weekday | ❌ | ✅ (v0.16.1) |
| Chart toggle (Customize) | ❌ | ✅ (v0.16.1) |
| Monthly wins vs losses | ❌ | ✅ |
| Stacked win/loss weekly | ❌ | ✅ |
| PnL distribution histogram | ❌ | ✅ |
| Max drawdown chart | ❌ | ✅ |
| Trading activity combo | ❌ | ✅ |
| Symbol butterfly comparison | ❌ | ✅ |
| Symbol performance table | ❌ | ✅ |
| Symbol radar chart | ❌ | ✅ |
| Channel drill-down line | ❌ | ✅ |
| **Signal Lifecycle page** | ❌ | ✅ (v0.16.0) |
| **Signal detail modal** | ❌ | ✅ (v0.16.0) |
| **Cascade delete** | ❌ | ✅ (v0.16.0) |
| **Confirm modal** | ❌ | ✅ (v0.16.0) |
| Settings page | ❌ | ✅ |
| CSV export | ✅ | ✅ |
| Premium tooltips | ✅ (upgraded) | ✅ |
| Framer Motion transitions | ❌ | ✅ |
| Glassmorphism design | ❌ | ✅ |
