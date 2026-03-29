# 📖 STRATEGY CONFIG GUIDE — telegram-mt5-bot v0.24.0

> **Tài liệu duy nhất** hướng dẫn cấu hình chiến thuật trading của bot.
>
> Mọi biến config, ý nghĩa, xung đột, ví dụ — tất cả ở đây.
>
> Không cần đọc doc nào khác để cấu hình bot.

---

## Mục lục

1. [Tổng Quan Cấu Hình](#1-tổng-quan-cấu-hình)
2. [Vào Lệnh (Entry Strategy)](#2-vào-lệnh-entry-strategy)
3. [Quản Lý Lệnh (Position Management)](#3-quản-lý-lệnh-position-management)
4. [Auto Partial Close — Tự Cắt Volume Khi Lãi](#4-auto-partial-close--tự-cắt-volume-khi-lãi)
5. [Breakeven — Dời SL Về Entry](#5-breakeven--dời-sl-về-entry)
6. [Trailing Stop — SL Đuổi Giá](#6-trailing-stop--sl-đuổi-giá)
7. [Group Management — Quản Lý Nhóm Lệnh](#7-group-management--quản-lý-nhóm-lệnh)
8. [Reply Actions — Điều Khiển Qua Telegram](#8-reply-actions--điều-khiển-qua-telegram)
9. [Risk Management — Quản Lý Vốn](#9-risk-management--quản-lý-vốn)
10. [Safety Gates — Cổng An Toàn](#10-safety-gates--cổng-an-toàn)
11. [Pipeline Guards — Bộ Lọc Thông Minh](#11-pipeline-guards--bộ-lọc-thông-minh)
12. [Xung Đột \& Ưu Tiên](#12-xung-đột--ưu-tiên)
13. [Kịch Bản Ví Dụ](#13-kịch-bản-ví-dụ)
14. [Bảng Tra Cứu Nhanh](#14-bảng-tra-cứu-nhanh)

---

## 1. Tổng Quan Cấu Hình

Bot có **2 nơi** để cấu hình chiến thuật:

| File | Phạm vi | Dùng cho |
|------|---------|----------|
| `.env` | **Global** — áp dụng tất cả channels | Risk, safety gates, lot, execution |
| `config/channels.json` | **Per-channel** — override cho từng channel | Strategy mode, entry, position management |

**Quy tắc ưu tiên**: `channels.json` > `.env`. Nếu channel không có config riêng → dùng `default` section → dùng `.env`.

### Cấu trúc `channels.json`

```json
{
    "default": {
        "name": "Global Defaults",
        "rules": { ... },        // Position management
        "strategy": { ... },     // Entry strategy
        "risk": { ... },         // Risk override (optional)
        "validation": { ... }    // Validation override (optional)
    },
    "channels": {
        "-1001234567890": {
            "name": "Gold Signals",
            "rules": { ... },    // Override rules for this channel
            "strategy": { ... }  // Override strategy for this channel
        }
    }
}
```

> ⚠️ **Thay đổi `channels.json` cần restart bot để apply.**

---

## 2. Vào Lệnh (Entry Strategy)

### 2.1 Strategy Mode — Cách bot tạo lệnh từ signal

| Config | File | Giá trị | Mô tả |
|--------|------|---------|-------|
| `strategy.mode` | channels.json | `"single"` | **Mặc định.** 1 signal = 1 order. Không re-entry. |
| | | `"range"` | 1 signal = N orders chia trên entry_range. Signal phải có range (VD: BUY GOLD 2020-2030). |
| | | `"scale_in"` | 1 signal = N orders cách nhau N pips (stepped). Cần `reentry_step_pips > 0`. |

### 2.2 Entry Config Chi Tiết

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `strategy.max_entries` | channels.json | `1` | Số order tối đa từ 1 signal. Hard cap = 10. |
| `strategy.volume_split` | channels.json | `"equal"` | Cách chia lot cho các entries (xem bảng dưới). |
| `strategy.reentry_step_pips` | channels.json | `0` | Khoảng cách pip giữa P1→P2→P3 (cho `scale_in`). `0` = mode bị disable. |
| `strategy.execute_all_immediately` | channels.json | `false` | `true` → đặt tất cả LIMIT/STOP ngay. `false` → chỉ P1 ngay, P2/P3 chờ RangeMonitor. |
| `strategy.signal_ttl_minutes` | channels.json | `15` | Signal hết hạn sau N phút → remaining levels EXPIRED, ngừng monitor. |
| `strategy.reentry_enabled` | channels.json | `false` | `true` → RangeMonitor quét giá để trigger P2/P3. |
| `MARKET_TOLERANCE_POINTS` | .env | `5.0` | Nếu giá cách entry ≤ N points → đặt MARKET thay vì LIMIT. |
| `PENDING_ORDER_TTL_MINUTES` | .env | `15` | Huỷ pending order (LIMIT/STOP) sau N phút chưa khớp. |

### 2.3 Volume Split — Cách chia lot

Ví dụ: `FIXED_LOT_SIZE=0.06`, `max_entries=3`

| Giá trị | L0 | L1 | L2 | Giải thích |
|---------|----|----|-----|-----------|
| `"equal"` | 0.02 | 0.02 | 0.02 | Chia đều |
| `"pyramid"` | 0.03 | 0.02 | 0.01 | Entry đầu lot lớn nhất, giảm dần |
| `"risk_based"` | Tùy SL | Tùy SL | Tùy SL | Level xa SL → lot lớn hơn (risk/pip thấp hơn) |
| `"per_entry"` | 0.06 | 0.06 | 0.06 | **Mỗi level nhận full lot.** Total = 0.18. |

> ⚠️ `per_entry` = mỗi entry nhận full `FIXED_LOT_SIZE`. Tổng volume = lot × max_entries.

### 2.4 Re-entry Config — Khi nào P2/P3 trigger

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `strategy.reentry_tolerance_pips` | channels.json | `0` | Trigger sớm N pip trước level (thay vì phải cross chính xác). |
| `strategy.max_reentry_distance_pips` | channels.json | `0` | Reject re-entry nếu giá đã trôi quá N pip khỏi level. `0` = disabled. |

**Ví dụ XAUUSD** (pip = $0.1):  
- P2 level = 3342, `reentry_tolerance_pips=5` ($0.50)
- Trigger khi giá lên 3341.5 thay vì phải 3342
- `max_reentry_distance_pips=10` ($1.00): nếu giá đã 3343 → reject (quá xa)

---

## 3. Quản Lý Lệnh (Position Management)

Bot quản lý lệnh đang mở qua **background loop** mỗi N giây.

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `POSITION_MANAGER_POLL_SECONDS` | .env | `5` | Chu kỳ quét (giây). Giảm = phản ứng nhanh hơn, tăng load. |

### Thứ tự xử lý mỗi cycle

```
Mỗi N giây:
  1. Lấy tất cả positions + pending orders từ MT5
  2. Lọc chỉ lệnh có magic number của bot
  3. Nếu position thuộc group → _manage_group()
  4. Nếu position KHÔNG thuộc group → _manage_individual()
     a. Breakeven check
     b. Trailing stop check
     c. Partial close check (pips mode HOẶC percent mode)
```

> **Quan trọng:** Khi `group_trailing_pips > 0`, group positions KHÔNG chạy individual management (breakeven, trailing_stop_pips riêng). Group có logic riêng.

---

## 4. Auto Partial Close — Tự Cắt Volume Khi Lãi

Tự động đóng **một phần volume cố định** khi profit đạt N pips. Phần còn lại tiếp tục chạy với TP gốc + trailing SL bảo vệ.

### Có 2 mode partial close:

| Mode | ENV/Config | Trigger | Đóng bao nhiêu | Khi nào dùng |
|------|-----------|---------|----------------|-------------|
| **Pips Mode** (v0.24.0) | `PARTIAL_CLOSE_TRIGGER_PIPS` + `PARTIAL_CLOSE_LOT` | Profit ≥ N pips | Lot cố định (VD: 0.02) | Muốn control chính xác lot đóng/giữ |
| **Percent Mode** (legacy) | `PARTIAL_CLOSE_PERCENT` | Giá gần TP1 | % của volume | Muốn đóng theo tỷ lệ |

> ⚠️ **Khi cả 2 mode đều set > 0**: Pips mode **ưu tiên**, Percent mode bị skip.

### 4.1 Pips Mode — Config chi tiết

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `PARTIAL_CLOSE_TRIGGER_PIPS` | .env | `0` | Lãi bao nhiêu pips → trigger partial close. `0` = disabled. |
| `PARTIAL_CLOSE_LOT` | .env | `0` | Lot cố định để đóng. Phải < volume hiện tại. |

**Kịch bản:**
```
Config: FIXED_LOT_SIZE=0.03, PARTIAL_CLOSE_TRIGGER_PIPS=30, PARTIAL_CLOSE_LOT=0.02

Mở lệnh: BUY XAUUSD 0.03 lot tại 3340
Giá lên 3343 (+30 pips):
  → Đóng 0.02 lot → chốt lãi
  → Còn 0.01 lot tiếp tục chạy
  → TP giữ nguyên (nếu có)
  → SL giữ nguyên
  → Trailing SL bảo vệ phần còn lại
  → ✂️ Telegram alert: "Auto Partial Close 0.02 lot at +30.0p"
```

**Bảo vệ:**
- Mỗi ticket chỉ trigger **1 lần**
- Nếu `PARTIAL_CLOSE_LOT >= pos.volume` → log warning + skip (không đóng hết)
- Volume được snap theo `volume_step` của symbol (VD: 0.01)

### 4.2 Percent Mode (Legacy)

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `PARTIAL_CLOSE_PERCENT` | .env / channels.json | `0` | % volume đóng khi giá chạm vùng TP1. `0` = disabled. |

---

## 5. Breakeven — Dời SL Về Entry

Tự động chuyển SL về mức entry + lock pips khi profit đạt ngưỡng. Bảo vệ vốn + khóa lãi nhỏ.

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `breakeven_trigger_pips` | channels.json (`rules`) | `0` | Profit bao nhiêu pip → trigger breakeven. `0` = disabled. |
| `breakeven_lock_pips` | channels.json (`rules`) | `2` | SL = entry ± lock pips (lock vào vùng lãi). |
| `BREAKEVEN_TRIGGER_PIPS` | .env | `0` | Global default (dùng khi channels.json không set). |
| `BREAKEVEN_LOCK_PIPS` | .env | `2` | Global default. |

**Kịch bản:**
```
Config: breakeven_trigger_pips=50, breakeven_lock_pips=30

BUY XAUUSD entry 3340, SL gốc 3330
Giá lên 3345 (+50 pips):
  → SL dịch từ 3330 → 3343 (entry + 30 pips × $0.1 = 3340 + $3 = 3343)
  → ✅ Đã khóa $3 profit cho dù giá quay đầu
```

**Lưu ý:**
- Chỉ trigger **1 lần** — không reset
- BUY: SL = entry + lock × pip_size (dịch lên)
- SELL: SL = entry - lock × pip_size (dịch xuống)

---

## 6. Trailing Stop — SL Đuổi Giá

SL tự động bám theo giá thuận lợi, giữ khoảng cách cố định. Chỉ dịch **1 chiều** (theo hướng lãi), không bao giờ dịch ngược.

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `trailing_stop_pips` | channels.json (`rules`) | `0` | Khoảng cách trail (pips). `0` = disabled. |
| `TRAILING_STOP_PIPS` | .env | `0` | Global default. |

**Kịch bản:**
```
Config: trailing_stop_pips=40

SELL XAUUSD entry 3340, SL gốc 3352
Giá xuống 3330:
  → new_sl = 3330 + 40 × $0.1 = 3334
  → 3334 < 3352 → DỊCH SL → 3334

Giá xuống 3310:
  → new_sl = 3310 + $4 = 3314
  → 3314 < 3334 → DỊCH SL → 3314

Giá lên 3315:
  → new_sl = 3315 + $4 = 3319
  → 3319 > 3314 → KHÔNG DỊCH (chỉ dịch thuận)

Giá lên 3314 → SL trigger → ĐÓNG
```

**Lưu ý:**
- Alert chỉ gửi khi SL dịch ≥ 10 pips (tránh spam)
- Throttle 60s per ticket

---

## 7. Group Management — Quản Lý Nhóm Lệnh

Khi bot tạo nhiều orders từ 1 signal (range/scale_in), tất cả được gom thành 1 **group**. Group có logic riêng.

### 7.1 Group Trailing SL

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `group_trailing_pips` | channels.json (`strategy`) | `0` | Trail SL **cả nhóm** theo giá. `0` = dùng individual trailing. |
| `group_be_on_partial_close` | channels.json (`strategy`) | `true` | Auto BE lệnh còn lại khi đóng 1 lệnh trong group. |

> ⚠️ **Khi `group_trailing_pips > 0`**: `breakeven_trigger/lock_pips` và `trailing_stop_pips` **BỊ BỎ QUA** cho nhóm đó. Group trailing thay thế toàn bộ.

**Kịch bản:**
```
Config: group_trailing_pips=50 (XAUUSD = $5.00)

SELL entries: P1=3340, P2=3342, P3=3344. SL gốc = 3352.

Giá xuống 3335:
  → Group SL = 3335 + $5 = 3340. 3340 < 3352 → DỊCH
  → CẢ 3 LỆNH: SL = 3340

Giá xuống 3310:
  → SL = 3310 + $5 = 3315.
  → CẢ 3 LỆNH: SL = 3315

Giá quay lên 3315 → 💥 SL HIT → ĐÓNG CẢ 3
  P1: +$25, P2: +$27, P3: +$29
```

### 7.2 SL Mode — Nguồn SL cho group

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `sl_mode` | channels.json (`rules`) | `"signal"` | Dùng SL từ signal gốc |
| | | `"zone"` | SL tính từ zone bounds |
| | | `"fixed"` | SL cố định (dùng `sl_max_pips_from_zone`) |

### 7.3 Reply Close Strategy

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `reply_close_strategy` | channels.json (`rules`) | `"highest_entry"` | Khi reply "close" → đóng lệnh nào? |
| | | `"highest_entry"` | SELL: đóng lowest entry (worst), BUY: đóng highest entry (worst) |
| | | `"lowest_entry"` | Ngược lại |
| | | `"oldest"` | Đóng lệnh cũ nhất |

---

## 8. Reply Actions — Điều Khiển Qua Telegram

Reply vào signal message gốc trên Telegram để điều khiển lệnh.

| Reply text | Action | Mô tả |
|-----------|--------|-------|
| `close`, `exit`, `đóng` | CLOSE | Đóng lệnh (group: theo `reply_close_strategy`) |
| `be`, `breakeven`, `hòa vốn` | BREAKEVEN | Dời SL về entry ± lock_pips |
| `+30`, `+50 pip`, `+120 pips` | SECURE_PROFIT | Đóng worst entry + BE rest |
| `sl 3340` | MODIFY_SL | Đổi SL sang giá cụ thể |
| `tp 3360` | MODIFY_TP | Đổi TP sang giá cụ thể |
| `cancel`, `hủy`, `miss`, `skip` | CANCEL | Huỷ pending orders + re-entry plans |
| `close 50%` | PARTIAL_CLOSE | Đóng 50% volume |

### Reply config

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `secure_profit_action` | channels.json (`rules`) | `"close_worst_be_rest"` | Action của `+N pip`: đóng worst entry + BE rest |
| `reply_be_lock_pips` | channels.json (`rules`) | `1` | Reply "be" → SL = entry ± N pip (không exact entry) |

**Kịch bản `+30` (SECURE_PROFIT):**
```
Config: secure_profit_action="close_worst_be_rest", reply_be_lock_pips=10

SELL group: P1=3340 (worst), P2=3342, P3=3344
Admin reply "+30":
  → ĐÓNG P1 (entry thấp nhất = ít lãi nhất cho SELL)
  → BE cho P2, P3:
    Floor SL = P1 entry - lock = 3340 - $1 = 3339
    P2 SL = 3339, P3 SL = 3339
  → ⚠️ Guard: nếu trailing đã set SL tốt hơn (VD 3325) → giữ 3325
```

---

## 9. Risk Management — Quản Lý Vốn

### 9.1 Lot Size

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `RISK_MODE` | .env | `FIXED_LOT` | `FIXED_LOT` = lot cố định. `RISK_PERCENT` = tính theo % balance. |
| `FIXED_LOT_SIZE` | .env | `0.01` | Lot cố định per order (trước split). |
| `RISK_PERCENT` | .env | `0.05` | % balance per trade (dùng cho mode RISK_PERCENT). 0.05 = 5%. |
| `LOT_MIN` | .env | `0.01` | Lot tối thiểu. |
| `LOT_MAX` | .env | `100.0` | Lot tối đa. |
| `LOT_STEP` | .env | `0.01` | Bước lot (snap). |

**Per-channel override** (trong channels.json):
```json
"risk": {
    "mode": "FIXED_LOT",
    "fixed_lot_size": 0.05
}
```

### 9.2 Daily Risk Guard — Phòng Vệ Cháy Tài Khoản

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `MAX_DAILY_TRADES` | .env | `0` | Max trades/ngày. `0` = unlimited. Mỗi re-entry cũng đếm. |
| `MAX_DAILY_LOSS` | .env | `0` | Max loss USD/ngày. Vượt → tạm dừng trading. |
| `MAX_CONSECUTIVE_LOSSES` | .env | `0` | Chuỗi thua liên tiếp → tạm dừng. |
| `DAILY_RISK_POLL_MINUTES` | .env | `5` | Chu kỳ quét deal history (phút). |

### 9.3 Exposure Guard — Chống Tập Trung Rủi Ro

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `MAX_SAME_SYMBOL_TRADES` | .env | `0` | Max positions cùng 1 symbol. `0` = unlimited. |
| `MAX_CORRELATED_TRADES` | .env | `0` | Max positions trong 1 nhóm tương quan. |
| `CORRELATION_GROUPS` | .env | (rỗng) | Định nghĩa nhóm: `XAUUSD:XAGUSD,EURUSD:GBPUSD` |

---

## 10. Safety Gates — Cổng An Toàn

Chặn signal trước khi vào lệnh.

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `MAX_SPREAD_PIPS` | .env | `5.0` | Reject signal khi spread > N pips. |
| `MAX_OPEN_TRADES` | .env | `5` | Reject signal khi đã có N positions mở. Re-entry cũng đếm. |
| `MAX_ENTRY_DISTANCE_PIPS` | .env | `50.0` | Reject nếu entry xa giá hiện tại > N pips. |
| `MAX_ENTRY_DRIFT_PIPS` | .env | `10.0` | Reject MARKET order nếu giá đã trôi > N pips so với signal entry. |
| `SIGNAL_AGE_TTL_SECONDS` | .env | `60` | Reject signal cũ hơn N giây. |
| `CIRCUIT_BREAKER_THRESHOLD` | .env | `3` | Sau N lần execute fail → dừng trading. |
| `CIRCUIT_BREAKER_COOLDOWN` | .env | `300` | Chờ N giây rồi thử lại. |

**Per-channel override** (trong channels.json):
```json
"validation": {
    "max_entry_distance_pips": 100,
    "max_entry_drift_pips": 20,
    "max_spread_pips": 10
}
```

---

## 11. Pipeline Guards — Bộ Lọc Thông Minh

Guards chạy bên trong pipeline, áp dụng thêm logic thông minh cho từng order.

| Config | File | Default | Mô tả |
|--------|------|---------|-------|
| `strategy.min_sl_distance_pips` | channels.json | `0` | Skip order nếu giá quá gần SL (< N pips). |
| `strategy.default_sl_pips_from_zone` | channels.json | `0` | Tự tạo SL từ zone nếu signal không có SL. SELL: zone_high + N. BUY: zone_low - N. |
| `strategy.max_sl_distance_pips` | channels.json | `0` | Cap SL nếu quá xa entry. Thay bằng `default_sl_pips_from_zone`. |
| `strategy.sl_buffer_pips` | channels.json | `0` | Nới rộng SL thêm N pips tránh spike (BUY: SL thấp hơn, SELL: SL cao hơn). |
| `strategy.max_reentry_distance_pips` | channels.json | `0` | Skip re-entry nếu giá quá xa level. |
| `order_types_allowed` | channels.json (`rules`) | `["MARKET","LIMIT","STOP"]` | Loại order cho phép. Loại STOP → fallback MARKET/LIMIT. |

---

## 12. Xung Đột & Ưu Tiên

### 12.1 Partial Close: 2 mode xung đột

| Tình huống | Kết quả |
|-----------|---------|
| `PARTIAL_CLOSE_TRIGGER_PIPS > 0` + `PARTIAL_CLOSE_LOT > 0` | ✅ **Pips mode chạy**, Percent mode bị skip |
| `PARTIAL_CLOSE_TRIGGER_PIPS = 0` + `PARTIAL_CLOSE_PERCENT > 0` | ✅ Percent mode chạy |
| Cả 2 đều = 0 | ❌ Không partial close |

### 12.2 Group vs Individual

| Tình huống | Kết quả |
|-----------|---------|
| `group_trailing_pips > 0` + position thuộc group | `_manage_group()` chạy. `breakeven_trigger`, `trailing_stop_pips` **BỊ SKIP** |
| `group_trailing_pips = 0` + position thuộc group | `_manage_individual()` chạy. Breakeven + trailing + partial close riêng từng lệnh |
| Position KHÔNG thuộc group | Luôn `_manage_individual()` |

### 12.3 SL Override Guards

| Tình huống | Kết quả |
|-----------|---------|
| Reply "be" nhưng SL hiện tại đã tốt hơn | Guard giữ SL cũ, **KHÔNG ghi đè** |
| Reply "+30" nhưng trailing đã set SL tốt hơn | Guard giữ SL cũ, **KHÔNG ghi đè** |
| `max_sl_distance_pips` + `sl_buffer_pips` | `max_sl_distance_pips` áp dụng TRƯỚC, rồi `sl_buffer_pips` nới thêm |

### 12.4 Pipeline Guard Order

```
Signal → Parse → Dedup → Safety Gates → Validate
                                         ↓
                  ┌──────────────────────────────────────┐
                  │ Pipeline Guards (theo thứ tự):       │
                  │ 1. max_sl_distance_pips (cap SL)     │
                  │ 2. sl_buffer_pips (nới SL)           │
                  │ 3. default_sl_pips_from_zone (tạo SL)│
                  │ 4. min_sl_distance_pips (skip order) │
                  │ 5. Entry drift guard                 │
                  └──────────────────────────────────────┘
                                         ↓
                                      Execute
```

---

## 13. Kịch Bản Ví Dụ

### 13.1 Scalping Nhẹ — Lot Nhỏ, Auto Cắt Lãi

**Mục tiêu:** Vào 1 lệnh, lãi 30 pips tự cắt 2/3, phần còn lại trailing bảo vệ.

```env
# .env
FIXED_LOT_SIZE=0.03
PARTIAL_CLOSE_TRIGGER_PIPS=30
PARTIAL_CLOSE_LOT=0.02
TRAILING_STOP_PIPS=20
BREAKEVEN_TRIGGER_PIPS=0            # không cần, trailing lo
```

```json
// channels.json
{
    "default": {
        "strategy": { "mode": "single" },
        "rules": {
            "trailing_stop_pips": 20,
            "partial_close_percent": 0
        }
    }
}
```

**Luồng:**
1. Signal → mở 0.03 lot
2. +30 pips → auto đóng 0.02, còn 0.01
3. Trailing 20 pips bảo vệ 0.01 lot
4. TP gốc vẫn giữ → nếu giá chạm TP → đóng nốt
5. Nếu giá quay → SL trailing → đóng tại SL

---

### 13.2 Swing Trade — Multi-Entry + Group Trailing

**Mục tiêu:** 3 entries cách nhau $2 (XAUUSD), group trailing $5, mỗi entry 0.01 lot.

```env
# .env
FIXED_LOT_SIZE=0.01
PARTIAL_CLOSE_TRIGGER_PIPS=0        # không dùng auto partial close
```

```json
// channels.json — Noval channel
{
    "channels": {
        "-1002044139064": {
            "name": "Noval channel",
            "rules": {
                "breakeven_trigger_pips": 50,
                "breakeven_lock_pips": 30,
                "trailing_stop_pips": 40,
                "secure_profit_action": "close_worst_be_rest",
                "reply_be_lock_pips": 10
            },
            "strategy": {
                "mode": "range",
                "max_entries": 3,
                "reentry_step_pips": 20,
                "volume_split": "per_entry",
                "signal_ttl_minutes": 30,
                "min_sl_distance_pips": 20,
                "default_sl_pips_from_zone": 55,
                "reentry_tolerance_pips": 5,
                "max_reentry_distance_pips": 10,
                "sl_buffer_pips": 5,
                "max_sl_distance_pips": 100,
                "group_trailing_pips": 50
            }
        }
    }
}
```

**Luồng:**
1. SELL XAUUSD 3340: P1=3340 (MARKET), P2=3342 (chờ), P3=3344 (chờ)
2. Giá lên 3342 → RangeMonitor trigger P2
3. Giá lên 3344 → trigger P3
4. Group trailing: SL = giá + $5 cho cả 3 lệnh
5. Admin reply "+30" → đóng P1 (worst) + BE P2, P3
6. Trailing tiếp tục bảo vệ

---

### 13.3 Conservative — Single Entry + Breakeven Only

**Mục tiêu:** 1 lệnh, breakeven bảo vệ, không trailing, không partial close.

```env
# .env
FIXED_LOT_SIZE=0.01
BREAKEVEN_TRIGGER_PIPS=30
BREAKEVEN_LOCK_PIPS=5
TRAILING_STOP_PIPS=0
PARTIAL_CLOSE_TRIGGER_PIPS=0
MAX_DAILY_LOSS=50.0
MAX_CONSECUTIVE_LOSSES=3
```

**Luồng:**
1. Signal → mở 0.01 lot
2. +30 pips → SL dời về entry + $0.5 (lock 5 pips)
3. Giá chạm TP → đóng lãi. Giá quay → SL ở breakeven → hòa vốn + $0.5

---

### 13.4 Auto Cắt + Trailing Combo

**Mục tiêu:** Vào 0.05 lot, +20 pips cắt 0.03, còn 0.02 trailing 15 pips.

```env
# .env
FIXED_LOT_SIZE=0.05
PARTIAL_CLOSE_TRIGGER_PIPS=20
PARTIAL_CLOSE_LOT=0.03
TRAILING_STOP_PIPS=15
BREAKEVEN_TRIGGER_PIPS=10
BREAKEVEN_LOCK_PIPS=3
```

**Luồng:**
1. Signal → mở 0.05 lot
2. +10 pips → breakeven: SL = entry + 3 pips  
3. +20 pips → auto đóng 0.03, còn 0.02
4. Trailing 15 pips bắt đầu bảo vệ 0.02 lot
5. Giá tiếp tục chạy → trailing đuổi theo → maximize profit

---

## 14. Bảng Tra Cứu Nhanh

### Tôi muốn... → Config cần đổi

| Tôi muốn... | Config | File |
|-------------|--------|------|
| 1 signal = 1 order | `strategy.mode: "single"` | channels.json |
| 1 signal = nhiều order từ range | `strategy.mode: "range"`, `max_entries: 3` | channels.json |
| Tự mua thêm khi giá giảm (scale-in) | `strategy.mode: "scale_in"`, `reentry_step_pips: 20` | channels.json |
| Mỗi entry nhận full lot | `strategy.volume_split: "per_entry"` | channels.json |
| Lot đầu lớn, sau nhỏ dần | `strategy.volume_split: "pyramid"` | channels.json |
| **Tự đóng 0.02 lot khi lãi 30 pips** | `PARTIAL_CLOSE_TRIGGER_PIPS=30`, `PARTIAL_CLOSE_LOT=0.02` | .env |
| Dời SL về entry khi có lãi | `breakeven_trigger_pips: 50` | channels.json |
| SL tự đuổi giá | `trailing_stop_pips: 40` | channels.json |
| Trail SL cả nhóm order | `strategy.group_trailing_pips: 50` | channels.json |
| Tự tạo SL khi signal không có | `strategy.default_sl_pips_from_zone: 30` | channels.json |
| Nới SL thêm vài pips tránh spike | `strategy.sl_buffer_pips: 3` | channels.json |
| Chặn SL quá xa | `strategy.max_sl_distance_pips: 100` | channels.json |
| Reply +pip đóng worst + BE rest | `rules.secure_profit_action: "close_worst_be_rest"` | channels.json |
| Dừng sau 3 lần thua liên tiếp | `MAX_CONSECUTIVE_LOSSES=3` | .env |
| Dừng sau $100 loss/ngày | `MAX_DAILY_LOSS=100.0` | .env |
| Chỉ cho 2 GOLD order mở | `MAX_SAME_SYMBOL_TRADES=2` | .env |
| Test không vào lệnh thật | `DRY_RUN=true` | .env |
| Xem debug signal trên Telegram | `DEBUG_SIGNAL_DECISION=true` | .env |
| Đổi lot size cho 1 channel | `risk.fixed_lot_size: 0.05` | channels.json |

---

> 📌 **Bookmark doc này.** Mỗi khi cần đổi config → ra đây tra. Không cần mở doc nào khác.
