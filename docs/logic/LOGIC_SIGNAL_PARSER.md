# LOGIC: Signal Parsing Pipeline

> Mục đích: Giải thích CHI TIẾT cách tin nhắn Telegram được parse thành cấu trúc `ParsedSignal`.
> File này giúp bạn tự sửa đổi logic parse khi cần hỗ trợ format tín hiệu mới.
> **Version**: v0.9.0 | **Last updated**: 2026-03-21

---

## Tổng Quan Flow

```
Raw Telegram Text
  ↓
cleaner.clean()              → Chuẩn hóa text
  ↓
symbol_detector.detect()     → Tìm symbol (VD: XAUUSD)
  ↓
side_detector.detect()       → Tìm hướng (BUY/SELL)
  ↓
entry_detector.detect()      → Tìm giá entry (hoặc None = MARKET)
  ↓
sl_detector.detect()         → Tìm Stop Loss
  ↓
tp_detector.detect()         → Tìm Take Profit (có thể nhiều TP)
  ↓
generate_fingerprint()       → SHA-256 hash từ các field
  ↓
ParsedSignal                 → Kết quả cuối cùng
```

> **File điều phối**: `core/signal_parser/parser.py` → class `SignalParser`, method `_do_parse()` (dòng 100-158)

---

## Bước 1: Cleaner — Chuẩn Hóa Text

**File**: `core/signal_parser/cleaner.py`  
**Function**: `clean(raw_text, max_length)` (dòng 13-41)

### Hoạt động:

```
"🔥 Gold BUY @ 2030 🎯"  →  "GOLD BUY @ 2030"
```

| Bước | Dòng code | Hành động | Ảnh hưởng nếu thay đổi |
|------|-----------|-----------|------------------------|
| Guard | 26-27 | Reject nếu rỗng | — |
| Guard | 29-30 | Reject nếu `len > max_length` | Tăng `MAX_MESSAGE_LENGTH` cho phép tin nhắn dài hơn, nhưng có rủi ro regex chạy chậm |
| Strip emoji | 32 | Xóa emoji Unicode (category `So`, `Sk`, `Cs`) | Nếu bỏ bước này, emoji có thể gây lỗi regex ở detector |
| Strip non-print | 33 | Xóa ký tự điều khiển, giữ `\n` và `\t` | — |
| Uppercase | 34 | `text.upper()` | **BẮT BUỘC**: Toàn bộ regex detector đều match UPPERCASE |
| Normalize space | 35 | Gộp nhiều space, xóa dòng trống | — |

### ⚠️ Nếu bạn muốn thay đổi:
- **Tăng `MAX_MESSAGE_LENGTH`**: Sửa trong `.env` → `MAX_MESSAGE_LENGTH=5000`. Không cần sửa code.
- **Giữ emoji**: Xóa dòng 32 (`text = _strip_emoji(raw_text)`), nhưng phải kiểm tra tất cả regex downstream.

---

## Bước 2: Symbol Detector — Tìm Cặp Tiền

**File**: `core/signal_parser/symbol_detector.py`  
**Function**: `detect(text, mapper)` (dòng 20-54)

### Hoạt động:
```
"GOLD BUY @ 2030"  →  mapper.resolve("GOLD")  →  "XAUUSD"
"XAU/USD BUY"      →  "XAU" + "USD" → "XAUUSD"
```

### Logic chi tiết:

| Ưu tiên | Dòng code | Pattern | Ví dụ |
|---------|-----------|---------|-------|
| 1 | 38-43 | Slash-separated: `XAU/USD`, `EUR / USD` | `r"\b([A-Z]{2,5})\s*/\s*([A-Z]{2,5})\b"` |
| 2 | 46-50 | Uppercase token 3-10 ký tự | `GOLD`, `XAUUSD`, `EURUSD` |

### Alias Map:

**File**: `utils/symbol_mapper.py` (dòng 12-67)

```python
"GOLD"     → "XAUUSD"
"SILVER"   → "XAGUSD"
"BITCOIN"  → "BTCUSD"
"NASDAQ"   → "NAS100"
"WTI"      → "USOIL"
"BRENT"    → "UKOIL"
```

### ⚠️ Nếu bạn muốn thay đổi:
- **Thêm symbol mới**: Thêm vào `_DEFAULT_ALIASES` dict trong `utils/symbol_mapper.py:12-67`.
  - Ví dụ: Thêm `"PLATINUM": "XPTUSD"` → bot sẽ nhận diện "PLATINUM" từ tin nhắn.
- **Broker dùng hậu tố** (VD: `XAUUSD.raw`): Đổi value trong map thành `"XAUUSD.raw"`.
- **Symbol không nhận diện** → message bị reject với lý do `"symbol not detected"`.

---

## Bước 3: Side Detector — Tìm Hướng BUY/SELL

**File**: `core/signal_parser/side_detector.py`  
**Function**: `detect(text)` (dòng 28-43)

