# LOGIC: Trade Strategy & Order Decision

> Mục đích: Giải thích CHI TIẾT chiến lược quyết định lệnh — khi nào vào lệnh, loại lệnh gì, khi nào hủy, khi nào dừng.  
> File này giúp bạn tự thay đổi chiến lược trading mà không cần hiểu toàn bộ codebase.

---

## Tổng Quan Pipeline Quyết Định

```
ParsedSignal (từ parser)
  ↓
[1] Circuit Breaker Check     → OPEN? → REJECT
  ↓
[2] Duplicate Check           → trùng? → REJECT
  ↓
[3] Lấy giá Live (bid/ask)   → MT5 hoặc Dry-Run simulate
  ↓
[4] Validation (8 rules)      → fail? → REJECT
  ↓
[5] Tính Volume (lot size)    → RiskManager
  ↓
[6] Quyết định Order Type     → MARKET / LIMIT / STOP
  ↓
[7] Build MT5 Request
  ↓
[8] Execute (hoặc Dry-Run)    → thành công? → record_success : record_failure
  ↓
[9] Lưu DB + Log
```

> **File chính**: `main.py` → method `_do_process_signal()` (dòng 250-460)

---

## [1] Circuit Breaker — Khi Nào DỪNG Giao Dịch

**File**: `core/circuit_breaker.py`  
**Check tại**: `main.py:318`

```python
if not self.circuit_breaker.is_trading_allowed:
    # → REJECT signal, không xử lý tiếp
```

### 3 trạng thái:

| State | Ý nghĩa | Giao dịch? |
|-------|---------|------------|
| `CLOSED` | Bình thường | ✅ Có |
| `OPEN` | Đã lỗi liên tiếp, đang pause | ❌ Không |
| `HALF_OPEN` | Hết cooldown, thử 1 lệnh probe | ✅ Có (1 lệnh) |

### Chuyển trạng thái:

```
CLOSED → (N lỗi liên tiếp) → OPEN
OPEN → (sau cooldown seconds) → HALF_OPEN
HALF_OPEN → (probe thành công) → CLOSED
HALF_OPEN → (probe thất bại) → OPEN
```

### Config:

| Env Key | Default | Ảnh hưởng |
|---------|---------|-----------|
| `CIRCUIT_BREAKER_THRESHOLD` | `3` | Số lỗi liên tiếp để mở breaker. Giảm xuống 1-2 → nhạy hơn, dễ pause. Tăng lên 5-10 → chịu lỗi hơn nhưng rủi ro mất tiền nhiều lần trước khi dừng. |
| `CIRCUIT_BREAKER_COOLDOWN` | `300` (5 phút) | Thời gian chờ trước khi thử lại. Giảm → probe sớm hơn. Tăng → an toàn hơn nhưng chậm hồi phục. |

### Ghi nhận success/failure:

| Event | File | Dòng | Hành động |
|-------|------|------|-----------|
| Lệnh thành công | `main.py` | 430, 436 | `circuit_breaker.record_success()` |
| Lệnh thất bại | `main.py` | 451 | `circuit_breaker.record_failure()` |

---

## [2] Duplicate Check — Chống Trùng Tín Hiệu

**Check tại**: `main.py:326-329`

```python
is_dup = self.storage.is_duplicate(
    signal_obj.fingerprint,
    ttl_seconds=self.settings.safety.signal_age_ttl_seconds,
)
```

**File**: `core/storage.py` → `is_duplicate()` (dòng 143-161)

### Logic:
- Query DB: tìm signal cùng fingerprint được tạo trong `ttl_seconds` gần nhất.
- Fingerprint = SHA-256(`symbol:side:entry:sl:tp`) → xem `LOGIC_SIGNAL_PARSER.md`.

### Config:

| Env Key | Default | Ảnh hưởng |
|---------|---------|-----------|
| `SIGNAL_AGE_TTL_SECONDS` | `60` | Window chống trùng. 60s = cùng signal gửi lại trong 1 phút → bị reject. Tăng → filter mạnh hơn. Giảm → cho phép signal giống nhau gần nhau hơn. |

### ⚠️ Lưu ý:
- **Duplicate KHÔNG reject ngay** ở đây — nó được truyền vào validator ở bước [4] rule 2.
- Signal giống nhau nhưng **entry khác 1 pip** → fingerprint khác → **KHÔNG bị filter**.

---

## [3] Lấy Giá Live — BID/ASK

**Check tại**: `main.py:332-348`

### Live mode:
```python
tick = self.executor.get_tick(signal_obj.symbol)
bid = tick.bid
ask = tick.ask
current_spread = tick.spread_points  # = (ask - bid) / point
current_price = ask if signal_obj.side == Side.BUY else bid
```

