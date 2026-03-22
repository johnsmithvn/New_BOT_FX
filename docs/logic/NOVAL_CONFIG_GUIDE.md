# Noval Channel Config Guide

Ví dụ xuyên suốt: **SELL XAUUSD zone 3340-3347, SL 3352, TP 3300**

> Gold pip_size = $0.1. Ví dụ: 50 pip = $5.00

---

## Config hiện tại

```json
{
    "rules": {
        "breakeven_trigger_pips": 50,
        "breakeven_lock_pips": 30,
        "trailing_stop_pips": 40,
        "partial_close_percent": 0,
        "secure_profit_action": "close_worst_be_rest",
        "reply_be_lock_pips": 10
    },
    "strategy": {
        "mode": "range",
        "max_entries": 3,
        "reentry_enabled": true,
        "execute_all_immediately": false,
        "signal_ttl_minutes": 30,
        "volume_split": "per_entry",
        "min_sl_distance_pips": 20,
        "default_sl_pips_from_zone": 50,
        "reentry_tolerance_pips": 5,
        "max_reentry_distance_pips": 10,
        "reentry_step_pips": 20,
        "group_trailing_pips": 50,
        "reply_close_strategy": "highest_entry",
        "group_be_on_partial_close": true
    }
}
```

---

## PHASE 1 — Vào lệnh

| Config | Giá trị | Tác dụng |
|--------|---------|----------|
| `mode: "range"` | | Chia zone thành nhiều entry |
| `max_entries: 3` | | 3 lệnh: P1, P2, P3 |
| `reentry_step_pips: 20` | $2.00 | Khoảng cách giữa các entry |
| `volume_split: "per_entry"` | | Mỗi lệnh 0.01 lot (không chia nhỏ) |
| `execute_all_immediately: false` | | Chỉ P1 MARKET, P2/P3 chờ |

```
P1 = 3340 (zone_low)    → MARKET ngay    → 0.01 lot
P2 = 3342 (+$2 từ P1)   → PENDING chờ    → 0.01 lot
P3 = 3344 (+$2 từ P2)   → PENDING chờ    → 0.01 lot
```

---

## PHASE 2 — Chờ P2/P3 trigger

| Config | Giá trị | Tác dụng |
|--------|---------|----------|
| `reentry_enabled: true` | | RangeMonitor quét giá mỗi 10s |
| `signal_ttl_minutes: 30` | | P2/P3 hết hạn sau 30 phút |
| `reentry_tolerance_pips: 5` | $0.50 | Trigger sớm $0.50 trước level |
| `max_reentry_distance_pips: 10` | $1.00 | Reject nếu giá trôi quá $1 khỏi level |
| `min_sl_distance_pips: 20` | $2.00 | Reject nếu giá quá gần SL |

```
Giá lên 3342:
  Effective level P2 = 3342 - $0.50 = 3341.5
  3342 ≥ 3341.5 → TRIGGER P2 ✅
  |3342 - 3342| = 0 pip ≤ 10 (max distance) → OK ✅
  |3342 - 3352| = 100 pip ≥ 20 (min SL dist) → OK ✅
  → P2 VÀO LỆNH MARKET ✅
```

---

## PHASE 3 — Quản lý lệnh đang chạy

| Config | Giá trị | Tác dụng |
|--------|---------|----------|
| `group_trailing_pips: 50` | $5.00 | Trail SL cả group, cách giá $5 |
| `breakeven_trigger/lock` | | ⚠️ **BỊ SKIP** khi group_trailing > 0 |
| `trailing_stop_pips: 40` | | ⚠️ **BỊ SKIP** khi group_trailing > 0 |

> **Quan trọng:** `group_trailing_pips > 0` → code dùng `_manage_group()`. 
> `breakeven` và `trailing_stop_pips` chỉ chạy khi `group_trailing_pips = 0`.

```
SELL entry P1=3340, P2=3342, P3=3344. SL gốc = 3352.

        3352 ── SL gốc (vùng lỗ)
        3344 ── P3
        3342 ── P2
        3340 ── P1 entry
giá →   3335

Group trail: SL = 3335 + $5 = 3340
3340 < 3352 → DỊCH ✅. Cả 3 lệnh: SL = 3340

giá →   3320
SL = 3320 + $5 = 3325. 3325 < 3340 → DỊCH ✅. SL = 3325

giá →   3310
SL = 3310 + $5 = 3315. DỊCH ✅. SL = 3315

Giá quay lên 3315 → 💥 SL TRIGGER → ĐÓNG CẢ 3 LỆNH
  P1: 3340-3315 = $25 profit
  P2: 3342-3315 = $27 profit
  P3: 3344-3315 = $29 profit
```