### Danh sách pattern (theo thứ tự ưu tiên):

| Ưu tiên | Pattern (dòng 14-25) | Match | Kết quả |
|---------|----------------------|-------|---------|
| 1 | `\bBUY\s*STOP\b` | "BUY STOP" | BUY |
| 2 | `\bBUY\s*LIMIT\b` | "BUY LIMIT" | BUY |
| 3 | `\bSELL\s*STOP\b` | "SELL STOP" | SELL |
| 4 | `\bSELL\s*LIMIT\b` | "SELL LIMIT" | SELL |
| 5 | `\bBUY\b` | "BUY" | BUY |
| 6 | `\bSELL\b` | "SELL" | SELL |
| 7 | `\bLONG\b` | "LONG" | BUY |
| 8 | `\bSHORT\b` | "SHORT" | SELL |

### ⚠️ Thứ tự RẤT QUAN TRỌNG:
- `BUY STOP` phải match **trước** `BUY`, nếu không "BUY STOP" chỉ match được `BUY`.
- Parser hiện tại **CHỈ TRẢ VỀ** `BUY` hoặc `SELL`. Thông tin LIMIT/STOP ở đây **KHÔNG DÙNG** cho quyết định order type — order type được quyết định ở `OrderBuilder` dựa trên giá live.

### ⚠️ Nếu bạn muốn thay đổi:
- **Thêm từ khóa mới**: Thêm tuple vào `_SIDE_PATTERNS` (dòng 14-25).
  - Ví dụ: `(re.compile(r"\bMUA\b"), "BUY")` → hỗ trợ tiếng Việt.
- **Không tìm thấy side** → message bị reject.

---

## Bước 4: Entry Detector — Tìm Giá Entry

**File**: `core/signal_parser/entry_detector.py`  
**Function**: `detect(text)` (dòng 28-65)

### Logic 3 tầng:

| Ưu tiên | Dòng code | Pattern | Ví dụ | Kết quả |
|---------|-----------|---------|-------|---------|
| 1 | 40-46 | Explicit patterns | `ENTRY 2030`, `@ 2030.50`, `PRICE: 2030` | `2030.0` |
| 2 | 49-50 | Market keywords | `NOW`, `MARKET`, `CMP`, `CURRENT PRICE` | `None` (= market) |
| 3 | 54-61 | Fallback: số ngay sau BUY/SELL | `BUY 2030`, `SELL 1.2050` | `2030.0` |

### Chi tiết các regex (dòng 15-20):

```python
r"\bENTRY\s*(?:PRICE)?\s*:?\s*(\d+\.?\d*)"   # ENTRY 2030, ENTRY PRICE: 2030.50
r"@\s*(\d+\.?\d*)"                              # @ 2030
r"\bPRICE\s*:?\s*(\d+\.?\d*)"                   # PRICE 2030, PRICE: 2030
r"\bENTER\s*(?:AT)?\s*:?\s*(\d+\.?\d*)"          # ENTER AT 2030
```

### Market Keywords (dòng 23-25):
```python
r"\b(?:NOW|MARKET|MARKET\s*(?:PRICE|EXECUTION)|CMP|CURRENT\s*(?:MARKET\s*)?PRICE)\b"
```

### ⚠️ QUAN TRỌNG:
- **`entry = None`** → bot sẽ gửi **MARKET ORDER** (mua/bán ngay ở giá hiện tại).
- **`entry = 2030.0`** → bot sẽ so sánh với giá live để quyết định LIMIT/STOP (xem file `LOGIC_TRADE_STRATEGY.md`).
- **Nếu cả 3 tầng đều không match** → `entry = None` → MARKET order.

### ⚠️ Nếu bạn muốn thay đổi:
- **Thêm pattern entry mới**: Thêm regex vào `_ENTRY_PATTERNS` list (dòng 15-20).
- **Bắt buộc phải có entry** (không cho market order): Trong `parser.py:132-133`, thêm check `if entry is None: return ParseFailure(...)`.

---

## Bước 5: SL Detector — Tìm Stop Loss

**File**: `core/signal_parser/sl_detector.py`  
**Function**: `detect(text)` (dòng 22-40)

### Các pattern (dòng 14-19):

| Pattern | Match | Ví dụ |
|---------|-------|-------|
| `\bSTOP\s*LOSS\s*:?\s*(\d+\.?\d*)` | STOP LOSS 2020 | 2020.0 |
| `\bSTOPLOSS\s*:?\s*(\d+\.?\d*)` | STOPLOSS: 2020 | 2020.0 |
| `\bSL\s*:?\s*(\d+\.?\d*)` | SL 2020, SL: 2020 | 2020.0 |
| `\bS/L\s*:?\s*(\d+\.?\d*)` | S/L 2020 | 2020.0 |