**File**: `core/trade_executor.py` → `get_tick()` (dòng 147-165)

### 🔴 CRITICAL: Price Reference Rule

| Side | Reference Price | Tại sao? |
|------|----------------|----------|
| **BUY** | **ASK** | Bạn MUA ở giá ASK (giá bên bán). ASK luôn > BID. |
| **SELL** | **BID** | Bạn BÁN ở giá BID (giá bên mua). BID luôn < ASK. |

> Dòng code: `main.py:334` và `main.py:346`  
> **Nếu đảo ngược (BUY dùng BID)** → order type sẽ sai, có thể gửi LIMIT khi nên gửi STOP.

### Dry-Run mode:
```python
bid, ask, current_spread = self._simulate_tick(signal_obj)
```

**File**: `main.py` → `_simulate_tick()` (dòng 190-229)

| Symbol chứa | Simulated Spread | Dòng code |
|-------------|-----------------|-----------|
| USD/EUR/GBP/JPY... (forex) | 0.0002 | 200-201 |
| XAU / GOLD (metals) | 0.5 | 202-203 |
| BTC / ETH (crypto) | 10.0 | 204-205 |

Giá sinh ra:
- **BUY**: `ask = entry`, `bid = entry - spread` (dòng 221-223)
- **SELL**: `bid = entry`, `ask = entry + spread` (dòng 224-226)

---

## [4] Validation — 8 Rules An Toàn

**File**: `core/signal_validator.py` → `validate()` (dòng 49-117)  
**Gọi tại**: `main.py:351-357`

### Thứ tự kiểm tra (QUAN TRỌNG — rule đầu reject sẽ bỏ qua các rule sau):

| Rule | Dòng code | Check | Config | Default | Khi fail |
|------|-----------|-------|--------|---------|----------|
| 1. Required fields | 71-75 | symbol & side phải có | — | — | Reject |
| 2. Duplicate | 78-82 | `is_duplicate` flag | `SIGNAL_AGE_TTL_SECONDS` | 60 | Reject |
| 3. SL coherence | 85-87 | BUY: SL < entry · SELL: SL > entry | — | — | Reject |
| 4. TP coherence | 90-92 | BUY: TP > entry · SELL: TP < entry | — | — | Reject |
| 5. Entry distance | 95-98 | \|entry - live_price\| ≤ max | `MAX_ENTRY_DISTANCE_POINTS` | 500 | Reject |
| 6. Signal age | 101-103 | age ≤ TTL | `SIGNAL_AGE_TTL_SECONDS` | 60 | Reject |
| 7. Spread | 106-109 | spread ≤ max | `MAX_SPREAD_POINTS` | 50 | Reject |
| 8. Max trades | 112-115 | open_positions < max | `MAX_OPEN_TRADES` | 5 | Reject |

### Chi tiết từng rule:

#### Rule 3 — SL Coherence (dòng 137-156)

```
BUY XAUUSD @ 2030, SL 2020  → ✅ SL (2020) < entry (2030)
BUY XAUUSD @ 2030, SL 2040  → ❌ SL (2040) ≥ entry (2030) → REJECT
SELL XAUUSD @ 2030, SL 2040 → ✅ SL (2040) > entry (2030)
SELL XAUUSD @ 2030, SL 2020 → ❌ SL (2020) ≤ entry (2030) → REJECT
```

> **Nếu SL hoặc entry = None** → skip check (dòng 139-140)

#### Rule 4 — TP Coherence (dòng 158-177)

```
BUY @ 2030, TP 2040   → ✅ TP > entry
BUY @ 2030, TP 2020   → ❌ TP ≤ entry → REJECT
SELL @ 2030, TP 2020  → ✅ TP < entry
SELL @ 2030, TP 2040  → ❌ TP ≥ entry → REJECT
```

> Kiểm tra **TẤT CẢ** TP (TP1, TP2, TP3...) — bất kỳ TP nào sai → reject.

#### Rule 5 — Entry Distance (dòng 179-196)

```
Giá live ASK = 2030
Signal entry = 2500
Distance = |2500 - 2030| = 470 points
MAX_ENTRY_DISTANCE_POINTS = 500
470 < 500 → ✅ PASS
```

### ⚠️ Nếu bạn muốn thay đổi:
- **Nới lỏng spread gate**: Tăng `MAX_SPREAD_POINTS` trong `.env`. Ví dụ: `100` cho phép spread rộng (ban đêm, tin tức).
- **Tắt entry distance check**: Set `MAX_ENTRY_DISTANCE_POINTS=99999`.
- **Bắt buộc có SL**: Thêm rule mới trong `validate()`: `if signal.sl is None: return ValidationResult(False, "missing SL")`.
- **Bắt buộc có TP**: Tương tự, check `if not signal.tp:`.