**SL chỉ dịch thuận lợi (SELL = xuống). Không bao giờ dịch ngược.**

---

## PHASE 4a — Reply "close"

| Config | Giá trị | Tác dụng |
|--------|---------|----------|
| `reply_close_strategy: "highest_entry"` | | Đóng lệnh **TỆ nhất** (auto detect BUY/SELL) |
| `group_be_on_partial_close: true` | | Auto BE lệnh còn lại |

```
"highest_entry" cho SELL → SELL worst = LOWEST entry = P1 (3340)
→ ĐÓNG P1 (bán rẻ nhất = ít lãi nhất)
→ BE cho P2, P3: SL = max(remaining entries) = 3344
```

---

## PHASE 4b — Reply "+30"

| Config | Giá trị | Tác dụng |
|--------|---------|----------|
| `secure_profit_action: "close_worst_be_rest"` | | Đóng worst + BE rest |
| `reply_be_lock_pips: 10` | $1.00 | Lock $1 profit khi BE |

```
SELL → worst = P1 (3340) → ĐÓNG P1
Remaining: P2 (3342), P3 (3344)
Floor SL = P1 entry - lock = 3340 - $1 = 3339
→ P2 SL = 3339, P3 SL = 3339

⚠️ Guard: nếu group trailing đã set SL tốt hơn (vd 3325) → giữ 3325
```

---

## PHASE 4c — Reply "be"

| Config | Giá trị | Tác dụng |
|--------|---------|----------|
| `reply_be_lock_pips: 10` | $1.00 | Dời SL vào vùng lãi $1 |

```
P1: SL = 3340 - $1 = 3339
P2: SL = 3342 - $1 = 3341
P3: SL = 3344 - $1 = 3343

⚠️ Guard: nếu SL hiện tại đã tốt hơn → KHÔNG ghi đè
```

---

## Tổng hợp: mỗi biến làm gì

### Strategy (vào lệnh + re-entry)

| Biến | Mặc định | Mục đích |
|------|----------|----------|
| `mode` | `"single"` | `"range"` = nhiều entry |
| `max_entries` | `1` | Số lệnh tối đa |
| `reentry_step_pips` | `0` | Khoảng cách giữa P1→P2→P3 |
| `volume_split` | `"equal"` | `"per_entry"` = mỗi lệnh full lot |
| `execute_all_immediately` | `false` | `true` = vào tất cả ngay |
| `reentry_enabled` | `false` | `true` = RangeMonitor quét P2/P3 |
| `signal_ttl_minutes` | `15` | Hết hạn pending plans |
| `reentry_tolerance_pips` | `0` | Trigger sớm N pip |
| `max_reentry_distance_pips` | `0` | Reject nếu giá trôi quá xa |
| `min_sl_distance_pips` | `0` | Reject nếu giá quá gần SL |
| `default_sl_pips_from_zone` | `0` | Tự tạo SL nếu signal không có |
| `group_trailing_pips` | `0` | Trail SL cả group (`0` = trail riêng) |
| `reply_close_strategy` | `"all"` | `"highest_entry"` = đóng worst |
| `group_be_on_partial_close` | `false` | Auto BE sau đóng 1 lệnh |

### Rules (quản lý lệnh)

| Biến | Mặc định | Mục đích |
|------|----------|----------|
| `breakeven_trigger_pips` | `0` | Auto BE khi profit ≥ N pip |
| `breakeven_lock_pips` | `0` | Lock N pip profit khi auto BE |
| `trailing_stop_pips` | `0` | Trail SL riêng từng lệnh |
| `partial_close_percent` | `0` | Auto đóng N% khi profit |
| `secure_profit_action` | `""` | Reply "+N": `"close_worst_be_rest"` |
| `reply_be_lock_pips` | `1` | Lock N pip khi reply "be" |

### Xung đột cần nhớ

| Tình huống | Kết quả |
|-----------|---------|
| `group_trailing > 0` | `breakeven_trigger/lock` + `trailing_stop_pips` **BỊ SKIP** |
| `group_trailing = 0` | Dùng `breakeven` + `trailing_stop_pips` riêng từng lệnh |
| Reply "be" sau auto BE | Guard giữ SL tốt hơn, **KHÔNG ghi đè** |
| Reply "+30" sau trailing | Guard giữ SL tốt hơn, **KHÔNG ghi đè** |
