# 🔍 Luồng Bot Chi Tiết — Với Config Hiện Tại

> File này vẽ **chính xác** luồng bot sẽ chạy với config `.env` + `channels.json` hiện tại.
>
> Mỗi channel có 1 section riêng, paste config thật + trace từng bước.

---

## Mục lục

1. [Config Chung (.env) — Áp dụng TẤT CẢ channels](#1-config-chung-env)
2. [Channel A: @shushutest1101 — Default Config](#2-channel-a-shushutest1101--default-config)
3. [Channel B: Noval (-1002044139064) — Custom Config](#3-channel-b-noval--1002044139064--custom-config)
4. [Background Tasks — Chạy Song Song Cho Mọi Channel](#4-background-tasks)

---

## 1. Config Chung (.env)

Áp dụng **tất cả channels** trừ khi channel có override.

```ini
# ── Chế độ chạy ──
DRY_RUN=false                          # ⚡ LIVE — lệnh thật
DEBUG_SIGNAL_DECISION=true             # 📩 Gửi debug message mỗi signal về TG admin

# ── Lot & Risk ──
RISK_MODE=FIXED_LOT                    # Lot cố định
FIXED_LOT_SIZE=0.01                    # 0.01 lot per order
LOT_MIN=0.01 / LOT_MAX=100 / LOT_STEP=0.01

# ── Safety Gates ──
MAX_SPREAD_PIPS=7.0                    # Reject signal nếu spread > 7 pips
MAX_OPEN_TRADES=10                     # Reject nếu đã có 10 positions
MAX_ENTRY_DISTANCE_PIPS=200.0          # Reject nếu entry xa giá > 200 pips
MAX_ENTRY_DRIFT_PIPS=10.0              # Reject MARKET nếu giá trôi > 10 pips vs signal
SIGNAL_AGE_TTL_SECONDS=60              # Reject signal cũ > 60s
PENDING_ORDER_TTL_MINUTES=5            # Auto hủy LIMIT/STOP sau 5 phút

# ── Execution ──
MARKET_TOLERANCE_POINTS=30.0           # |entry - price| ≤ 30 points → MARKET (XAUUSD: $0.30)
DEVIATION_POINTS=20                    # Max slippage cho MARKET
ORDER_MAX_RETRIES=3                    # Retry 3 lần nếu execute fail
CIRCUIT_BREAKER_THRESHOLD=999          # Gần như disabled (999 lần fail mới dừng)
SYMBOL_SUFFIX=m                        # XAUUSD → XAUUSDm (Exness)

# ── Position Manager (Global defaults) ──
BREAKEVEN_TRIGGER_PIPS=0.0             # ❌ Disabled globally
TRAILING_STOP_PIPS=0.0                 # ❌ Disabled globally
PARTIAL_CLOSE_PERCENT=0                # ❌ Disabled globally
PARTIAL_CLOSE_TRIGGER_PIPS=0.0         # ❌ Disabled globally
PARTIAL_CLOSE_LOT=0.0                  # ❌ Disabled globally
POSITION_MANAGER_POLL_SECONDS=3        # Quét mỗi 3 giây

# ── Exposure Guard ──
MAX_SAME_SYMBOL_TRADES=0               # ❌ Unlimited
MAX_CORRELATED_TRADES=0                # ❌ Unlimited

# ── Daily Risk Guard ──
MAX_DAILY_TRADES=0                     # ❌ Unlimited
MAX_DAILY_LOSS=0.0                     # ❌ Unlimited
MAX_CONSECUTIVE_LOSSES=10              # ⛔ Dừng sau 10 lần thua liên tiếp
```

### ⚠️ Logic ẩn quan trọng từ .env

| Logic | Giải thích |
|-------|-----------|
| **breakeven/trailing/partial = 0** | Global defaults tắt hết. Nếu channel KHÔNG override → lệnh mở sẽ **KHÔNG được bảo vệ** — chỉ SL/TP gốc hoạt động. |
| **CIRCUIT_BREAKER_THRESHOLD=999** | Bot gần như không bao giờ tự dừng do lỗi execute. Cần monitor thủ công. |
| **MAX_CONSECUTIVE_LOSSES=10** | Sau 10 lệnh thua liên tiếp → **TẤT CẢ trading dừng** cho đến khi có 1 lệnh thắng (poll mỗi 5 phút). |
| **POSITION_MANAGER_POLL_SECONDS=3** | Quét giá mỗi 3 giây — nhanh hơn default (5s). Breakeven/trailing react nhanh hơn nhưng tốn resource. |
| **PENDING_ORDER_TTL_MINUTES=5** | LIMIT/STOP chưa khớp sau 5 phút → tự hủy. Khá ngắn — re-entry levels có thể bị hủy sớm. |
| **SYMBOL_SUFFIX=m** | Mọi symbol từ signal auto thêm "m": XAUUSD → XAUUSDm. Nếu broker đổi suffix → tất cả lệnh fail. |
| **MAX_ENTRY_DISTANCE_PIPS=200** | Rất rộng — gần như không reject signal nào dựa trên entry distance. |

---

## 2. Channel A: @shushutest1101 — Default Config

### Config hiệu lực

Channel này **KHÔNG có** entry trong `channels.json` → dùng toàn bộ `default`:

```json
// Effective config cho @shushutest1101:
{
    "rules": {
        "breakeven_trigger_pips": 0,       // ❌ Disabled
        "breakeven_lock_pips": 2,          // (unused vì trigger=0)
        "trailing_stop_pips": 0,           // ❌ Disabled
        "partial_close_percent": 0,        // ❌ Disabled
        "secure_profit_action": "close_worst_be_rest",
        "reply_be_lock_pips": 1
    },
    "strategy": {
        "mode": "single",                  // 1 signal = 1 order
        "max_entries": 1,
        "reentry_enabled": false,          // Không re-entry
        "volume_split": "equal",
        // Guards tất cả = 0 (disabled)
        "min_sl_distance_pips": 0,
        "default_sl_pips_from_zone": 0,
        "sl_buffer_pips": 0,
        "max_sl_distance_pips": 0
    },
    "risk": {},                            // → dùng .env: FIXED_LOT 0.01
    "validation": {}                       // → dùng .env: 200/10/7 pips
}
```

### Luồng chi tiết — Ví dụ: `SELL XAUUSD 3340, SL 3352, TP 3300`

```
📱 Telegram message từ @shushutest1101
│
▼ STEP 0: Command Check
│  "SELL XAUUSD..." → KHÔNG phải command (close/be/status)
│  → Tiếp tục parse
│
▼ STEP 1: SignalParser
│  Parse thành:
│    symbol = XAUUSD (→ XAUUSDm sau suffix)
│    side = SELL
│    entry = 3340.0
│    sl = 3352.0
│    tp = [3300.0]
│    fingerprint = "abc123def456"
│    received_at = 2026-03-29T15:00:00+07:00
│
▼ STEP 2: Safety Gates (chạy tuần tự, fail sớm = reject)
│
│  ┌─ 2a. Circuit Breaker ─────────────────────┐
│  │ Threshold = 999. Consecutive fails = 0     │
│  │ → OPEN? NO → PASS ✅                       │
│  └────────────────────────────────────────────┘
│
│  ┌─ 2b. Daily Risk Guard ────────────────────┐
│  │ MAX_DAILY_TRADES=0 → unlimited → PASS ✅   │
│  │ MAX_DAILY_LOSS=0 → unlimited → PASS ✅     │
│  │ MAX_CONSECUTIVE_LOSSES=10                  │
│  │ Consecutive losses hiện tại = 2            │
│  │ 2 < 10 → PASS ✅                           │
│  └────────────────────────────────────────────┘
│
│  ┌─ 2c. Exposure Guard ──────────────────────┐
│  │ MAX_SAME_SYMBOL_TRADES=0 → unlimited      │
│  │ → PASS ✅                                   │
│  └────────────────────────────────────────────┘
│
│  ┌─ 2d. Open Trades Gate ────────────────────┐
│  │ Hiện có 3 positions. MAX_OPEN_TRADES=10    │
│  │ 3 < 10 → PASS ✅                           │
│  └────────────────────────────────────────────┘
│
▼ STEP 3: Duplicate Check
│  fingerprint "abc123def456" có trong DB trong 60s gần?
│  → NO → PASS ✅
│
▼ STEP 4: Market Data (lấy từ MT5)
│  XAUUSDm: bid=3339.5, ask=3340.0
│  point=0.01, pip_size=0.1
│  spread = (ask - bid) / pip_size = 0.5 / 0.1 = 5.0 pips
│
▼ STEP 5: Validator (8 rules)
│  ┌────────────────────────────────────────────┐
│  │ R1: SL/TP logic? SELL: SL > entry ✅       │
│  │ R2: TP < entry? 3300 < 3340 ✅             │
│  │ R3: Spread ≤ 7.0? 5.0 ≤ 7.0 ✅            │
│  │ R4: Signal age ≤ 60s? ✅                   │
│  │ R5: Entry distance ≤ 200 pips? ✅          │
│  │ ... (all pass)                             │
│  └────────────────────────────────────────────┘
│
▼ STEP 6: Store Signal → DB (status=PARSED)
│
▼ STEP 6.5: Drift Guard
│  entry=3340, ask=3340.0 (SELL dùng ask)
│  drift = |3340 - 3340| / 0.1 = 0 pips
│  0 ≤ 10 → PASS ✅
│
▼ STEP 7: Pipeline Execute
│
│  ┌─ Channel strategy: mode=single ───────────┐
│  │ max_entries=1 → 1 order duy nhất           │
│  └────────────────────────────────────────────┘
│
│  ┌─ RiskManager ─────────────────────────────┐
│  │ RISK_MODE=FIXED_LOT                       │
│  │ lot = 0.01                                │
│  │ Snap: 0.01 (≥ LOT_MIN, ≤ LOT_MAX) ✅     │
│  └────────────────────────────────────────────┘
│
│  ┌─ OrderBuilder ────────────────────────────┐
│  │ |entry - ask| = |3340 - 3340| = 0 pts     │
│  │ 0 ≤ MARKET_TOLERANCE=30 points            │
│  │ → ORDER TYPE: SELL (MARKET) ✅            │
│  │                                            │
│  │ Build request:                             │
│  │   action = TRADE_ACTION_DEAL              │
│  │   symbol = XAUUSDm                        │
│  │   volume = 0.01                           │
│  │   type = ORDER_TYPE_SELL                  │
│  │   price = 3339.5 (bid)                    │
│  │   sl = 3352.0                             │
│  │   tp = 3300.0                             │
│  │   deviation = 20                          │
│  │   magic = 234000                          │
│  └────────────────────────────────────────────┘
│
│  ┌─ TradeExecutor ───────────────────────────┐
│  │ mt5.order_send(request)                   │
│  │ → retcode=10009 (DONE) ✅                 │
│  │ → ticket=12345678                         │
│  │ → Store order to DB                       │
│  │ → Register group (single-ticket group)    │
│  └────────────────────────────────────────────┘
│
▼ STEP 8: Post-Execute
│  📩 DEBUG message gửi TG admin (DEBUG_SIGNAL_DECISION=true)
│  📩 Telegram alert: "✅ SELL XAUUSDm 0.01 lot at 3339.5"
│
└─ DONE. Lệnh đang chạy trên MT5.
```

### Sau khi vào lệnh — Position Manager quét mỗi 3s

```
⏱ Mỗi 3 giây, PositionManager._check_positions():

Ticket 12345678 thuộc group? YES (single-ticket group)
  → group_trailing_pips = 0 (default, KHÔNG set)
  → Fallback: _manage_individual() per ticket

_manage_individual(ticket=12345678):
  ┌─ Breakeven? ────────────┐
  │ breakeven_trigger = 0   │    ← default channel, 0 = disabled
  │ → SKIP ❌                │
  └─────────────────────────┘

  ┌─ Trailing stop? ────────┐
  │ trailing_stop = 0       │    ← default channel, 0 = disabled
  │ → SKIP ❌                │
  └─────────────────────────┘

  ┌─ Partial close? ────────┐
  │ trigger_pips = 0        │    ← .env, 0 = disabled
  │ close_lot = 0           │
  │ partial_percent = 0     │    ← default channel, 0 = disabled
  │ → SKIP ❌                │
  └─────────────────────────┘

⚠️ KẾT LUẬN: Lệnh từ @shushutest1101 KHÔNG ĐƯỢC BẢO VỆ GÌ.
   Chỉ SL 3352 và TP 3300 gốc hoạt động.
   Bot KHÔNG tự breakeven, KHÔNG trailing, KHÔNG partial close.
   Lệnh sẽ chạy cho đến khi:
     a) Giá chạm SL 3352 → thua
     b) Giá chạm TP 3300 → thắng
     c) Admin reply "close" / "be" / "+30" trên Telegram → manual action
```

### Reply actions khả dụng

| Reply text | Action | Kết quả |
|-----------|--------|---------|
| `close` | CLOSE | Đóng lệnh. Chỉ có 1 ticket → đóng nó. |
| `be` | BREAKEVEN | SL = entry ± `reply_be_lock_pips=1` → SELL: SL = 3340 - 1×$0.1 = 3339.9 |
| `+30` | SECURE_PROFIT | Chỉ có 1 ticket → đóng nó luôn (không có "worst" để chọn) |
| `sl 3345` | MOVE_SL | Đổi SL sang 3345 |
| `cancel` | CANCEL | Hủy pending orders (nếu có) |

---

## 3. Channel B: Noval (-1002044139064) — Custom Config

### Config hiệu lực

```json
{
    "name": "Noval channel",
    "rules": {
        "breakeven_trigger_pips": 50,      // ✅ +50 pips → breakeven
        "breakeven_lock_pips": 30,         // ✅ Lock $3.0 profit (30 pips × $0.1)
        "trailing_stop_pips": 40,          // ✅ Trail SL cách giá $4.0
        "partial_close_percent": 0,        // ❌ Disabled
        "secure_profit_action": "close_worst_be_rest",
        "reply_be_lock_pips": 10           // Reply "be" → lock $1.0 profit
    },
    "strategy": {
        "mode": "range",                   // ✅ Multi-entry từ zone
        "max_entries": 2,                  // ✅ Tối đa 2 orders
        "execute_all_immediately": false,  // P1 MARKET ngay, P2 chờ RangeMonitor
        "signal_ttl_minutes": 30,          // P2 hết hạn sau 30 phút
        "volume_split": "per_entry",       // ✅ Mỗi entry = full 0.01 lot
        "min_sl_distance_pips": 20,        // ✅ Reject nếu giá < 20 pips từ SL
        "default_sl_pips_from_zone": 55,   // ✅ Tự tạo SL nếu signal không có
        "reentry_tolerance_pips": 5,       // ✅ Trigger sớm 5 pips ($0.50)
        "max_reentry_distance_pips": 10,   // ✅ Reject re-entry nếu giá trôi > 10 pips ($1.0)
        "reentry_step_pips": 35,           // ✅ P2 cách P1 = 35 pips ($3.50)
        "sl_buffer_pips": 5,              // ✅ Nới SL thêm 5 pips ($0.50) tránh spike
        "max_sl_distance_pips": 100        // ✅ Cap SL ≤ 100 pips ($10.0) từ entry
    }
    // risk: không set → dùng .env: FIXED_LOT 0.01
    // validation: không set → dùng .env: 200/10/7 pips
    // group_trailing_pips: KHÔNG SET → = 0 → dùng individual management
}
```

### ⚠️ Logic ẩn quan trọng cho Noval

| Logic ẩn | Giải thích |
|---------|-----------|
| **`group_trailing_pips` = 0** | Noval **KHÔNG** có group trailing. Dù mode=range tạo 2 lệnh, mỗi lệnh được quản lý **riêng** bởi `breakeven_trigger=50` + `trailing_stop=40`. |
| **`per_entry` split** | Mỗi entry nhận **full 0.01 lot**. Tổng = 0.02 lot (nếu P2 trigger). KHÔNG chia nhỏ. |
| **`reentry_step_pips=35`** | P2 entry = P1 entry + 35 pips (SELL: cao hơn P1). Khá xa — P2 có thể không bao giờ trigger. |
| **`sl_buffer_pips=5`** | SL gốc 3352 → SL thực = 3352 + $0.50 = 3352.5 (SELL: nới lên). Tránh spike. |
| **`max_sl_distance_pips=100`** | Nếu signal SL quá xa (>100 pips = $10), sẽ bị cap về 100 pips. |
| **`default_sl_pips_from_zone=55`** | Signal KHÔNG có SL → bot tự tạo: SELL: zone_high + 55 pips × $0.1 = zone_high + $5.50 |
| **`min_sl_distance_pips=20`** | Nếu giá đã < 20 pips ($2.00) từ SL → REJECT order (giá quá gần SL, risk/reward tệ). |
| **`signal_ttl_minutes=30`** | P2 hết hạn sau 30 phút. Nếu giá không chạm level P2 trong 30p → P2 EXPIRED. |
| **PARTIAL_CLOSE = disabled** | Đang dùng `PARTIAL_CLOSE_TRIGGER_PIPS=0` + `PARTIAL_CLOSE_LOT=0` (.env) + `partial_close_percent=0` (channel) → **KHÔNG có partial close tự động.** |

### Luồng chi tiết — Ví dụ: `SELL XAUUSD 3340-3347, SL 3352, TP 3300`

```
📱 Telegram message từ Noval channel
│  "SELL XAUUSD 3340-3347, SL 3352, TP 3300"
│
▼ STEP 1: SignalParser
│  Parse thành:
│    symbol = XAUUSD (→ XAUUSDm)
│    side = SELL
│    entry = 3340.0 (zone_low)
│    entry_range = [3340.0, 3347.0]    ← parser detect range
│    sl = 3352.0
│    tp = [3300.0]
│    fingerprint = "noval_abc123"
│
▼ STEP 2-5: Safety Gates + Validate (giống Channel A)
│  Spread ≤ 7? ✅ | Open trades < 10? ✅ | Dedup? ✅ | ...
│
▼ STEP 6: Store Signal → DB
│
▼ STEP 6.5: Pipeline Guards (NOVAL-SPECIFIC)
│
│  ┌─ G1: max_sl_distance_pips = 100 ──────────┐
│  │ SL distance = |3340 - 3352| / 0.1 = 120p   │
│  │ 120 > 100 → CAP SL                         │
│  │ SELL: new_sl = entry + 100 × $0.1           │
│  │         = 3340 + $10 = 3350                  │
│  │ SL thay đổi: 3352 → 3350 ✅                 │
│  └─────────────────────────────────────────────┘
│
│  ┌─ G2: sl_buffer_pips = 5 ──────────────────┐
│  │ SELL: nới SL lên (xa entry hơn)             │
│  │ new_sl = 3350 + 5 × $0.1 = 3350.5           │
│  │ SL thay đổi: 3350 → 3350.5 ✅               │
│  └─────────────────────────────────────────────┘
│
│  ┌─ G3: min_sl_distance_pips = 20 ───────────┐
│  │ Giá hiện tại ask = 3340                     │
│  │ SL distance = |3340 - 3350.5| / 0.1 = 105p  │
│  │ 105 ≥ 20 → PASS ✅                          │
│  │ (Nếu giá đã 3349, distance=15 < 20 → SKIP) │
│  └─────────────────────────────────────────────┘
│
▼ STEP 7: Pipeline Execute (mode=range)
│
│  ┌─ EntryStrategy.plan_entries() ────────────┐
│  │ mode = "range"                             │
│  │ max_entries = 2                            │
│  │ reentry_step_pips = 35                     │
│  │ entry_range = [3340, 3347]                 │
│  │                                            │
│  │ SELL: entry từ zone_low lên                │
│  │ P1 = 3340.0 (zone_low)                    │
│  │ P2 = 3340 + 35 × $0.1 = 3343.5            │
│  │                                            │
│  │ Plans:                                     │
│  │   L0: entry=3340.0 (execute ngay)          │
│  │   L1: entry=3343.5 (chờ RangeMonitor)      │
│  └────────────────────────────────────────────┘
│
│  ┌─ split_volume(mode="per_entry") ──────────┐
│  │ Mỗi level nhận full lot:                  │
│  │   L0: 0.01 lot                             │
│  │   L1: 0.01 lot                             │
│  │ Tổng exposure nếu P2 trigger: 0.02 lot    │
│  └────────────────────────────────────────────┘
│
│  ┌─ L0: Execute ngay ────────────────────────┐
│  │ |3340 - ask| = 0 ≤ 30 pts → MARKET        │
│  │ SELL XAUUSDm 0.01 lot at 3339.5 (bid)     │
│  │ SL = 3350.5 (sau guards)                  │
│  │ TP = 3300.0                                │
│  │ → ticket=11111111                          │
│  └────────────────────────────────────────────┘
│
│  ┌─ L1: Defer → RangeMonitor ────────────────┐
│  │ entry=3343.5                               │
│  │ execute_all_immediately=false               │
│  │ → Register PENDING trong SignalStateManager │
│  │ → RangeMonitor sẽ quét giá mỗi 5s          │
│  │ → Hết hạn sau 30 phút (signal_ttl=30)     │
│  └────────────────────────────────────────────┘
│
│  ┌─ Register Group ──────────────────────────┐
│  │ Group fingerprint = "noval_abc123"         │
│  │ Tickets = [11111111]                       │
│  │ group_trailing_pips = 0 (NOT SET)          │
│  │ → Save to DB for restart recovery          │
│  └────────────────────────────────────────────┘
│
└─ DONE. P1 đang chạy. P2 đang chờ.
```

### Phase 2: RangeMonitor quét P2

```
⏱ RangeMonitor chạy mỗi 5 giây:

  Thời gian: T+10 phút. Signal chưa hết hạn (30 phút).

  ┌─ Check P2 level = 3343.5 ──────────────────┐
  │ reentry_tolerance_pips = 5 ($0.50)           │
  │ Effective level = 3343.5 - $0.50 = 3343.0    │
  │ (SELL: trigger khi giá LÊN qua level)       │
  │                                              │
  │ Giá hiện tại ask = 3344.0                    │
  │ Previous ask = 3342.0                        │
  │ prev < 3343.0 → curr ≥ 3343.0               │
  │ → CROSS DETECTED ✅                          │
  │                                              │
  │ Distance check:                              │
  │   |3344 - 3343.5| / 0.1 = 5 pips             │
  │   5 ≤ max_reentry_distance=10 → OK ✅        │
  │                                              │
  │ Min SL distance check:                       │
  │   |3344 - 3350.5| / 0.1 = 65 pips            │
  │   65 ≥ 20 → OK ✅                            │
  │                                              │
  │ Re-run Safety Gates (CB + Daily + Exposure)  │
  │   → All PASS ✅                               │
  │                                              │
  │ Execute P2:                                  │
  │   SELL XAUUSDm 0.01 lot at 3343.5 (MARKET)  │
  │   SL = 3350.5                                │
  │   TP = 3300.0                                │
  │   → ticket=22222222                          │
  │                                              │
  │ Group update:                                │
  │   tickets = [11111111, 22222222]              │
  │   Signal state → COMPLETED (all levels done)  │
  └──────────────────────────────────────────────┘

  ✅ Bây giờ có 2 lệnh SELL đang chạy:
     P1: ticket=11111111, entry=3340.0, 0.01 lot
     P2: ticket=22222222, entry=3343.5, 0.01 lot
     Tổng exposure: 0.02 lot
```

### Phase 3: Position Manager quản lý lệnh — Mỗi 3 giây

```
⏱ PositionManager._check_positions() mỗi 3s:

  Tickets [11111111, 22222222] thuộc group "noval_abc123"
  group_trailing_pips = 0 → fallback _manage_individual() PER TICKET

  ═══════════════════════════════════════════════════
  TICKET 11111111 (P1, entry=3340.0)
  ═══════════════════════════════════════════════════
  Giá hiện tại: ask = 3335.0 (SELL dùng ask)
  profit_pips = (3340 - 3335) / 0.1 = 50 pips

  ┌─ Breakeven? ────────────────────────────────┐
  │ trigger = 50 pips                            │
  │ profit = 50 pips ≥ 50 → TRIGGER ✅           │
  │ Already applied? NO                          │
  │                                              │
  │ SELL: new_sl = entry - lock × pip_size       │
  │     = 3340 - 30 × $0.1 = 3340 - $3 = 3337   │
  │                                              │
  │ Current SL = 3350.5                          │
  │ 3337 < 3350.5 (SELL: lower = better) → DỊCH │
  │ → SL = 3337.0 ✅                             │
  │ → _breakeven_applied.add(11111111)           │
  │ 📩 Telegram: "🔒 Breakeven P1 SL→3337"       │
  └──────────────────────────────────────────────┘

  ┌─ Trailing stop? ────────────────────────────┐
  │ trail_pips = 40                              │
  │ profit = 50 ≥ 40 → active                   │
  │                                              │
  │ SELL: new_sl = ask + trail × pip_size        │
  │     = 3335 + 40 × $0.1 = 3335 + $4 = 3339   │
  │                                              │
  │ Current SL = 3337 (just set by breakeven)    │
  │ 3339 > 3337 → KHÔNG DỊCH (SELL: higher=worse)│
  │ → SKIP ❌ (trailing SL sẽ kick in khi giá    │
  │   xuống đủ xa)                               │
  └──────────────────────────────────────────────┘

  ┌─ Partial close? ────────────────────────────┐
  │ trigger_pips = 0 (from .env) → ❌ SKIP       │
  └──────────────────────────────────────────────┘

  ═══════════════════════════════════════════════════
  TICKET 22222222 (P2, entry=3343.5)
  ═══════════════════════════════════════════════════
  profit_pips = (3343.5 - 3335) / 0.1 = 85 pips

  ┌─ Breakeven? ────────────────────────────────┐
  │ 85 ≥ 50 → TRIGGER ✅                        │
  │ new_sl = 3343.5 - $3 = 3340.5                │
  │ Current SL = 3350.5                          │
  │ 3340.5 < 3350.5 → DỊCH SL = 3340.5          │
  └──────────────────────────────────────────────┘

  ┌─ Trailing stop? ────────────────────────────┐
  │ new_sl = 3335 + $4 = 3339                    │
  │ Current SL = 3340.5                          │
  │ 3339 < 3340.5 → DỊCH SL = 3339 ✅           │
  │ (trailing đang tốt hơn breakeven cho P2!)    │
  │ 📩 Alert nếu SL dịch ≥ 10 pips               │
  └──────────────────────────────────────────────┘
```

### Phase 4: Giá tiếp tục xuống — Trailing đuổi

```
  Giá ask = 3320.0, profit P1 = 200 pips, P2 = 235 pips

  P1: trailing new_sl = 3320 + $4 = 3324
      current SL = 3337 → 3324 < 3337 → DỊCH ✅ SL = 3324

  P2: trailing new_sl = 3320 + $4 = 3324
      current SL = 3339 → 3324 < 3339 → DỊCH ✅ SL = 3324

  ⚠️ LƯU Ý: 2 lệnh có SL KHÁC NHAU ban đầu (do breakeven lock
  tại entry khác nhau), nhưng trailing sẽ ĐỒNG BỘ SL khi giá
  xuống xa — cả 2 converge về cùng SL = ask + $4.
```

### Phase 5: Giá quay đầu — SL hit

```
  Giá ask bắt đầu leo từ 3310 → 3320 → 3324

  Trailing KHÔNG dịch ngược (3324 + $4 = 3328 > 3324 → SKIP)
  SL giữ nguyên = 3324

  Giá ask = 3324 → SL TRIGGER trên MT5
  → CẢ 2 LỆNH ĐÓNG:
    P1: entry 3340, close 3324 → profit = $1.60 (0.01 lot × 16 × $1)
    P2: entry 3343.5, close 3324 → profit = $1.95

  📩 TradeTracker detect → gửi PnL reply về Telegram admin
```

### Reply actions khả dụng cho Noval

| Reply | Action | Kết quả cho group 2 lệnh |
|-------|--------|-------------------------|
| `close` | CLOSE | `reply_close_strategy="close_worst_be_rest"` → đóng worst entry (P1: entry thấp nhất cho SELL = ít lãi nhất). Lệnh còn lại giữ nguyên. |
| `be` | BREAKEVEN | Cả 2 lệnh: SL = entry - `reply_be_lock_pips=10` × $0.1. P1: SL=3339, P2: SL=3342.5. Guard: nếu SL hiện tại tốt hơn → giữ. |
| `+30` | SECURE_PROFIT | Đóng worst (P1) + BE cho P2: SL = P1 entry - lock = 3340 - $1 = 3339. Guard: nếu trailing đã set tốt hơn → giữ. |
| `close 50%` | CLOSE_PARTIAL | Đóng 50% volume mỗi ticket: 0.01 × 50% = 0.005 → snap 0.01 (LOT_STEP) → 🚫 volume = lot_min → KHÔNG thể chia. |
| `cancel` | CANCEL | Huỷ pending P2 nếu chưa trigger + cancel trong SignalStateManager. |

### Kịch bản P2 không trigger

```
  Giá không bao giờ lên 3343.0 (effective level với tolerance)
  Sau 30 phút (signal_ttl_minutes=30):
    → RangeMonitor mark P2 = EXPIRED
    → Signal state → COMPLETED (L0 executed, L1 expired)
    → Chỉ P1 đang chạy, managed individually
```

### Kịch bản signal KHÔNG có SL

```
  "SELL XAUUSD 3340-3347, TP 3300"  ← KHÔNG có SL

  ┌─ default_sl_pips_from_zone = 55 ────────────┐
  │ SELL: SL tự tạo = zone_high + 55 × $0.1     │
  │     = 3347 + $5.50 = 3352.5                  │
  │                                              │
  │ Sau đó:                                      │
  │ max_sl_distance check: 3352.5                │
  │ |3340 - 3352.5| / 0.1 = 125 pips > 100      │
  │ → Cap: new_sl = 3340 + $10 = 3350           │
  │ + sl_buffer: 3350 + $0.50 = 3350.5           │
  │                                              │
  │ Final SL = 3350.5                            │
  └──────────────────────────────────────────────┘
```

---

## 4. Background Tasks

Chạy song song, ảnh hưởng **mọi channel**.

```
┌────────────────────────────────────────────────────────────┐
│ TASK                │ INTERVAL  │ EFFECT                    │
├─────────────────────┼───────────┼───────────────────────────┤
│ PositionManager     │ 3s        │ BE/trailing/partial close │
│ RangeMonitor        │ 5s        │ Trigger re-entry P2       │
│ TradeTracker        │ 30s       │ Detect close → PnL reply  │
│ OrderLifecycle      │ 30s       │ Hủy pending > 5 phút      │
│ MT5Watchdog         │ 30s       │ Health check MT5           │
│ DailyRiskGuard      │ 5 min     │ Poll deals, check limits  │
│ Heartbeat           │ 30 min    │ Log status summary         │
│ Storage Cleanup     │ 24h       │ Xóa records cũ > 30 ngày  │
│ Position Cleanup    │ 1 AM UTC+7│ Prune memory dicts         │
│ Session Reset       │ 12h       │ Telethon session refresh   │
└─────────────────────┴───────────┴───────────────────────────┘
```

### Timeline chạy — khi có 1 signal Noval

```
T=0s    Signal nhận, parse, validate, P1 execute
T=0.1s  Group register, P2 register to RangeMonitor
T=3s    PositionManager: check P1 (BE=0? trail=0? → SKIP hoặc trigger)
T=5s    RangeMonitor: check P2 level (giá cross chưa?)
T=6s    PositionManager: check P1 again
T=10s   RangeMonitor: check P2 again
...
T=30s   TradeTracker: poll MT5 deals (nếu có close → PnL)
T=30s   OrderLifecycle: check pending orders > 5 phút?
T=30s   MT5Watchdog: MT5 alive?
...
T=300s  DailyRiskGuard: poll deal history, update counters
...
T=1800s (30 min) P2 hết hạn nếu chưa trigger → EXPIRED
```

---

> 📌 **File này phản ánh config tại thời điểm viết.** Nếu config thay đổi → luồng thay đổi theo.
>
> Xem `STRATEGY_CONFIG_GUIDE.md` để biết ý nghĩa từng biến và cách đổi.