---

## [5] Tính Volume (Lot Size)

**File**: `core/risk_manager.py`  
**Gọi tại**: `main.py:376-380`

### Mode 1: FIXED_LOT (dòng 59-60)

```python
volume = self._fixed_lot  # từ FIXED_LOT_SIZE env
```

### Mode 2: RISK_PERCENT (dòng 64-92)

```python
risk_amount = balance * (risk_percent / 100)
sl_distance = |entry - sl|
volume = risk_amount / (sl_distance * pip_value)
```

**Ví dụ**: Balance $10,000, Risk 1%, Entry 2030, SL 2020:
```
risk_amount = 10000 * 0.01 = $100
sl_distance = |2030 - 2020| = 10
volume = 100 / (10 * pip_value)
```

### Clamp (dòng 94-103):

```python
volume = floor(volume / lot_step) * lot_step   # Làm tròn xuống
volume = max(lot_min, min(volume, lot_max))     # Giới hạn
```

### Config:

| Env Key | Default | Ảnh hưởng |
|---------|---------|-----------|
| `RISK_MODE` | `FIXED_LOT` | `FIXED_LOT` = lot cố định, `RISK_PERCENT` = tự tính theo SL distance |
| `FIXED_LOT_SIZE` | `0.01` | Lot cố định. 0.01 = micro lot. |
| `RISK_PERCENT` | `1.0` | % balance rủi ro mỗi lệnh. 1% = mất $100 nếu hit SL trên balance $10k. |
| `LOT_MIN` | `0.01` | Lot tối thiểu broker cho phép |
| `LOT_MAX` | `100.0` | Lot tối đa |
| `LOT_STEP` | `0.01` | Bước lot (broker quy định) |

### ⚠️ Fallback:
- Nếu `RISK_PERCENT` mode nhưng thiếu `balance`, `entry`, `sl`, hoặc `pip_value` → **tự động dùng `FIXED_LOT_SIZE`** (dòng 78-80).

---

## [6] Quyết Định Order Type — 🔴 LOGIC QUAN TRỌNG NHẤT

**File**: `core/order_builder.py` → `decide_order_type()` (dòng 50-157)  
**Gọi tại**: `main.py:401`

### Ma trận quyết định:

#### BUY (dòng 75-115, so sánh với ASK):

```
entry = None                    → MARKET ORDER (mua ngay)
|entry - ask| ≤ tolerance       → MARKET ORDER (giá quá gần)
entry < ask                     → BUY LIMIT  (chờ giá giảm xuống entry)
entry > ask                     → BUY STOP   (chờ giá tăng lên entry)
```

#### SELL (dòng 117-157, so sánh với BID):

```
entry = None                    → MARKET ORDER (bán ngay)
|entry - bid| ≤ tolerance       → MARKET ORDER (giá quá gần)
entry > bid                     → SELL LIMIT  (chờ giá tăng lên entry)
entry < bid                     → SELL STOP   (chờ giá giảm xuống entry)
```

### Tolerance:

```python
tolerance = MARKET_TOLERANCE_POINTS * point
# point = 0.00001 (forex) hoặc 0.01 (metals)
# Ví dụ: tolerance = 5.0 * 0.01 = 0.05 cho XAUUSD
```

**File**: `core/order_builder.py:68`  
**Config**: `MARKET_TOLERANCE_POINTS` trong `.env`

### ⚠️ Ví dụ thực tế XAUUSD:

```
Signal: BUY XAUUSD @ 2030
Live ASK: 2030.2
point = 0.01
tolerance = 5.0 * 0.01 = 0.05

|2030 - 2030.2| = 0.2 > 0.05  → BUY LIMIT (chờ giá giảm về 2030)
```

```
Signal: BUY XAUUSD @ 2030
Live ASK: 2030.03
|2030 - 2030.03| = 0.03 ≤ 0.05  → MARKET ORDER (giá đủ gần, mua ngay)
```

### ⚠️ Nếu bạn muốn thay đổi:
- **Luôn dùng MARKET**: Set `MARKET_TOLERANCE_POINTS=99999` → tất cả signal trở thành market order.
- **Luôn dùng LIMIT/STOP**: Set `MARKET_TOLERANCE_POINTS=0` → chỉ market khi `entry = None`.
- **Thay đổi logic hoàn toàn**: Sửa method `_decide_buy()` và `_decide_sell()` trong `order_builder.py:75-157`.