### ⚠️ Nếu bạn muốn thay đổi:
- **SL = None** hiện tại **KHÔNG bị reject** — lệnh sẽ được gửi không có SL. Nếu muốn **bắt buộc SL**, thêm check trong `signal_validator.py` hoặc `parser.py`.
- **SL bằng pip thay vì giá** (VD: "SL 30 pips"): Hiện tại KHÔNG hỗ trợ, chỉ nhận giá tuyệt đối.

---

## Bước 6: TP Detector — Tìm Take Profit

**File**: `core/signal_parser/tp_detector.py`  
**Function**: `detect(text)` (dòng 25-62)

### Logic 2 tầng:

| Ưu tiên | Dòng code | Pattern | Ví dụ | Kết quả |
|---------|-----------|---------|-------|---------|
| 1 | 37-46 | Numbered TP | `TP1 2040 TP2 2050 TP3 2060` | `[2040.0, 2050.0, 2060.0]` |
| 2 | 49-58 | Single TP | `TAKE PROFIT: 2040`, `T/P 2040`, `TP 2040` | `[2040.0]` |

### Regex chi tiết:

```python
# Numbered: TP1 2040, TP 2: 2050
r"\bTP\s*(\d)\s*:?\s*(\d+\.?\d*)"

# Single patterns (thứ tự ưu tiên):
r"\bTAKE\s*PROFIT\s*:?\s*(\d+\.?\d*)"
r"\bT/P\s*:?\s*(\d+\.?\d*)"
r"\bTP\s*:?\s*(\d+\.?\d*)"
```

### ⚠️ QUAN TRỌNG:
- Numbered TPs được **sort theo index** (TP1 trước TP2).
- Single TPs được **sort tăng dần theo giá trị** và **deduplicate**.
- **Chỉ có TP1** được dùng khi gửi lệnh MT5 (`signal.tp[0]`). Các TP còn lại hiện tại chỉ log, chưa quản lý partial close.
- **TP = []** (không có TP) → lệnh gửi với `tp = 0.0` (không có take profit).

### ⚠️ Nếu bạn muốn thay đổi:
- **Bắt buộc có ít nhất 1 TP**: Thêm check trong `parser.py` hoặc `signal_validator.py`.
- **Dùng TP cuối cùng** thay vì TP đầu tiên: Đổi `signal.tp[0]` thành `signal.tp[-1]` trong `order_builder.py:88,97,106,114,130,139,148,156`.

---

## Bước 7: Fingerprint — Tạo ID Duy Nhất

**File**: `core/signal_parser/parser.py`  
**Function**: `generate_fingerprint()` (dòng 20-39)

### Công thức:

```python
raw = "XAUUSD:BUY:2030.0:2020.0:2040.0|2050.0"
fingerprint = SHA256(raw)[:16]
# → "a3b2c1d4e5f67890"
```

### ⚠️ QUAN TRỌNG:
- Fingerprint dùng để **chống duplicate**: Cùng symbol + side + entry + SL + TP → cùng fingerprint → bị reject.
- **Nếu 2 signal giống nhau** nhưng entry khác 1 pip → fingerprint khác → không bị filter.
- TTL duplicate window: `SIGNAL_AGE_TTL_SECONDS` (default 60s).

---

## Kết Quả Cuối: ParsedSignal

**File**: `core/models.py`

```python
@dataclass
class ParsedSignal:
    symbol: str              # "XAUUSD"
    side: Side               # Side.BUY hoặc Side.SELL
    entry: float | None      # 2030.0 hoặc None (= MARKET)
    sl: float | None         # 2020.0 hoặc None
    tp: list[float]          # [2040.0, 2050.0] hoặc []
    fingerprint: str         # "a3b2c1d4e5f67890"
    raw_text: str            # Text gốc
    source_chat_id: str      # ID chat Telegram
    source_message_id: str   # ID message
    received_at: datetime    # Thời điểm nhận
    parse_confidence: float  # 0.0-1.0 (v0.6.0)
    parse_source: str        # Parser name (v0.6.0)
    entry_range: tuple[float, float] | None  # (2020, 2030) cho range signals (v0.9.0)
```

> **v0.6.0**: fingerprint bao gồm `source_chat_id` (breaking change).
> **v0.9.0**: `entry_range` được detect khi signal có dạng "BUY GOLD 2020-2030".
> Nếu `entry_range` khác None và channel strategy mode = `range` → `EntryStrategy` sẽ tạo nhiều entry plans.

---

## Tóm Tắt: Khi Nào Message Bị Reject?

| Lý do | File | Dòng |
|-------|------|----- |
| Rỗng hoặc quá dài | `cleaner.py` | 26-30 |
| Không tìm thấy symbol | `symbol_detector.py` → `parser.py` | 117-121 |
| Không tìm thấy BUY/SELL | `side_detector.py` → `parser.py` | 125-129 |
| Exception bất kỳ | `parser.py` | 94-98 |

> **Entry, SL, TP đều OPTIONAL** — message chỉ cần có `symbol + side` là parse thành công.
