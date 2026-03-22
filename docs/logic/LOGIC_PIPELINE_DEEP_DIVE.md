# PIPELINE DEEP-DIVE — Từ Parse thành công → Vào lệnh → Hủy lệnh

> Giả định: Telegram đã gửi message OK, parser đã parse **thành công** → `ParsedSignal`.
> File này đi qua **TỪNG DÒNG CODE** với **MỌI use case thực tế**.

---

## MỤC LỤC

1. [ParsedSignal — output sau khi parse thành công](#1-parsedsignal--output-sau-khi-parse-thành-công)
2. [9 Use Case cụ thể từ Telegram → Kết quả cuối](#2-9-use-case-cụ-thể-từ-telegram--kết-quả-cuối)
3. [Từng bước pipeline — giải thích từng dòng code](#3-từng-bước-pipeline--giải-thích-từng-dòng-code)
4. [Bảng biến — ý nghĩa, file gốc, ảnh hưởng khi đổi](#4-bảng-biến--ý-nghĩa-file-gốc-ảnh-hưởng-khi-đổi)
5. [Bản đồ: đổi dòng nào → ảnh hưởng cái nào](#5-bản-đồ-đổi-dòng-nào--ảnh-hưởng-cái-nào)
6. [Hướng dẫn Refactor chi tiết](#6-hướng-dẫn-refactor-chi-tiết)

---

## 1. ParsedSignal — output sau khi parse thành công

File: `core/models.py` dòng 36-49

```python
@dataclass
class ParsedSignal:
    symbol: str             # (1) Tên symbol broker: "XAUUSD", "EURUSD"
    side: Side              # (2) BUY hoặc SELL
    entry: float | None     # (3) Giá vào lệnh, None = vào lệnh MARKET ngay
    sl: float | None        # (4) Stop Loss price
    tp: list[float]         # (5) Danh sách Take Profit [TP1, TP2, TP3...]
    raw_text: str           # (6) Text gốc từ Telegram
    source_chat_id: str     # (7) ID chat Telegram
    source_message_id: str  # (8) ID message Telegram
    received_at: datetime   # (9) Thời điểm nhận message (UTC)
    fingerprint: str        # (10) SHA256 hash 16 ký tự, dùng để dedupe
```

**Fingerprint** tạo từ: `SHA256("XAUUSD:BUY:2030.0:2020.0:2040.0|2050.0")[:16]`

---

## 2. 9 Use Case cụ thể từ Telegram → Kết quả cuối

---

### USE CASE 1: BUY XAUUSD với entry price — vào BUY_LIMIT

**Telegram message:**
```
XAUUSD BUY 2030
SL 2020
TP1 2040
TP2 2050
TP3 2060
```

**ParsedSignal sau parse:**
```python
signal = ParsedSignal(
    symbol="XAUUSD", side=Side.BUY, entry=2030.0,
    sl=2020.0, tp=[2040.0, 2050.0, 2060.0],
    fingerprint="a1b2c3d4e5f6g7h8"
)
```

**Giả sử thị trường hiện tại:**
```
XAUUSD: bid=2034.50, ask=2035.00, spread=50 points = 5 pips
point=0.01, pip_size=0.1
```

**Pipeline chạy từng bước (v0.5.1):**

| Bước | Code | Giá trị | Kết quả |
|------|------|---------|---------|
| **Step 0: Command** | `command_parser.parse(raw_text)` | `None` (not a command) | → tiếp tục signal flow |
| **Step 2: Circuit Breaker** | `circuit_breaker.is_trading_allowed` | state=CLOSED | ✅ PASS |
| **Step 2b: Daily Risk** | `daily_guard.is_trading_allowed` | no limits hit | ✅ PASS |
| **Step 2c: Exposure** | `exposure_guard.is_allowed("XAUUSD")` | 0 open XAUUSD | ✅ PASS |
| **Step 3: Duplicate** | `storage.is_duplicate("a1b2c3d4e5f6g7h8", ttl=60)` | lần đầu | `is_dup=False` |
| **Step 4: Market Data** | `mt5.symbol_info("XAUUSD")` | point=0.01, digits=2 | pip_size=0.01×10=0.1 |
| | `executor.get_tick("XAUUSD")` | bid=2034.50, ask=2035.00 | spread_points=50 |
| | `ask if BUY` | ask=2035.00 | `current_price=2035.00` |
| | `50 / 10.0` | | `spread_pips=5.0` |
| **Validate Rule 1** | `signal.symbol="XAUUSD"` | có | ✅ |
| **Validate Rule 2** | `is_duplicate=False` | | ✅ |
| **Validate Rule 3** | SL coherence: `2020 < 2030` (BUY: SL < entry) | | ✅ |
| **Validate Rule 4** | TP coherence: `2040 > 2030`, `2050 > 2030`, `2060 > 2030` | | ✅ |
| **Validate Rule 5** | `|2030 - 2035| / 0.1 = 50.0 pips ≤ 50.0` | | ✅ PASS (vừa đúng limit) |
| **Validate Rule 6** | `age=2s ≤ 60s` | | ✅ |
| **Validate Rule 7** | `spread=5.0 ≤ 5.0` | | ✅ PASS (vừa đúng limit) |
| **Validate Rule 8** | `open_positions=2 < 5` | | ✅ |
| Volume | FIXED_LOT: `0.01` | | `volume=0.01` |
| **Order Decision** | `tolerance = 5 × 0.01 = 0.05` | | |
| | `|2030 - 2035| = 5.0 > 0.05` | entry < ask | **→ BUY_LIMIT** |
| Build Request | price=2030, sl=2020, tp=2040, type=BUY_LIMIT | | Pending order |
| | `deviation = compute_deviation(50) = max(20, 50×0) = 20` | | dynamic deviation |
| Execute | `mt5.order_send(request)` | retcode=10008 | **✅ SUCCESS** |

**Kết quả cuối cùng: Đặt lệnh BUY_LIMIT chờ giá về 2030 mới mua**

---

### USE CASE 2: BUY XAUUSD MARKET — không có entry price

**Telegram message:**
```
GOLD BUY NOW
SL 2920
TP 2950
```

**ParsedSignal:**
```python
signal = ParsedSignal(
    symbol="XAUUSD",      # "GOLD" → SymbolMapper → "XAUUSD"
    side=Side.BUY,
    entry=None,            # "NOW" → entry_detector trả None
    sl=2920.0, tp=[2950.0]
)
```

**Thị trường:** `bid=2934.50, ask=2935.00`

**Pipeline:**

| Bước | Code | Kết quả |
|------|------|---------|
| Validate Rule 3 | SL coherence: `sl=2920, entry=None` → **SKIP** (entry=None) | ✅ |
| Validate Rule 4 | TP coherence: `tp=2950, entry=None` → **SKIP** | ✅ |
| Validate Rule 5 | Entry distance: `entry=None` → **SKIP** | ✅ |
| Order Decision | `signal.entry is None` → trực tiếp **MARKET** | → OrderKind.MARKET |
| Build Request | action=TRADE_ACTION_DEAL, type=ORDER_TYPE_BUY, price=**ask=2935.00** | |
| | type_filling=ORDER_FILLING_IOC | |
| Execute | `mt5.order_send(request)` | **→ Mua ngay tại 2935.00** |

**Kết quả: Vào lệnh BUY ngay lập tức tại giá ask hiện tại**

---

### USE CASE 3: SELL EURUSD — vào SELL_LIMIT

**Telegram message:**
```
EURUSD SELL 1.0850
STOP LOSS 1.0900
TAKE PROFIT 1.0780
```

**ParsedSignal:**
```python
signal = ParsedSignal(
    symbol="EURUSD", side=Side.SELL, entry=1.0850,
    sl=1.0900, tp=[1.0780]
)
```

**Thị trường:** `bid=1.0830, ask=1.0832, point=0.00001, pip_size=0.0001`

**Pipeline:**

| Bước | Code | Tính toán | Kết quả |
|------|------|-----------|---------|
| Validate Rule 3 | SL coherence: SELL → SL phải > entry | `1.0900 > 1.0850` | ✅ |
| Validate Rule 4 | TP coherence: SELL → TP phải < entry | `1.0780 < 1.0850` | ✅ |
| Validate Rule 5 | `|1.0850 - 1.0830| / 0.0001 = 20 pips ≤ 50` | | ✅ |
| Spread | `(1.0832 - 1.0830) / 0.00001 = 20 pts → 20/10 = 2 pips` | | ✅ (2 ≤ 5) |
| **Order Decision** | SELL → so sánh entry vs **bid** | | |
| | `tolerance = 5 × 0.00001 = 0.00005` | | |
| | `|1.0850 - 1.0830| = 0.002 > 0.00005` | entry > bid | **→ SELL_LIMIT** |
| Build Request | action=TRADE_ACTION_PENDING, price=1.0850 | | Chờ giá lên 1.0850 |

**Kết quả: Đặt SELL_LIMIT chờ giá lên 1.0850 mới bán**

> **Tại sao SELL_LIMIT?** Vì entry(1.0850) > bid(1.0830) → muốn bán ở giá **cao hơn** giá hiện tại → đó là SELL_LIMIT.

---

### USE CASE 4: BUY_STOP — Entry cao hơn giá hiện tại

**Telegram message:**
```
XAUUSD BUY 2940
SL 2930
TP 2960
```

**Thị trường:** `bid=2934.50, ask=2935.00, point=0.01`

**Pipeline Order Decision:**
```
tolerance = 5 × 0.01 = 0.05
|2940 - 2935| = 5.0 > 0.05   → KHÔNG phải MARKET
entry(2940) > ask(2935)       → BUY_STOP
```

**Kết quả: Đặt BUY_STOP — chờ giá BÙNG LÊN 2940 rồi mới mua**

> **Tại sao BUY_STOP?** Vì muốn mua ở giá **cao hơn** hiện tại (breakout strategy).

---

### USE CASE 5: SELL_STOP — Entry thấp hơn giá hiện tại

**Telegram message:**
```
EURUSD SHORT 1.0800
SL 1.0850
TP 1.0750
```

**Thị trường:** `bid=1.0830, ask=1.0832, point=0.00001`

**Pipeline Order Decision:**
```
tolerance = 5 × 0.00001 = 0.00005
|1.0800 - 1.0830| = 0.003 > 0.00005   → KHÔNG phải MARKET
entry(1.0800) < bid(1.0830)             → SELL_STOP
```

**Kết quả: Đặt SELL_STOP — chờ giá RƠI XUỐNG 1.0800 rồi mới bán**

---

### USE CASE 6: Entry gần giá → Tự động vào MARKET

**Telegram message:**
```
XAUUSD BUY 2935.03
SL 2925
TP 2945
```

**Thị trường:** `ask=2935.00, point=0.01`

**Pipeline Order Decision:**
```
tolerance = 5 × 0.01 = 0.05
|2935.03 - 2935.00| = 0.03 ≤ 0.05   → MARKET!
```

**Kết quả: Tuy có entry price nhưng GẦN giá hiện tại quá → vào lệnh MARKET ngay**

> **Ý nghĩa của MARKET_TOLERANCE_POINTS:** Nếu entry cách giá hiện tại ≤ `5 × point` → coi như giá hiện tại, vào MARKET luôn thay vì đặt pending chờ 0.03$.

---

### USE CASE 7: BỊ REJECT — Entry quá xa giá

**Telegram message:**
```
XAUUSD BUY 2900
SL 2890
TP 2920
```

**Thị trường:** `ask=2960.00, pip_size=0.1`

**Pipeline Validate Rule 5:**
```
|2900 - 2960| / 0.1 = 600 pips > 50 pips
→ REJECTED! "entry distance (600.0 pips) exceeds max (50 pips)"
```

**Kết quả: Lệnh bị từ chối vì entry quá xa giá hiện tại**

> **Đổi ENV để cho phép:** Tăng `MAX_ENTRY_DISTANCE_PIPS=700` → sẽ pass.

---

### USE CASE 8: BỊ REJECT — Spread quá rộng

**Telegram message:**
```
XAUUSD BUY 2935
SL 2925
TP 2945
```

**Thị trường:** `bid=2934.00, ask=2935.00, spread_points=100`

**Pipeline:**
```
spread_pips = 100 / 10 = 10.0 pips
10.0 > 5.0  → REJECTED! "spread (10.0 pips) exceeds max (5.0 pips)"
```

**Kết quả: Lệnh bị từ chối vì spread quá rộng (thường xảy ra khi tin tức)**

> **Đổi ENV:** Tăng `MAX_SPREAD_PIPS=15` → chấp nhận spread rộng hơn.

---

### USE CASE 9: BỊ REJECT — SL sai vị trí (coherence fail)

**Telegram message (SAI):**
```
XAUUSD BUY 2935
SL 2940          ← SL CAO HƠN entry = vô lý cho lệnh BUY!
TP 2950
```

**Pipeline Validate Rule 3:**
```
BUY: SL(2940) >= entry(2935) = True
→ REJECTED! "BUY signal SL (2940.0) must be below entry (2935.0)"
```

**Kết quả: Từ chối vì SL ở trên entry → nếu giá đi lên thì hit SL trước TP**

---

## 3. Từng bước pipeline — giải thích từng dòng code

> File: `main.py`, function `_do_process_signal()`
> Pipeline v0.9.0: Steps 0–6 unchanged. Steps 7–9 now delegated to `SignalPipeline.execute_signal_plans()` (single/range/scale_in modes).
> The step-by-step breakdown below describes the **pre-P9 logic** for reference. In v0.9.0, the Pipeline handles volume, order building, and execution internally.

---

### Step 0: ⚡ COMMAND INTERCEPT (dòng 518-543)
```python
cmd = self.command_parser.parse(raw_text)
if cmd is not None:
    if dry_run:
        return  # skip in dry-run
    summary = self.command_executor.execute(cmd)
    return  # stop pipeline — not a signal
```

**Ý nghĩa**: Kiểm tra message có phải management command không **TRƯỚC** khi parse signal.

| Command | Ví dụ | Hành vi |
|---------|-------|---------|
| `CLOSE ALL` | "close all" | Đóng tất cả position bot |
| `CLOSE <SYMBOL>` | "close XAUUSD" | Đóng position theo symbol |
| `CLOSE HALF` | "close half" | Đóng 50% volume mỗi position |
| `MOVE SL <PRICE>` | "move sl 2030" | Di chuyển SL tất cả position |
| `BREAKEVEN` | "breakeven" | SL → entry trên position đang lãi |

> Nếu `cmd = None` → không phải command → chuyển sang Step 1 (parse signal bình thường)

---

### Step 1: Parse signal (dòng 545-577)
> Phần này giữ nguyên logic từ trước. Xem section UseCase để hiểu chi tiết.

---

### Dòng 515: Đọc chế độ chạy
```python
dry_run = self.settings.runtime.dry_run
```
- **Biến**: `dry_run` (bool)
- **Từ ENV**: `DRY_RUN=false`
- **Ý nghĩa**: `True` = không gửi lệnh thật, chỉ mô phỏng
- **Đổi →**: Toàn bộ logic MT5 bị skip, dùng giá giả

### Dòng 579-580: Lấy signal + fingerprint
```python
signal_obj: ParsedSignal = result      # Signal đã parse xong
fp = signal_obj.fingerprint[:12]       # Cắt 12 ký tự đầu để log gọn
```
- **`signal_obj`**: Chứa toàn bộ data signal (symbol, side, entry, sl, tp...)
- **`fp`**: Viết tắt fingerprint dùng trong log, 12 ký tự đủ unique
- **Đổi →**: Nếu đổi từ `[:12]` sang `[:8]` → chỉ ảnh hưởng log display, không ảnh hưởng logic

### Dòng 582-611: Log + DB events
```python
log_event("parse_success", fingerprint=fp, symbol=..., side=..., entry=...)
self.storage.store_event(fingerprint=fp, event_type="signal_received", ...)
self.storage.store_event(fingerprint=fp, event_type="signal_parsed", ...)
```
- **Ý nghĩa**: Ghi nhận lifecycle trong DB và log file
- **Đổi →**: Chỉ ảnh hưởng tracing/audit, KHÔNG ảnh hưởng trading logic

---

### Step 2: ⛔ CIRCUIT BREAKER CHECK (dòng 613-621)
```python
if not self.circuit_breaker.is_trading_allowed:
    reason = "circuit breaker OPEN — trading paused"
    return  # DỪNG pipeline
```

**Circuit Breaker là gì?**
- Bộ ngắt mạch an toàn: nếu N lệnh liên tiếp fail → TẠM DỪNG giao dịch
- 3 trạng thái: CLOSED (bình thường) → OPEN (tạm dừng) → HALF_OPEN (thử 1 lệnh)

**Biến liên quan:**
| Biến | File | Ý nghĩa |
|------|------|---------|
| `_threshold` | `circuit_breaker.py` | Từ ENV `CIRCUIT_BREAKER_THRESHOLD=3`. Bao nhiêu fail liên tiếp → OPEN |
| `_cooldown` | `circuit_breaker.py` | Từ ENV `CIRCUIT_BREAKER_COOLDOWN=300`. Bao lâu chờ trước khi thử lại (giây) |
| `_state` | `circuit_breaker.py` | State hiện tại: CLOSED/OPEN/HALF_OPEN |
| `_consecutive_failures` | `circuit_breaker.py` | Đếm số fail liên tiếp |

---

### Step 2b: ⛔ DAILY RISK GUARD CHECK (dòng 623-632)
```python
if self.daily_guard:
    allowed, guard_reason = self.daily_guard.is_trading_allowed
    if not allowed:
        return  # DỪNG pipeline
```

**Daily Risk Guard là gì? (P4)**
- Poll-based: đọc `MT5.history_deals_get()` mỗi `DAILY_RISK_POLL_MINUTES=5`
- 3 limits độc lập (mặc định 0 = disabled):

| ENV | Ý nghĩa | Ví dụ |
|-----|---------|-------|
| `MAX_DAILY_TRADES=10` | Max closed deals per UTC day | 10 lệnh/ngày |
| `MAX_DAILY_LOSS=100.0` | Max cumulative loss USD per day | Dừng khi lỗ $100 |
| `MAX_CONSECUTIVE_LOSSES=5` | Pause after N consecutive losses | 5 lần thua liên tiếp |

> File: `core/daily_risk_guard.py`. Chạy background, tự refresh counter. Gửi Telegram alert khi breach.

---

### Step 2c: ⛔ EXPOSURE GUARD CHECK (dòng 459-467)
```python
if self.exposure_guard:
    exp_allowed, exp_reason = self.exposure_guard.is_allowed(signal_obj.symbol)
    if not exp_allowed:
        return  # DỪNG pipeline
```

**Exposure Guard là gì? (P5)**
- Query live MT5 positions qua `TradeExecutor.get_position_symbols()` trên mỗi signal (không dùng stale counters)
- 2 limits:

| ENV | Ý nghĩa | Ví dụ |
|-----|---------|-------|
| `MAX_SAME_SYMBOL_TRADES=2` | Max open positions trên cùng symbol | Tối đa 2 lệnh XAUUSD |
| `MAX_CORRELATED_TRADES=3` | Max open positions trên nhóm tương quan | 3 lệnh metals (XAU+XAG) |

- `CORRELATION_GROUPS=XAUUSD:XAGUSD,EURUSD:GBPUSD:EURGBP`

> File: `core/exposure_guard.py`

---

### Step 3: DUPLICATE CHECK (dòng 469-473)
```python
is_dup = self.storage.is_duplicate(
    signal_obj.fingerprint,                          # SHA256 hash
    ttl_seconds=self.settings.safety.signal_age_ttl_seconds,  # ENV: 60s
)
```

**Logic SQL trong `storage.py`:**
```sql
SELECT COUNT(*) FROM signals
WHERE fingerprint = 'a1b2c3d4...'
  AND datetime(created_at) > datetime('now', '-60 seconds')
```

- **Ý nghĩa**: Cùng signal (cùng symbol+side+entry+sl+tp) trong 60 giây → coi là trùng
- **`is_dup` chỉ set cờ**, validator mới check reject (Rule 2)
- **Đổi `SIGNAL_AGE_TTL_SECONDS=300`:** Cửa sổ dedupe rộng 5 phút → signal gửi lại trong 5 phút bị reject

---

### Dòng 340-399: 📊 GET MARKET DATA (quan trọng nhất)

#### Mục tiêu: Lấy 7 giá trị

| Biến | Ý nghĩa | Dùng ở đâu |
|------|---------|------------|
| `bid` | Giá mua hiện tại | Order Builder (SELL reference) |
| `ask` | Giá bán hiện tại | Order Builder (BUY reference) |
| `current_price` | ask nếu BUY, bid nếu SELL | Validator (entry distance) |
| `current_spread` | Spread tính bằng points | Validator (spread gate) → cần chuyển pips |
| `open_positions` | Số lệnh đang mở | Validator (max trades) |
| `point` | Đơn vị nhỏ nhất của giá | Order Builder (tolerance) |
| `pip_size` | Size 1 pip tính bằng giá | Validator (entry distance) |

#### DRY_RUN mode (dòng 351-365):

```python
bid, ask, current_spread = self._simulate_tick(signal_obj)
current_price = ask if signal_obj.side == Side.BUY else bid
open_positions = 0
```

**`_simulate_tick()` (dòng 199-238):**
```python
def _simulate_tick(self, signal: ParsedSignal):
    spread = 0.5                    # default cho metals
    symbol = signal.symbol.upper()

    # Chọn spread giả theo loại symbol
    if any(fx in symbol for fx in ("USD","EUR","GBP","JPY","AUD","NZD","CAD","CHF")):
        spread = 0.0002             # forex pairs
    elif "XAU" in symbol or "GOLD" in symbol:
        spread = 0.5                # vàng: $0.50
    elif "BTC" in symbol or "ETH" in symbol:
        spread = 10.0               # crypto

    entry = signal.entry            # dùng entry signal làm giá gốc
    if entry is None:               # nếu MARKET → dùng SL/TP ước tính
        if signal.sl and signal.tp:
            entry = (signal.sl + signal.tp[0]) / 2
        elif signal.sl:
            entry = signal.sl + (50.0 * spread)
        elif signal.tp:
            entry = signal.tp[0] - (50.0 * spread)
        else:
            entry = 2000.0          # fallback

    if signal.side == Side.BUY:
        ask = entry                 # BUY: ask = entry → giá entry đúng giá ASK
        bid = entry - spread
    else:
        bid = entry                 # SELL: bid = entry
        ask = entry + spread

    spread_points = spread / (0.00001 if spread < 1 else 0.01)
    return bid, ask, spread_points
```

**Đổi `_simulate_tick()`:** Chỉ ảnh hưởng DRY_RUN mode, không ảnh hưởng LIVE.

#### Point/Pip_size ở DRY_RUN (dòng 356-365):
```python
if "XAU" in symbol or "GOLD" in symbol:
    point = 0.01        # XAUUSD: $0.01 per point
    pip_size = 0.1       # XAUUSD: $0.10 per pip (= 10 points)
elif "JPY" in symbol:
    point = 0.001        # JPY pairs: 3 digits
    pip_size = 0.01
else:
    point = 0.00001      # Forex: 5 digits
    pip_size = 0.0001     # Forex: 4th digit = 1 pip
```

#### LIVE mode (dòng 367-394):

```python
# Lấy point từ MT5
import MetaTrader5 as mt5
symbol_info = mt5.symbol_info(signal_obj.symbol)
point = symbol_info.point           # MT5 trả chính xác
digits = symbol_info.digits
if digits <= 3:
    pip_size = point * 10           # XAU: 0.01×10 = 0.1
else:
    pip_size = point * 10           # EUR: 0.00001×10 = 0.0001

# Lấy tick live
tick = self.executor.get_tick(signal_obj.symbol)
bid = tick.bid
ask = tick.ask
current_spread = tick.spread_points
current_price = ask if signal_obj.side == Side.BUY else bid

# Đếm lệnh đang mở
open_positions = self.executor.positions_total()
```

**`get_tick()` trong `trade_executor.py` (dòng 151-169):**
```python
def get_tick(self, symbol: str):
    tick = mt5.symbol_info_tick(symbol)     # Gọi MT5 API
    info = mt5.symbol_info(symbol)
    point = info.point if info else 0.00001
    spread_points = (tick.ask - tick.bid) / point  # Tính spread bằng points

    return TickData(bid=tick.bid, ask=tick.ask,
                    spread_points=spread_points, time=tick.time)
```

#### Dòng 397-399: Chuyển spread units
```python
current_spread_pips = None
if current_spread is not None:
    current_spread_pips = current_spread / 10.0  # 10 points = 1 pip
```
- **Ý nghĩa**: MT5 trả spread bằng **points**, validator cần **pips**
- **Công thức**: «1 pip = 10 points» cho mọi symbol (5-digit broker)
- **Ví dụ XAUUSD**: spread=50 points → 50/10 = 5 pips

---

### Step 5: ✅ VALIDATE (8 rules) (dòng 536-552)

```python
vr = self.validator.validate(
    signal_obj,                        # ParsedSignal
    current_price=current_price,       # ask/bid tùy side
    current_spread_pips=current_spread_pips,
    open_positions=open_positions,
    is_duplicate=is_dup,               # True/False từ Step 3
    pip_size=pip_size,                 # 0.1 (XAU), 0.0001 (EUR)
)
```

File: `core/signal_validator.py`

#### 8 Rules theo thứ tự ưu tiên (RULE ĐẦU FAIL → REJECT NGAY, KHÔNG CHECK TIẾP):

**Rule 1 — Required fields:**
```python
if not signal.symbol:    → REJECT "missing symbol"
if not signal.side:      → REJECT "missing side"
```
> Thực tế sau parse thành công thì luôn có symbol+side, nên rule này hiếm khi hit.

**Rule 2 — Duplicate:**
```python
if is_duplicate:
    → REJECT "duplicate signal (fingerprint: a1b2c3d4)"
```
> Dùng `is_dup` từ Step 3. Signal giống 100% trong TTL window → reject.

**Rule 3 — SL Coherence:**
```python
if signal.sl is None or signal.entry is None:
    → SKIP (không check nếu thiếu SL hoặc entry)

BUY: SL >= entry → REJECT "BUY signal SL (...) must be below entry (...)"
SELL: SL <= entry → REJECT "SELL signal SL (...) must be above entry (...)"
```

**Rule 4 — TP Coherence:**
```python
if not signal.tp or signal.entry is None:
    → SKIP

for mỗi TP:
    BUY: TP <= entry → REJECT "BUY signal TP1 (...) must be above entry (...)"
    SELL: TP >= entry → REJECT "SELL signal TP1 (...) must be below entry (...)"
```

**Rule 5 — Entry Distance (50 pips — all order types):**
```python
if current_price is not None and signal.entry is not None:
    raw_distance = abs(signal.entry - current_price)
    distance_pips = raw_distance / pip_size

    if distance_pips > max_entry_distance_pips:
        → REJECT "entry distance (X pips) exceeds max (50 pips)"
```

| Ví dụ | entry | price | pip_size | distance_pips | max=50 | Kết quả |
|-------|-------|-------|----------|---------------|--------|---------|
| XAUUSD | 2030 | 2035 | 0.1 | 50.0 | 50 | ✅ PASS (= limit) |
| XAUUSD | 2030 | 2036 | 0.1 | 60.0 | 50 | ❌ REJECT |
| EURUSD | 1.0800 | 1.0830 | 0.0001 | 30.0 | 50 | ✅ PASS |
| EURUSD | 1.0700 | 1.0830 | 0.0001 | 130.0 | 50 | ❌ REJECT |

**Rule 6 — Signal Age:**
```python
now = datetime.now(timezone.utc)
age_seconds = (now - signal.received_at).total_seconds()

if age_seconds > signal_age_ttl:     # ENV: 60s
    → REJECT "signal age (90s) exceeds TTL (60s)"
```
> Khi nào xảy ra: bot bị lag, queue tích tụ, hoặc reprocess signal cũ.

**Rule 7 — Spread Gate:**
```python
if current_spread_pips is not None:
    if spread_pips > max_spread_pips:   # ENV: 5.0
        → REJECT "spread (10.0 pips) exceeds max (5.0 pips)"
```

**Rule 8 — Max Open Trades:**
```python
if open_positions is not None:
    if open_count >= max_open_trades:   # ENV: 5
        → REJECT "max open trades reached (5/5)"
```

> ⚠️ **Lưu ý v0.9.0**: Ngoài 8 rules trong validator, pipeline còn có:
> - **Step 2b** (daily risk guard: max trades/loss/consecutive) chạy TRƯỚC validator
> - **Step 2c** (exposure guard: same symbol + correlation) chạy TRƯỚC validator
> - **Entry drift guard** (tight 10 pip guard for MARKET) chạy SAU validate, TRƯỚC pipeline execute
> - **Re-entry risk guards** (circuit breaker + daily + exposure) chạy mỗi lần RangeMonitor trigger
>
> Tổng cộng = **12+ lớp bảo vệ**.

---

### Step 6: Store signal (dòng 735-736)
```python
self.storage.store_signal(signal_obj, SignalStatus.PARSED)
```
- SQL: `INSERT INTO signals (fingerprint, symbol, side, entry, sl, tp, status='parsed', ...)`

---

### Step 7: 💰 CALCULATE VOLUME

> ⚠️ **v0.9.0 Note**: In P9, volume calculation is handled inside `SignalPipeline.execute_signal_plans()`. For `range`/`scale_in` modes, volume is split across entry levels by `EntryStrategy.split_volume()` (equal/pyramid/risk_based).

```python
if dry_run:
    balance = 10000.0                  # Giả lập $10,000
else:
    account = self.executor.account_info()
    balance = account["balance"]       # Balance thật từ MT5

volume = self.risk_manager.calculate_volume(
    balance=balance,
    entry=signal_obj.entry,
    sl=signal_obj.sl,
)
```

**`calculate_volume()` trong `risk_manager.py`:**

```python
# Mode 1: FIXED_LOT (mặc định)
if self._mode == "RISK_PERCENT":
    volume = self._risk_based_volume(balance, entry, sl, pip_value)
else:
    volume = self._fixed_lot     # ENV: FIXED_LOT_SIZE=0.01 → volume=0.01

return self._clamp_volume(volume)
```

**`_risk_based_volume()` (chỉ khi mode=RISK_PERCENT):**
```python
sl_distance = abs(entry - sl)          # |2030 - 2020| = 10.0
risk_amount = balance * (risk_percent / 100.0)  # 10000 × (1.0/100) = $100
volume = risk_amount / (sl_distance * pip_value) # 100 / (10 × 10) = 1.0 lot
```
> ⚠️ Hiện tại code gọi `calculate_volume(balance, entry, sl)` KHÔNG truyền `pip_value` → khi mode=RISK_PERCENT, `pip_value=None` → fallback về `_fixed_lot`.

**`_clamp_volume()`:**
```python
volume = math.floor(volume / lot_step) * lot_step  # Round xuống: 1.037 → 1.03
volume = max(lot_min, min(volume, lot_max))          # Clamp: [0.01, 100.0]
volume = round(volume, 2)                            # Fix floating point
```

---

### Step 8: 🎯 BUILD ORDER

> ⚠️ **v0.9.0 Note**: In P9, order building is done per-level inside `SignalPipeline`. Each level gets its own `decide_order_type()` → `build_request()` call with the level-specific price and volume.

```python
decision = self.order_builder.decide_order_type(signal_obj, bid, ask, point)
request = self.order_builder.build_request(
    signal_obj, decision, volume, bid, ask,
    spread_points=current_spread if current_spread else 0.0,
)
```

**`decide_order_type()` trong `order_builder.py`:**

```python
tolerance = self._tolerance * point
# ENV: MARKET_TOLERANCE_POINTS=5, point=0.01 (XAU)
# → tolerance = 5 × 0.01 = 0.05

if signal.side == Side.BUY:
    return self._decide_buy(signal, ask, tolerance)
else:
    return self._decide_sell(signal, bid, tolerance)
```

**Ma trận quyết định hoàn chỉnh với ví dụ số:**

```
═══ BUY ═══
ask = 2935.00, tolerance = 0.05

entry=None           → MARKET (mua ngay tại ask)
entry=2935.03        → |2935.03 - 2935.00| = 0.03 ≤ 0.05 → MARKET
entry=2930.00        → |2930 - 2935| = 5 > 0.05, entry < ask → BUY_LIMIT (chờ giá xuống)
entry=2940.00        → |2940 - 2935| = 5 > 0.05, entry > ask → BUY_STOP (chờ giá lên)

═══ SELL ═══
bid = 2934.50, tolerance = 0.05

entry=None           → MARKET (bán ngay tại bid)
entry=2934.47        → |2934.47 - 2934.50| = 0.03 ≤ 0.05 → MARKET
entry=2940.00        → |2940 - 2934.50| = 5.5 > 0.05, entry > bid → SELL_LIMIT (chờ giá lên)
entry=2930.00        → |2930 - 2934.50| = 4.5 > 0.05, entry < bid → SELL_STOP (chờ giá xuống)
```

**`build_request()` — tạo dict cho MT5 (v0.5.1 — dynamic deviation):**

```python
# Dynamic deviation: tự động widen slippage khi spread cao
effective_deviation = self.compute_deviation(spread_points)
# Nếu DYNAMIC_DEVIATION_MULTIPLIER=1.5, spread=50pts:
#   → max(20, 50×1.5) = max(20, 75) = 75
# Nếu DYNAMIC_DEVIATION_MULTIPLIER=0 (disabled):
#   → luôn trả về base_deviation = 20

request = {
    "symbol": "XAUUSD",
    "volume": 0.01,
    "sl": 2020.0,                # từ decision.sl
    "tp": 2040.0,                # từ decision.tp (chỉ TP1!)
    "deviation": effective_deviation,  # Dynamic! max(base, spread × multiplier)
    "magic": 234000,             # ENV: BOT_MAGIC_NUMBER
    "comment": "signal:a1b2c3d4",
}

# MARKET order:
request["action"] = mt5.TRADE_ACTION_DEAL
request["type"] = mt5.ORDER_TYPE_BUY     # hoặc SELL
request["price"] = ask                     # hoặc bid
request["type_filling"] = mt5.ORDER_FILLING_IOC

# PENDING order (LIMIT/STOP):
request["action"] = mt5.TRADE_ACTION_PENDING
request["type"] = mt5.ORDER_TYPE_BUY_LIMIT  # hoặc SELL_LIMIT, BUY_STOP, SELL_STOP
request["price"] = signal.entry              # giá entry signal
request["type_time"] = mt5.ORDER_TIME_GTC    # Good Till Cancelled
request["type_filling"] = mt5.ORDER_FILLING_RETURN
```

> ⚠️ **Chỉ dùng TP1!** `decision.tp = signal.tp[0] if signal.tp else None`. TP2, TP3 chỉ được log, không gửi MT5.

---

### Step 8b: ⛔ ENTRY DRIFT GUARD — chỉ cho MARKET orders (dòng 579-592)

```python
if decision.order_kind == OrderKind.MARKET and signal_obj.entry is not None:
    drift_result = self.validator.validate_entry_drift(
        signal_obj, current_price, pip_size
    )
    if not drift_result.valid:
        return  # REJECT
```

**Khi nào trigger?**
- Signal có entry price (VD: `BUY 2935`)
- Nhưng entry nằm trong tolerance → order_builder quyết định MARKET
- Trước khi execute, kiểm tra: entry đã drift quá xa chưa?

**Logic:**
```python
drift_pips = abs(signal.entry - current_price) / pip_size
if drift_pips > MAX_ENTRY_DRIFT_PIPS:   # ENV: 10.0
    → REJECT "entry drift (15.0 pips) exceeds max (10 pips)"
```

| Ví dụ | entry | current_price | pip_size | drift_pips | max=10 | Kết quả |
|-------|-------|---------------|----------|------------|--------|---------|
| XAUUSD | 2935 | 2935.5 | 0.1 | 5.0 | 10 | ✅ PASS |
| XAUUSD | 2935 | 2937 | 0.1 | 20.0 | 10 | ❌ REJECT |
| EURUSD | 1.0850 | 1.0845 | 0.0001 | 5.0 | 10 | ✅ PASS |

> **Tại sao cần Step 8b riêng?** Vì Rule 5 (entry distance) dùng limit rộng 50 pips, nhưng MARKET cần tight guard 10 pips. Nếu signal gửi entry=2935, giá đã xê dịch → vào MARKET tại 2937 thì drift=20 pips là nguy hiểm.

---

### Step 9: ⚡ EXECUTE

> ⚠️ **v0.9.0 Note**: In P9, execution is handled by `SignalPipeline`. For multi-order mode, each level is executed sequentially. Results are returned as a list of dicts to `main.py` for metrics tracking.

#### DRY_RUN (dòng 452-467):
```python
if dry_run:
    log_event("dry_run_execution", ...)
    self.storage.update_signal_status(fp, SignalStatus.EXECUTED)
    self.circuit_breaker.record_success()     # Luôn success trong dry run
    print(f"[PIPELINE] ... exec=DRY_RUN_OK vol={volume}")
```
→ Không gọi MT5, chỉ log + mark success.

#### LIVE (dòng 468-496):
```python
exec_result = self.executor.execute(request, fingerprint=fp)
```

**`execute()` trong `trade_executor.py` (dòng 214-317):**

```python
for attempt in range(1, max_retries + 1):     # 1, 2, 3
    result = mt5.order_send(request)

    if result is None:
        # MT5 không trả gì → retry
        sleep(retry_delay × attempt)           # 1s, 2s, 3s
        continue

    retcode = result.retcode

    # SUCCESS: 10008 (placed), 10009 (done), 10010 (done partial)
    if retcode in (10008, 10009, 10010):
        return ExecutionResult(success=True, retcode=retcode,
                               ticket=result.order)

    # RETRYABLE: 10004 (requote), 10020 (price changed),
    #            10021 (price off), 10024 (too many req), 10031 (connection)
    if retcode in (10004, 10020, 10021, 10024, 10031):
        sleep(retry_delay × attempt)
        continue

    # NON-RETRYABLE: invalid volume, invalid stops, etc.
    return ExecutionResult(success=False, retcode=retcode)

# Hết retry
return ExecutionResult(success=False, retcode=-1,
                       message="all retries exhausted")
```

**Sau execute:**
```python
if exec_result.success:
    circuit_breaker.record_success()        # Reset failure counter
    storage.update_signal_status(fp, EXECUTED)
    storage.store_order(ticket=..., success=True)
else:
    circuit_breaker.record_failure()        # Tăng failure counter
    storage.update_signal_status(fp, FAILED)
    storage.store_order(ticket=None, success=False)
```

---

### HỦY LỆNH PENDING: `order_lifecycle_manager.py`

Background loop chạy mỗi `LIFECYCLE_CHECK_INTERVAL_SECONDS=30`:

```python
def _check_and_expire(self):
    orders = self._executor.get_pending_orders()    # Lấy tất cả pending
    now = int(time.time())

    for order in orders:
        age = now - order["time_setup"]              # Tuổi lệnh (giây)
        if age > self._ttl_seconds:                  # ENV: 15×60=900s
            self._executor.cancel_order(order["ticket"])
```

**cancel_order() gọi MT5:**
```python
request = {"action": mt5.TRADE_ACTION_REMOVE, "order": ticket}
result = mt5.order_send(request)
success = result.retcode in (10008, 10009)
```

---

## 4. Bảng biến — ý nghĩa, file gốc, ảnh hưởng khi đổi

### Biến ENV ảnh hưởng trực tiếp đến chiến lược

| ENV | Giá trị | File sử dụng | Ảnh hưởng |
|-----|---------|-------------|-----------|
| `MAX_ENTRY_DISTANCE_PIPS` | 50.0 | `signal_validator.py` | Tăng → chấp nhận entry xa giá hơn |
| `MAX_ENTRY_DRIFT_PIPS` | 10.0 | `signal_validator.py` | Tight guard cho MARKET orders (Step 8b) |
| `MAX_SPREAD_PIPS` | 5.0 | `signal_validator.py` | Tăng → chấp nhận spread rộng hơn (⚠️ hiện tại bị comment out) |
| `MAX_OPEN_TRADES` | 5 | `signal_validator.py` | Tăng → đồng thời nhiều lệnh hơn |
| `SIGNAL_AGE_TTL_SECONDS` | 60 | `signal_validator.py`, `storage.py` | Tăng → chấp nhận signal cũ hơn + dedupe window rộng hơn |
| `MARKET_TOLERANCE_POINTS` | 5.0 | `order_builder.py` | Tăng → nhiều MARKET order hơn, ít LIMIT/STOP hơn |
| `DEVIATION_POINTS` | 20 | `order_builder.py` | Base slippage tolerance (trước dynamic) |
| `DYNAMIC_DEVIATION_MULTIPLIER` | 0.0 | `order_builder.py` | >0 → deviation = max(base, spread×multiplier). 0=disabled |
| `PENDING_ORDER_TTL_MINUTES` | 15 | `order_lifecycle_manager.py` | Tăng → lệnh pending sống lâu hơn |
| `RISK_MODE` | FIXED_LOT | `risk_manager.py` | Đổi sang RISK_PERCENT → lot size thay đổi theo balance |
| `FIXED_LOT_SIZE` | 0.01 | `risk_manager.py` | Tăng → rủi ro $ lớn hơn mỗi lệnh |
| `CIRCUIT_BREAKER_THRESHOLD` | 3 | `circuit_breaker.py` | Tăng → cho phép fail nhiều hơn |
| `MAX_DAILY_TRADES` | 0 | `daily_risk_guard.py` | Max closed deals per UTC day. 0=disabled |
| `MAX_DAILY_LOSS` | 0.0 | `daily_risk_guard.py` | Max realized loss USD per day. 0=disabled |
| `MAX_CONSECUTIVE_LOSSES` | 5 | `daily_risk_guard.py` | Pause after N consecutive losses. 0=disabled |
| `MAX_SAME_SYMBOL_TRADES` | 0 | `exposure_guard.py` | Max open positions on same symbol. 0=disabled |
| `MAX_CORRELATED_TRADES` | 0 | `exposure_guard.py` | Max open across correlation group. 0=disabled |
| `CORRELATION_GROUPS` | (empty) | `exposure_guard.py` | Groups: `XAUUSD:XAGUSD,EURUSD:GBPUSD` |
| `BREAKEVEN_TRIGGER_PIPS` | 0.0 | `position_manager.py` | Profit pips to trigger breakeven. 0=disabled |
| `TRAILING_STOP_PIPS` | 0.0 | `position_manager.py` | Trail SL at pip distance. 0=disabled |
| `PARTIAL_CLOSE_PERCENT` | 0 | `position_manager.py` | % volume to close at TP1. 0=disabled |
| `DRY_RUN` | false | `main.py` | true → không giao dịch thật |

### Biến nội bộ quan trọng trong pipeline (v0.9.0)

| Biến | Nơi tạo | Kiểu | Truyền cho | Ý nghĩa |
|------|---------|------|-----------|---------|
| `point` | `main.py:659` | float | `pipeline`, `order_builder` | Đơn vị giá nhỏ nhất (XAU=0.01, EUR=0.00001) |
| `pip_size` | `main.py:660` | float | `validator.validate()` | Size 1 pip (XAU=0.1, EUR=0.0001) |
| `bid` | `main.py:663/700` | float | `pipeline`, `order_builder` | Giá mua hiện tại |
| `ask` | `main.py:663/701` | float | `pipeline`, `order_builder` | Giá bán hiện tại |
| `current_price` | `main.py:664/703` | float | `validator` (entry distance) | = ask nếu BUY, bid nếu SELL |
| `current_spread_pips` | `main.py:709` | float | `validator` (spread gate) | Spread tính bằng pips |
| `is_dup` | `main.py:646` | bool | `validator` | Duplicate flag từ DB |
| `balance` | `main.py:742-745` | float | `pipeline.execute_signal_plans()` | Account balance (10000 dry-run) |
| `results` | `main.py:768` | list[dict] | metrics tracking | Danh sách kết quả execute (1 cho single, N cho multi) |
| `tolerance` | `order_builder.py:67` | float | internal | `MARKET_TOLERANCE_POINTS × point` |

---

## 5. Bản đồ: đổi dòng nào → ảnh hưởng cái nào

```
┌────────────────────────────────────────────────────────────────────┐
│  THAY ĐỔI entry_detector.py                                       │
│  (regex detect entry price)                                        │
│    ↓                                                               │
│  entry thay đổi                                                    │
│    ├→ fingerprint thay đổi (hash bao gồm entry)                  │
│    │    └→ duplicate check thay đổi                                │
│    ├→ SL coherence check: so sánh sl vs entry                     │
│    ├→ TP coherence check: so sánh tp vs entry                     │
│    ├→ entry distance check: |entry - price| thay đổi             │
│    ├→ order type decision: entry vs bid/ask thay đổi              │
│    │    └→ MARKET vs LIMIT vs STOP thay đổi                       │
│    └→ risk calculation: sl_distance = |entry - sl| thay đổi       │
│         └→ volume thay đổi (nếu RISK_PERCENT mode)                │
├────────────────────────────────────────────────────────────────────┤
│  THAY ĐỔI MARKET_TOLERANCE_POINTS (ENV)                           │
│    ↓                                                               │
│  tolerance = points × point thay đổi                               │
│    └→ Quyết định MARKET vs LIMIT/STOP thay đổi                    │
│         ├→ MARKET: vào ngay tại giá hiện tại                      │
│         └→ LIMIT/STOP: đặt pending, có thể bị hủy bởi lifecycle   │
├────────────────────────────────────────────────────────────────────┤
│  THAY ĐỔI MAX_ENTRY_DISTANCE_PIPS (ENV)                           │
│    ↓                                                               │
│  Chỉ ảnh hưởng duy nhất:                                          │
│    signal_validator._validate_entry_distance() dòng 223            │
│    → Nhiều/ít signal bị reject                                     │
├────────────────────────────────────────────────────────────────────┤
│  THAY ĐỔI pip_size logic (main.py dòng 348-379)                   │
│    ↓                                                               │
│  ├→ entry distance check (pips = distance/pip_size) thay đổi      │
│  └→ Validator dùng pip_size sai → reject/accept ngược              │
├────────────────────────────────────────────────────────────────────┤
│  THAY ĐỔI _decide_buy()/_decide_sell() (order_builder.py)         │
│    ↓                                                               │
│  ├→ Loại lệnh thay đổi (MARKET/LIMIT/STOP)                       │
│  ├→ build_request() tạo request khác (action, type, filling)      │
│  └→ executor nhận request khác → kết quả execution khác           │
├────────────────────────────────────────────────────────────────────┤
│  THAY ĐỔI executor.execute() retry logic                          │
│    ↓                                                               │
│  ├→ Retryable codes thay đổi → success rate thay đổi              │
│  └→ Circuit breaker nhận success/failure khác → state thay đổi    │
│       └→ Signal tiếp theo có thể bị block hoặc không              │
└────────────────────────────────────────────────────────────────────┘
```

---

## 6. Hướng dẫn Refactor chi tiết

### 6.1 Vấn đề hiện tại

`main.py` `_do_process_signal()` = **1 function khổng lồ 240 dòng** chứa:
- Get data logic
- Chiến lược vào lệnh
- Validation
- Risk calculation
- Order building
- Execution

→ Muốn đổi 1 thứ phải sờ vào cả function → rủi ro break.

### 6.2 Tách thành 3 interface pluggable

#### Interface 1: `IDataProvider` — Lấy data thị trường

```python
# core/interfaces.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class MarketSnapshot:
    bid: float
    ask: float
    spread_pips: float
    point: float
    pip_size: float
    open_positions: int
    balance: float

class IDataProvider(ABC):
    @abstractmethod
    def get_snapshot(self, symbol: str, side: str) -> MarketSnapshot: ...
```

**Hiện tại** (extract từ `main.py` dòng 340-399):
```python
class MT5DataProvider(IDataProvider):
    """Lấy data từ MT5 — logic hiện tại."""
    def get_snapshot(self, symbol, side):
        # Toàn bộ code dòng 366-394 move vào đây
        ...

class DryRunDataProvider(IDataProvider):
    """Simulate — logic _simulate_tick() hiện tại."""
    def get_snapshot(self, symbol, side):
        # Toàn bộ code dòng 351-365 move vào đây
        ...
```

**Tương lai**:
```python
class ExternalAPIDataProvider(IDataProvider):
    """Lấy data từ REST API khác (TradingView, cTrader...)"""

class AggregatedDataProvider(IDataProvider):
    """Combine nhiều nguồn data, chọn giá tốt nhất"""
```

#### Interface 2: `IEntryStrategy` — Quyết định vào lệnh

```python
@dataclass
class EntryDecision:
    should_enter: bool
    order_kind: OrderKind | None = None
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    volume: float = 0.0
    reject_reason: str = ""

class IEntryStrategy(ABC):
    @abstractmethod
    def evaluate(self, signal: ParsedSignal, snapshot: MarketSnapshot) -> EntryDecision: ...
```

**Hiện tại** (extract validator + order_builder + risk_manager):
```python
class SimpleEntryStrategy(IEntryStrategy):
    """Logic hiện tại — validate → calculate volume → decide order type."""
    def __init__(self, validator, risk_manager, order_builder):
        ...
    def evaluate(self, signal, snapshot):
        # Step 1: Validate (8 rules)
        vr = self._validator.validate(signal, snapshot.current_price, ...)
        if not vr.valid:
            return EntryDecision(should_enter=False, reject_reason=vr.reason)
        # Step 2: Volume
        volume = self._risk.calculate_volume(snapshot.balance, signal.entry, signal.sl)
        # Step 3: Order type
        decision = self._builder.decide_order_type(signal, snapshot.bid, snapshot.ask, snapshot.point)
        return EntryDecision(should_enter=True, order_kind=decision.order_kind, ...)
```

**Tương lai** — thêm chiến lược mới MÀ KHÔNG SỬA code cũ:
```python
class TrendFollowStrategy(IEntryStrategy):
    """Chỉ vào lệnh nếu signal cùng chiều trend H4."""
    def evaluate(self, signal, snapshot):
        # 1. Validate cơ bản
        # 2. Lấy H4 candles, tính trend
        # 3. BUY chỉ khi trend UP, SELL chỉ khi trend DOWN
        # 4. Volume theo ATR
        ...

class ScalperStrategy(IEntryStrategy):
    """Chỉ MARKET, không LIMIT/STOP, spread < 2 pips."""
    def evaluate(self, signal, snapshot):
        if snapshot.spread_pips > 2:
            return EntryDecision(should_enter=False, reject_reason="spread too wide for scalp")
        return EntryDecision(should_enter=True, order_kind=OrderKind.MARKET, ...)

class PartialEntryStrategy(IEntryStrategy):
    """Chia volume ra 3 lần vào, mỗi TP1 scale 33%."""
    ...
```

#### Interface 3: `ICancelStrategy` — Hủy lệnh

```python
class ICancelStrategy(ABC):
    @abstractmethod
    def should_cancel(self, order: dict, now: int) -> tuple[bool, str]: ...
```

**Hiện tại:**
```python
class TTLCancelStrategy(ICancelStrategy):
    """Hủy nếu quá thời gian — logic hiện tại."""
    def __init__(self, ttl_minutes: int):
        self._ttl = ttl_minutes * 60
    def should_cancel(self, order, now):
        age = now - order["time_setup"]
        if age > self._ttl:
            return True, f"expired after {age}s"
        return False, ""
```

**Tương lai:**
```python
class PriceReversalCancel(ICancelStrategy):
    """Hủy nếu giá đi ngược quá N pips."""

class NewsWindowCancel(ICancelStrategy):
    """Hủy tất cả pending trước tin tức quan trọng."""

class CompositeCancelStrategy(ICancelStrategy):
    """Kết hợp nhiều strategy — bất kỳ cái nào True → hủy."""
    def __init__(self, strategies: list[ICancelStrategy]):
        self._strategies = strategies
    def should_cancel(self, order, now):
        for s in self._strategies:
            cancel, reason = s.should_cancel(order, now)
            if cancel:
                return True, reason
        return False, ""
```

### 6.3 Pipeline mới sau refactor

```python
# main.py sau refactor
class Bot:
    def _init_components(self):
        # ... existing setup ...

        # Pluggable components
        if self.settings.runtime.dry_run:
            self.data_provider = DryRunDataProvider()
        else:
            self.data_provider = MT5DataProvider(self.executor)

        self.entry_strategy = SimpleEntryStrategy(
            self.validator, self.risk_manager, self.order_builder
        )
        self.cancel_strategy = TTLCancelStrategy(
            self.settings.safety.pending_order_ttl_minutes
        )

    def _do_process_signal(self, raw_text, chat_id, message_id):
        # Step 1: Parse (giữ nguyên)
        signal_obj = self.parser.parse(raw_text, chat_id, message_id)
        if isinstance(signal_obj, ParseFailure): return

        # Step 2: Circuit breaker (giữ nguyên)
        if not self.circuit_breaker.is_trading_allowed: return

        # Step 3: Get data (THAY THẾ 60 dòng → 1 dòng)
        snapshot = self.data_provider.get_snapshot(
            signal_obj.symbol, signal_obj.side.value
        )

        # Step 4: Strategy (THAY THẾ validate+risk+order_builder → 1 dòng)
        decision = self.entry_strategy.evaluate(signal_obj, snapshot)
        if not decision.should_enter: return

        # Step 5: Build + Execute (giữ nguyên)
        request = build_mt5_request(signal_obj, decision, snapshot)
        exec_result = self.executor.execute(request)
        ...
```

### 6.4 Cách thêm strategy mới (không sửa code cũ)

1. Tạo file `core/strategies/trend_follow.py`
2. Implement `IEntryStrategy`
3. Thêm vào `.env`: `ENTRY_STRATEGY=trend_follow`
4. Thêm case vào factory
5. **Không cần sửa `main.py`, `signal_validator.py`, `order_builder.py`**

### 6.5 Thứ tự refactor an toàn

| # | Task | Risk | Files |
|---|------|------|-------|
| 1 | Tạo `core/interfaces.py` với 3 abstract classes | LOW | 1 file mới |
| 2 | Tạo `MT5DataProvider` — extract logic từ main.py dòng 340-399 | MEDIUM | 1 file mới + sửa main.py |
| 3 | Tạo `DryRunDataProvider` — extract `_simulate_tick()` | LOW | 1 file mới + xóa method cũ |
| 4 | Tạo `SimpleEntryStrategy` — wrap validator+risk+builder | MEDIUM | 1 file mới |
| 5 | Tạo `TTLCancelStrategy` — extract từ lifecycle_manager | LOW | 1 file mới |
| 6 | Sửa `main.py` dùng interfaces | HIGH | sửa main.py |
| 7 | Thêm ENV `ENTRY_STRATEGY`, `DATA_PROVIDER` | LOW | settings.py + .env |

> ⚠️ **Mỗi bước = 1 PR riêng. Test DRY_RUN sau mỗi bước.**