---

## [7] Build MT5 Request

**File**: `core/order_builder.py` → `build_request()` (dòng 159-214)  
**Gọi tại**: `main.py:402`

### Market Order (dòng 189-199):
```python
request = {
    "action": mt5.TRADE_ACTION_DEAL,      # Giao dịch ngay
    "type": mt5.ORDER_TYPE_BUY,           # hoặc SELL
    "price": ask,                          # BUY→ASK, SELL→BID
    "type_filling": mt5.ORDER_FILLING_IOC, # Immediate-Or-Cancel
    "deviation": DEVIATION_POINTS,         # Max slippage
    "magic": BOT_MAGIC_NUMBER,             # ID bot
}
```

### Pending Order (dòng 200-212):
```python
request = {
    "action": mt5.TRADE_ACTION_PENDING,    # Đặt lệnh chờ
    "type": mt5.ORDER_TYPE_BUY_LIMIT,      # hoặc BUY_STOP, SELL_LIMIT, SELL_STOP
    "price": signal.entry,                 # Giá entry từ signal
    "type_time": mt5.ORDER_TIME_GTC,       # Good-Till-Cancelled
    "type_filling": mt5.ORDER_FILLING_RETURN, # Cho phép fill từng phần
}
```

### Config quan trọng:

| Env Key | Default | Ảnh hưởng |
|---------|---------|-----------|
| `DEVIATION_POINTS` | `20` | Slippage tối đa cho market order. Quá thấp → bị reject khi volatile. Quá cao → fill giá xấu. |
| `BOT_MAGIC_NUMBER` | `234000` | ID duy nhất để phân biệt lệnh bot vs lệnh tay trong MT5. Nếu chạy nhiều bot → mỗi bot cần magic khác nhau. |

### ⚠️ Về TP:
- **Chỉ TP1** (`signal.tp[0]`) được gắn vào lệnh (dòng 88, 97, 106, 114, 130, 139, 148, 156).
- Các TP còn lại (TP2, TP3) hiện tại **chỉ log**, chưa tự động partial close.
- Muốn dùng TP cuối: đổi `signal.tp[0]` → `signal.tp[-1]` ở các dòng trên.

---

## [8] Execute — Gửi Lệnh

**File**: `core/trade_executor.py` → `execute()` (dòng 210-313)  
**Gọi tại**: `main.py:433`

### Bounded Retry (dòng 226-283):

```
Lần 1: order_send(request)
  → Nếu retcode ∈ {10008, 10009, 10010} → SUCCESS ✅
  → Nếu retcode ∈ {10004, 10020, 10021, 10024, 10031} → RETRY
  → Nếu retcode khác → FAIL ❌ (không retry)
  → Nếu result = None → RETRY

Lần 2: sleep(1.0 * 2) → retry
Lần 3: sleep(1.0 * 3) → retry
→ Hết retry → FAIL
```

### Success codes (dòng 254):
| Retcode | Ý nghĩa |
|---------|---------|
| 10008 | `TRADE_RETCODE_PLACED` — Lệnh chờ đã đặt |
| 10009 | `TRADE_RETCODE_DONE` — Giao dịch hoàn tất |
| 10010 | `TRADE_RETCODE_DONE_PARTIAL` — Fill một phần |

### Retryable codes (dòng 272):
| Retcode | Ý nghĩa | Tại sao retry? |
|---------|---------|----------------|
| 10004 | REQUOTE | Giá đã thay đổi, thử lại |
| 10020 | PRICE_CHANGED | Tương tự |
| 10021 | PRICE_OFF | Giá không hợp lệ tạm thời |
| 10024 | TOO_MANY_REQUESTS | Rate limit, chờ rồi thử |
| 10031 | CONNECTION | Mất kết nối tạm |

### Non-retryable (fail ngay):
| Retcode | Ý nghĩa |
|---------|---------|
| 10006 | REJECT — Broker từ chối |
| 10013 | INVALID — Request sai |
| 10014 | INVALID_VOLUME — Lot sai |
| 10016 | INVALID_STOPS — SL/TP sai |
| 10018 | MARKET_CLOSED |
| 10019 | NO_MONEY |

### Config:

| Env Key | Default | Ảnh hưởng |
|---------|---------|-----------|
| `ORDER_MAX_RETRIES` | `3` | Tăng → chịu lỗi tốt hơn nhưng chậm hơn khi lỗi thật. Giảm → fail nhanh. |
| `ORDER_RETRY_DELAY_SECONDS` | `1.0` | Delay giữa retries = `delay * attempt_number`. Delay 1.0: lần 2 chờ 2s, lần 3 chờ 3s. |

### ⚠️ Nếu bạn muốn thay đổi:
- **Thêm retcode vào retryable**: Sửa dòng 272 trong `trade_executor.py`, thêm retcode vào tuple `(10004, 10020, ...)`.
- **Không retry**: Set `ORDER_MAX_RETRIES=1`.

---

## [9] Pending Order TTL — Khi Nào HỦY Lệnh Chờ

**File**: `core/order_lifecycle_manager.py`  
**Gọi tại**: `main.py:147-151`

### Logic (dòng 72-106):

```python
# Mỗi 30 giây, quét tất cả pending orders
for order in all_pending_orders:
    age = now - order.time_setup
    if age > PENDING_ORDER_TTL_MINUTES * 60:
        executor.cancel_order(order.ticket)
```

### Config:

| Env Key | Default | Ảnh hưởng |
|---------|---------|-----------|
| `PENDING_ORDER_TTL_MINUTES` | `15` | Lệnh chờ quá 15 phút → auto-cancel. Tăng → để lệnh chờ lâu hơn. Giảm → cancel sớm, tránh chạy lệnh cũ. |
| `LIFECYCLE_CHECK_INTERVAL_SECONDS` | `30` | Tần suất quét. Giảm → phản ứng nhanh hơn nhưng tải MT5 nhiều hơn. |

### ⚠️ Chỉ cancel lệnh có `magic = BOT_MAGIC_NUMBER`:
- Hiện tại quét **TẤT CẢ** pending orders, bao gồm lệnh tay.
- Nếu muốn chỉ cancel lệnh bot: thêm `if order["magic"] == BOT_MAGIC_NUMBER` vào dòng 80.

---

## [10] MT5 Watchdog — Khi Nào Reconnect

**File**: `core/mt5_watchdog.py`  
**Gọi tại**: `main.py:153-158`

### Logic (dòng 89-148):

```python
# Mỗi 30 giây
info = executor.account_info()

if info is not None:
    # OK — reset failure counter
    consecutive_failures = 0

if info is None:
    consecutive_failures += 1
    
    if is_weekend():
        # Suppress — không reinit vào cuối tuần
        return
    
    if consecutive_failures <= max_reinit:
        # Reinit với exponential backoff
        delay = 5.0 * (2 ^ (failures - 1))  # 5s, 10s, 20s, 40s, 80s
        executor.shutdown()
        sleep(delay)
        executor.init_mt5()
    else:
        # Alert: hết retry → cần can thiệp thủ công
        on_reinit_exhausted()
```

### Config:

| Env Key | Default | Ảnh hưởng |
|---------|---------|-----------|
| `WATCHDOG_INTERVAL_SECONDS` | `30` | Tần suất health check |
| `WATCHDOG_MAX_REINIT` | `5` | Max lần reinit. Sau 5 lần → gửi alert, dừng reinit. |

---

## Tóm Tắt: Signal Lifecycle Trong DB

Mỗi signal được track qua bảng `events`:

```
signal_received    → tin nhắn mới từ Telegram
signal_parsed      → parse thành công (có symbol + side)
signal_rejected    → bị reject bởi validator (kèm reason)
signal_submitted   → đã build request, sắp gửi MT5
signal_executed    → MT5 trả về success
signal_failed      → MT5 trả về failure (kèm retcode)
```

**File**: `main.py` — tất cả `store_event()` calls xuyên suốt pipeline.

---

## Tóm Tắt Nhanh: Muốn Thay Đổi Gì → Sửa Ở Đâu

| Muốn thay đổi | Sửa file | Sửa gì |
|---------------|----------|--------|
| Thêm format tin nhắn mới | `core/signal_parser/*.py` | Thêm regex |
| Thêm symbol mới | `utils/symbol_mapper.py:12-67` | Thêm vào dict |
| Luôn dùng market order | `.env` | `MARKET_TOLERANCE_POINTS=99999` |
| Bắt buộc có SL | `core/signal_validator.py:validate()` | Thêm check `sl is None` |
| Thay đổi TP nào dùng cho lệnh | `core/order_builder.py` | Đổi `signal.tp[0]` → `signal.tp[-1]` |
| Tắt circuit breaker | `.env` | `CIRCUIT_BREAKER_THRESHOLD=99999` |
| Chạy nhiều bot | `.env` | Đổi `BOT_MAGIC_NUMBER` cho mỗi bot |
| Nới lỏng spread | `.env` | Tăng `MAX_SPREAD_POINTS` |
| Chỉ cancel lệnh bot | `core/order_lifecycle_manager.py:80` | Thêm filter `magic` |
