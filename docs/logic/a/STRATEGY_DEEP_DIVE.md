# STRATEGY DEEP-DIVE — Toàn bộ luồng chiến lược vào lệnh

> **Version**: v0.3.2
> **Last updated**: 2026-03-15
> **Scope**: Giải thích chi tiết toàn bộ biến, function, luồng code liên quan đến **chiến lược giao dịch**, **quyết định vào lệnh**, **lấy data**, và **hủy lệnh**.

---

## Mục lục

1. [Tổng quan kiến trúc pipeline](#1-tổng-quan-kiến-trúc-pipeline)
2. [Tất cả biến ENV — ý nghĩa & ảnh hưởng](#2-tất-cả-biến-env--ý-nghĩa--ảnh-hưởng)
3. [Luồng code chạy (Flow chi tiết)](#3-luồng-code-chạy-flow-chi-tiết)
4. [Giải thích toàn bộ function theo từng file](#4-giải-thích-toàn-bộ-function-theo-từng-file)
5. [Bản đồ phụ thuộc — đổi dòng nào ảnh hưởng cái nào](#5-bản-đồ-phụ-thuộc--đổi-dòng-nào-ảnh-hưởng-cái-nào)
6. [Hướng dẫn Refactor — tùy biến linh hoạt chiến lược](#6-hướng-dẫn-refactor--tùy-biến-linh-hoạt-chiến-lược)

---

## 1. Tổng quan kiến trúc pipeline

```
Telegram Message
     │
     ▼
┌─────────────┐
│  Listener   │  ← telegram_listener.py: nhận tin nhắn từ Telegram
└──────┬──────┘
       │ raw_text, chat_id, message_id
       ▼
┌─────────────┐
│   Parser    │  ← signal_parser/parser.py: phân tích text → ParsedSignal
│  ┌────────┐ │
│  │Cleaner │ │  ← Bước 1: Làm sạch text (emoji, uppercase, whitespace)
│  │Symbol  │ │  ← Bước 2: Tìm symbol (XAUUSD, GOLD, EURUSD...)
│  │Side    │ │  ← Bước 3: Tìm hướng (BUY/SELL/LONG/SHORT)
│  │Entry   │ │  ← Bước 4: Tìm giá entry (hoặc MARKET)
│  │SL      │ │  ← Bước 5: Tìm Stop Loss
│  │TP      │ │  ← Bước 6: Tìm Take Profit (hỗ trợ multi-TP)
│  └────────┘ │
└──────┬──────┘
       │ ParsedSignal (symbol, side, entry, sl, tp[], fingerprint)
       ▼
┌─────────────────┐
│ Circuit Breaker  │  ← circuit_breaker.py: nếu OPEN → từ chối
└───────┬─────────┘
        ▼
┌─────────────┐
│  Duplicate  │  ← storage.py: kiểm tra fingerprint trùng trong TTL window
│   Check     │
└──────┬──────┘
       ▼
┌─────────────┐
│ Get Market  │  ← trade_executor.py: lấy bid/ask/spread/point từ MT5
│    Data     │     (hoặc simulate nếu DRY_RUN)
└──────┬──────┘
       ▼
┌─────────────┐
│  Validator  │  ← signal_validator.py: 8 rules kiểm tra an toàn
└──────┬──────┘
       ▼
┌─────────────┐
│    Risk     │  ← risk_manager.py: tính volume (lot size)
│  Manager    │
└──────┬──────┘
       ▼
┌──────────────┐
│ Order Builder│  ← order_builder.py: quyết định loại lệnh + build request
└──────┬───────┘
       ▼
┌─────────────┐
│  Executor   │  ← trade_executor.py: gửi lệnh lên MT5 (có retry)
└──────┬──────┘
       ▼
┌─────────────┐
│  Storage    │  ← storage.py: lưu kết quả vào SQLite
└─────────────┘
```

---

## 2. Tất cả biến ENV — ý nghĩa & ảnh hưởng

### 2.1 Telegram

| Biến | Giá trị mẫu | Ý nghĩa | Ảnh hưởng khi đổi |
|------|-------------|---------|-------------------|
| `TELEGRAM_API_ID` | `33243696` | ID ứng dụng Telegram (từ my.telegram.org) | Đổi → phải tạo lại session |
| `TELEGRAM_API_HASH` | `5162cb...` | Hash bí mật của app Telegram | Đổi → phải tạo lại session |
| `TELEGRAM_PHONE` | `+84329210528` | Số điện thoại đăng nhập Telegram | Đổi → login tài khoản khác |
| `TELEGRAM_SESSION_NAME` | `forex_bot` | Tên file session Telethon | Đổi → tạo session mới, phải xác thực lại |
| `TELEGRAM_SOURCE_CHATS` | `@shushutest1101` | Danh sách chat/channel để lắng nghe signal | **QUAN TRỌNG**: thêm/bớt channel → thay đổi nguồn signal |
| `TELEGRAM_ADMIN_CHAT` | *(trống)* | Chat ID để nhận cảnh báo (circuit breaker, MT5 mất kết nối) | Trống = không gửi alert |
| `SESSION_RESET_HOURS` | `12` | Mỗi N giờ tự reset session Telethon (tránh memory leak) | Tăng = ít reset hơn, có thể leak memory |

### 2.2 MetaTrader 5

| Biến | Giá trị mẫu | Ý nghĩa | Ảnh hưởng khi đổi |
|------|-------------|---------|-------------------|
| `MT5_PATH` | `C:\...\terminal64.exe` | Đường dẫn tới MT5 terminal | Sai path → `init_mt5()` fail |
| `MT5_LOGIN` | `10010081521` | Số tài khoản MT5 | Đổi = giao dịch trên tài khoản khác |
| `MT5_PASSWORD` | `5wLrU-Db` | Mật khẩu tài khoản | Sai → không login được |
| `MT5_SERVER` | `MetaQuotes-Demo` | Tên server broker | Đổi = kết nối server khác |

### 2.3 Risk Management — Quyết định khối lượng lệnh

| Biến | Giá trị mẫu | Ý nghĩa | Ảnh hưởng khi đổi |
|------|-------------|---------|-------------------|
| `RISK_MODE` | `FIXED_LOT` | Chế độ quản lý rủi ro: `FIXED_LOT` hoặc `RISK_PERCENT` | **CRITICAL**: đổi sang `RISK_PERCENT` = lot size tính theo % balance |
| `FIXED_LOT_SIZE` | `0.01` | Lot cố định khi mode = FIXED_LOT | Tăng = rủi ro lớn hơn mỗi lệnh |
| `RISK_PERCENT` | `0.05` | % balance rủi ro mỗi lệnh (khi mode=RISK_PERCENT) | 1% = $100 risk trên $10k balance |
| `LOT_MIN` | `0.01` | Lot tối thiểu broker cho phép | Nhỏ hơn broker min → bị clamp lên |
| `LOT_MAX` | `100.0` | Lot tối đa | Quá lớn = rủi ro cực kỳ |
| `LOT_STEP` | `0.01` | Bước lot (volume được round theo step này) | Thay đổi = thay đổi precision |

### 2.4 Safety Gates — Cửa an toàn quyết định TỪ CHỐI lệnh

> ⚠️ **ĐÂY LÀ NHÓM BIẾN QUAN TRỌNG NHẤT CHO CHIẾN LƯỢC VÀO LỆNH**

| Biến | Giá trị mẫu | Đơn vị | Ý nghĩa | Ảnh hưởng khi đổi |
|------|-------------|--------|---------|-------------------|
| `MAX_SPREAD_PIPS` | `5.0` | pips | Spread tối đa cho phép. XAUUSD: 5 pips = $0.50 | Tăng = chấp nhận spread rộng hơn, có thể slippage |
| `MAX_OPEN_TRADES` | `5` | count | Số lệnh mở tối đa cùng lúc | Tăng = nhiều lệnh hơn = nhiều exposure |
| `PENDING_ORDER_TTL_MINUTES` | `15` | minutes | Thời gian sống của lệnh pending. Quá TTL → tự hủy | Tăng = chờ lâu hơn cho entry price |
| `SIGNAL_AGE_TTL_SECONDS` | `60` | seconds | Signal quá N giây → từ chối (tránh vào lệnh trễ) | Tăng = chấp nhận signal cũ hơn |
| `MAX_ENTRY_DISTANCE_PIPS` | `50.0` | pips | Khoảng cách tối đa giữa entry và giá hiện tại. XAUUSD: 50 pips = $5.00 | Tăng = chấp nhận entry xa giá hơn |

### 2.5 Trade Execution — Cấu hình thực thi lệnh

| Biến | Giá trị mẫu | Ý nghĩa | Ảnh hưởng khi đổi |
|------|-------------|---------|-------------------|
| `BOT_MAGIC_NUMBER` | `234000` | ID duy nhất để nhận diện lệnh của bot trong MT5 | Đổi = không nhận diện được lệnh cũ |
| `DEVIATION_POINTS` | `20` | Slippage tối đa cho lệnh market (đơn vị: points) | Tăng = chấp nhận slippage nhiều hơn |
| `MARKET_TOLERANCE_POINTS` | `5.0` | Nếu \|entry - giá\| ≤ tolerance×point → vào lệnh MARKET thay vì LIMIT/STOP | **CRITICAL**: tăng = nhiều lệnh market hơn |
| `ORDER_MAX_RETRIES` | `3` | Số lần retry khi `order_send` fail | Tăng = kiên nhẫn hơn nhưng chậm hơn |
| `ORDER_RETRY_DELAY_SECONDS` | `1.0` | Delay giữa các retry (nhân với attempt number) | Tăng = chờ lâu hơn giữa retry |
| `WATCHDOG_INTERVAL_SECONDS` | `30` | MT5 health check mỗi N giây | Giảm = phát hiện mất kết nối nhanh hơn |
| `WATCHDOG_MAX_REINIT` | `5` | Số lần retry reconnect MT5 tối đa | Hết retry = cần can thiệp thủ công |
| `LIFECYCLE_CHECK_INTERVAL_SECONDS` | `30` | Quét pending orders mỗi N giây để hủy expired | Giảm = hủy nhanh hơn |

### 2.6 Runtime

| Biến | Giá trị mẫu | Ý nghĩa | Ảnh hưởng khi đổi |
|------|-------------|---------|-------------------|
| `DRY_RUN` | `false` | `true` = chế độ mô phỏng, không gửi lệnh thật | **CRITICAL**: `true` → KHÔNG giao dịch thật |
| `ALERT_COOLDOWN_SECONDS` | `300` | Rate limit alert (tránh spam cùng loại alert) | Giảm = nhiều alert hơn |
| `CIRCUIT_BREAKER_THRESHOLD` | `3` | Số lần fail liên tiếp → tạm dừng giao dịch | Tăng = cho phép fail nhiều hơn trước khi pause |
| `CIRCUIT_BREAKER_COOLDOWN` | `300` | Thời gian cooldown trước khi thử lại (giây) | Tăng = pause lâu hơn |
| `STORAGE_RETENTION_DAYS` | `30` | Tự xóa records cũ hơn N ngày | Giảm = tiết kiệm disk nhưng mất history |

### 2.7 Parser & Logging

| Biến | Giá trị mẫu | Ý nghĩa | Ảnh hưởng khi đổi |
|------|-------------|---------|-------------------|
| `MAX_MESSAGE_LENGTH` | `2000` | Tin nhắn dài hơn → bị reject (chống spam) | Tăng = chấp nhận message dài hơn |
| `LOG_LEVEL` | `INFO` | Level log: DEBUG / INFO / WARNING / ERROR | `DEBUG` = nhiều log chi tiết hơn |
| `LOG_FILE` | `logs/bot.log` | Đường dẫn file log | Đổi path = log ở chỗ khác |
| `LOG_ROTATION` | `10 MB` | Xoay file log khi đạt size | Tăng = file log lớn hơn trước khi rotate |

---

## 3. Luồng code chạy (Flow chi tiết)

### 3.1 Khởi động (`main.py` → `Bot.run()`)

```python
# 1. Load tất cả ENV settings
self.settings = load_settings()        # config/settings.py

# 2. Khởi tạo logger
setup_logger(level, file_path, rotation)

# 3. Khởi tạo Storage (SQLite)
self.storage = Storage()               # tạo/mở data/bot.db

# 4. Khởi tạo Parser
mapper = SymbolMapper()                # load alias map (GOLD→XAUUSD...)
self.parser = SignalParser(mapper, max_message_length)

# 5. Khởi tạo Validator
self.validator = SignalValidator(
    max_entry_distance_pips,           # từ ENV: MAX_ENTRY_DISTANCE_PIPS
    signal_age_ttl_seconds,            # từ ENV: SIGNAL_AGE_TTL_SECONDS
    max_spread_pips,                   # từ ENV: MAX_SPREAD_PIPS
    max_open_trades,                   # từ ENV: MAX_OPEN_TRADES
)

# 6. Khởi tạo Risk Manager
self.risk_manager = RiskManager(mode, fixed_lot_size, risk_percent, ...)

# 7. Khởi tạo Order Builder
self.order_builder = OrderBuilder(
    market_tolerance_points,           # từ ENV: MARKET_TOLERANCE_POINTS
    deviation,                         # từ ENV: DEVIATION_POINTS
    magic,                             # từ ENV: BOT_MAGIC_NUMBER
)

# 8. Khởi tạo Trade Executor
self.executor = TradeExecutor(mt5_path, login, password, server, max_retries, retry_delay)

# 9. Khởi tạo Circuit Breaker, Alerter, MessageUpdateHandler

# 10. Khởi tạo Telegram Listener → gắn callback _process_signal
self.listener.set_pipeline_callback(self._process_signal)

# 11. Khởi tạo Lifecycle Manager (hủy pending expired)
# 12. Khởi tạo MT5 Watchdog (health check)

# 13. Init MT5 (nếu không phải DRY_RUN)
# 14. Start Telegram listener
# 15. Start background services
# 16. Chờ signal...
```

### 3.2 Pipeline xử lý signal (`Bot._do_process_signal()`)

> File: `main.py`, dòng 259-496

```
┌──────────────────────────────────────────────────────────────────┐
│  STEP 1: PARSE (dòng 269-294)                                    │
│  ─────────────────────────────                                    │
│  parser.parse(raw_text, chat_id, message_id)                     │
│    → cleaner.clean()          # Xóa emoji, uppercase             │
│    → symbol_detector.detect() # Tìm symbol từ text              │
│    → side_detector.detect()   # Tìm BUY/SELL                    │
│    → entry_detector.detect()  # Tìm giá entry (hoặc None=MARKET)│
│    → sl_detector.detect()     # Tìm SL                          │
│    → tp_detector.detect()     # Tìm TP1, TP2, TP3...            │
│    → generate_fingerprint()   # SHA256(symbol:side:entry:sl:tp)  │
│                                                                   │
│  Kết quả: ParsedSignal hoặc ParseFailure                         │
│  Nếu FAIL → log + DB event + return                              │
├──────────────────────────────────────────────────────────────────┤
│  STEP 2: CIRCUIT BREAKER CHECK (dòng 327-332)                    │
│  ─────────────────────────────────────────────                    │
│  circuit_breaker.is_trading_allowed                               │
│    → CLOSED hoặc HALF_OPEN = cho phép                            │
│    → OPEN = từ chối → return                                      │
├──────────────────────────────────────────────────────────────────┤
│  STEP 3: DUPLICATE CHECK (dòng 335-338)                          │
│  ──────────────────────────────────────                           │
│  storage.is_duplicate(fingerprint, signal_age_ttl_seconds)       │
│    → SELECT COUNT FROM signals WHERE fingerprint=? AND age < TTL │
│    → Nếu trùng, sẽ bị reject ở validator                         │
├──────────────────────────────────────────────────────────────────┤
│  STEP 4: GET MARKET DATA (dòng 340-399)                          │
│  ──────────────────────────────────────                           │
│  **Đây là bước lấy data quan trọng nhất!**                       │
│                                                                   │
│  Nếu DRY_RUN:                                                    │
│    → _simulate_tick(signal) → bid, ask, spread giả               │
│    → Xác định point/pip_size theo symbol                          │
│                                                                   │
│  Nếu LIVE:                                                        │
│    → mt5.symbol_info() → lấy point, digits                        │
│    → executor.get_tick(symbol) → bid, ask, spread_points          │
│    → executor.positions_total() → đếm lệnh đang mở              │
│    → Chuyển spread từ points → pips (chia 10)                     │
│                                                                   │
│  Kết quả: bid, ask, current_price, current_spread_pips,          │
│           open_positions, point, pip_size                          │
├──────────────────────────────────────────────────────────────────┤
│  STEP 5: VALIDATE (dòng 401-416)                                 │
│  ────────────────────────────────                                 │
│  validator.validate(signal, current_price, spread_pips, ...)     │
│                                                                   │
│  8 RULES theo priority (đầu tiên fail → reject ngay):            │
│  1. Required fields: phải có symbol + side                       │
│  2. Duplicate: fingerprint trùng trong TTL window                │
│  3. SL coherence: BUY→SL<entry, SELL→SL>entry                   │
│  4. TP coherence: BUY→TP>entry, SELL→TP<entry                   │
│  5. Entry distance: |entry-price|/pip_size ≤ max_distance_pips   │
│  6. Signal age: tuổi signal ≤ TTL seconds                        │
│  7. Spread gate: spread ≤ max_spread_pips                        │
│  8. Max trades: open_positions < max_open_trades                 │
│                                                                   │
│  Nếu FAIL → store signal + return                                │
├──────────────────────────────────────────────────────────────────┤
│  STEP 6: STORE SIGNAL (dòng 418-419)                             │
│  ───────────────────────────────────                              │
│  storage.store_signal(signal, PARSED)                             │
├──────────────────────────────────────────────────────────────────┤
│  STEP 7: CALCULATE VOLUME (dòng 421-432)                         │
│  ───────────────────────────────────────                          │
│  Nếu DRY_RUN: balance = 10000                                    │
│  Nếu LIVE: balance = executor.account_info()["balance"]          │
│                                                                   │
│  risk_manager.calculate_volume(balance, entry, sl)               │
│    → FIXED_LOT: trả fixed_lot_size                               │
│    → RISK_PERCENT: risk_amount / (sl_distance * pip_value)       │
│    → _clamp_volume: round + min/max                               │
├──────────────────────────────────────────────────────────────────┤
│  STEP 8: BUILD ORDER (dòng 434-449)                              │
│  ──────────────────────────────────                               │
│  order_builder.decide_order_type(signal, bid, ask, point)        │
│    → Quyết định: MARKET / BUY_LIMIT / BUY_STOP / ...            │
│                                                                   │
│  order_builder.build_request(signal, decision, volume, bid, ask) │
│    → Dict request MT5-compatible                                  │
├──────────────────────────────────────────────────────────────────┤
│  STEP 9: EXECUTE (dòng 451-496)                                  │
│  ──────────────────────────────                                   │
│  Nếu DRY_RUN: log + mark EXECUTED + circuit_breaker.success()    │
│                                                                   │
│  Nếu LIVE:                                                        │
│    executor.execute(request, fingerprint)                         │
│      → mt5.order_send(request) — retry tối đa max_retries lần   │
│      → Retryable codes: requote, price changed, too many requests│
│      → Non-retryable: invalid volume, invalid stops, etc.        │
│                                                                   │
│    SUCCESS → circuit_breaker.record_success() + store order       │
│    FAIL    → circuit_breaker.record_failure() + store order       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Giải thích toàn bộ function theo từng file

### 4.1 `config/settings.py` — Load cấu hình

| Function | Ý nghĩa |
|----------|---------|
| `_env(key, default, required)` | Đọc env var, exit nếu required mà thiếu |
| `_env_int(key, default)` | Đọc env var → int, exit nếu không parse được |
| `_env_float(key, default)` | Đọc env var → float |
| `_env_list(key, default)` | Đọc env var → list (split bằng dấu phẩy) |
| `load_settings()` | Load toàn bộ `.env` → trả về `Settings` dataclass |

**Dataclasses**:
- `TelegramConfig` — cấu hình Telegram (api_id, api_hash, phone, source_chats...)
- `MT5Config` — cấu hình MT5 (path, login, password, server)
- `RiskConfig` — mode, fixed_lot_size, risk_percent, lot_min/max/step
- `SafetyConfig` — **max_spread_pips, max_open_trades, pending_order_ttl_minutes, signal_age_ttl_seconds, max_entry_distance_pips**
- `ExecutionConfig` — magic number, deviation, tolerance, retries, watchdog intervals
- `RuntimeConfig` — dry_run, alert cooldown, circuit breaker params
- `LogConfig` — level, file, rotation
- `ParserConfig` — max_message_length

### 4.2 `core/models.py` — Data contracts

| Class/Enum | Ý nghĩa | Dùng ở đâu |
|------------|---------|------------|
| `Side` | BUY hoặc SELL | Parser → tất cả pipeline |
| `OrderKind` | MARKET, BUY_LIMIT, BUY_STOP, SELL_LIMIT, SELL_STOP | OrderBuilder → Executor |
| `SignalStatus` | received → parsed → submitted → executed/failed/rejected | Storage lifecycle |
| `ParsedSignal` | **Kết quả parse**: symbol, side, entry, sl, tp[], fingerprint, received_at... | Parser output → toàn bộ pipeline |
| `ParseFailure` | Kết quả khi parse thất bại: reason, raw_text | Parser output → log & skip |
| `TradeDecision` | **Quyết định lệnh**: order_kind, price, sl, tp | OrderBuilder → Executor |
| `ExecutionResult` | Kết quả execution: success, retcode, ticket, message | Executor → main pipeline |

### 4.3 `core/signal_parser/cleaner.py` — Làm sạch text

| Function | Ý nghĩa |
|----------|---------|
| `clean(raw_text, max_length)` | Pipeline: reject empty/long → strip emoji → uppercase → collapse whitespace |
| `_strip_emoji(text)` | Xóa ký tự emoji (Unicode category So, Sk, Cs) |
| `_strip_non_printable(text)` | Xóa ký tự control (giữ newline, tab) |
| `_normalize_whitespace(text)` | Tab→space, nhiều space→1 space, xóa dòng trống |

### 4.4 `core/signal_parser/symbol_detector.py` — Phát hiện symbol

| Function | Ý nghĩa |
|----------|---------|
| `detect(text, mapper)` | Tìm symbol: thử "XAU/USD" format trước → tìm token uppercase 3-10 ký tự → resolve qua `SymbolMapper` |

**Regex quan trọng**:
- `\b([A-Z]{3,10})\b` — tìm word toàn chữ hoa 3-10 ký tự
- `\b([A-Z]{2,5})\s*/\s*([A-Z]{2,5})\b` — tìm dạng "XAU/USD"

### 4.5 `core/signal_parser/side_detector.py` — Phát hiện hướng

| Function | Ý nghĩa |
|----------|---------|
| `detect(text)` | Scan 8 patterns theo thứ tự ưu tiên, trả "BUY" hoặc "SELL" |

**Patterns theo priority**:
1. `BUY STOP` → BUY
2. `BUY LIMIT` → BUY
3. `SELL STOP` → SELL
4. `SELL LIMIT` → SELL
5. `BUY` → BUY
6. `SELL` → SELL
7. `LONG` → BUY
8. `SHORT` → SELL

### 4.6 `core/signal_parser/entry_detector.py` — Phát hiện giá entry

| Function | Ý nghĩa |
|----------|---------|
| `detect(text)` | Tìm entry price, trả `float` hoặc `None` (=MARKET) |

**Strategy tìm entry (theo thứ tự)**:
1. Pattern: `ENTRY 2030`, `ENTRY PRICE: 2030.50`, `@ 2030`, `PRICE: 2030`, `ENTER AT 2030`
2. Nếu không tìm thấy số → kiểm tra keyword MARKET: `NOW`, `MARKET`, `CMP`, `CURRENT PRICE`
3. Fallback: tìm `BUY 2030` hoặc `SELL 2030`
4. Nếu không tìm được gì → `None` (vào lệnh MARKET)

### 4.7 `core/signal_parser/sl_detector.py` — Phát hiện SL

| Function | Ý nghĩa |
|----------|---------|
| `detect(text)` | Tìm SL price, trả `float` hoặc `None` |

**Patterns**: `STOP LOSS: 2020`, `STOPLOSS 2020`, `SL: 2020`, `S/L 2020`

### 4.8 `core/signal_parser/tp_detector.py` — Phát hiện TP

| Function | Ý nghĩa |
|----------|---------|
| `detect(text)` | Tìm danh sách TP, trả `list[float]` sorted ascending |

**Strategy**:
1. Tìm numbered TPs: `TP1 2040`, `TP2 2050`, `TP3 2060` → sort theo index
2. Nếu không có numbered → tìm single: `TAKE PROFIT 2040`, `T/P 2040`, `TP 2040`

### 4.9 `core/signal_parser/parser.py` — Orchestrator

| Function | Ý nghĩa |
|----------|---------|
| `generate_fingerprint(symbol, side, entry, sl, tp_list)` | SHA256 hash từ signal fields normalized → chuỗi 16 ký tự |
| `SignalParser.parse(raw_text, ...)` | Điều phối 6 bước parse, exception-safe |
| `SignalParser._do_parse(raw_text, common)` | Logic thực tế: clean → symbol → side → entry → sl → tp → fingerprint |

### 4.10 `core/signal_validator.py` — 8 quy tắc an toàn

| Function | Ý nghĩa | Rule # |
|----------|---------|--------|
| `validate(signal, current_price, spread_pips, open_positions, is_duplicate, pip_size)` | Chạy tất cả 8 rules. Trả `ValidationResult(valid, reason)` | All |
| `_validate_spread(spread_pips)` | `spread > max_spread_pips` → reject | 7 |
| `_validate_max_trades(open_count)` | `open >= max_open_trades` → reject | 8 |
| `_validate_sl_coherence(signal)` | BUY: SL phải < entry. SELL: SL phải > entry | 3 |
| `_validate_tp_coherence(signal)` | BUY: TP phải > entry. SELL: TP phải < entry | 4 |
| `_validate_entry_distance(signal, current_price, pip_size)` | `|entry - price| / pip_size > max_distance_pips` → reject | 5 |
| `_validate_signal_age(signal)` | `(now - received_at).seconds > ttl` → reject | 6 |

**pip_size giải thích**:
- **XAUUSD**: pip_size = 0.1 → entry=2030, price=2035 → distance = 5.0/0.1 = 50 pips
- **EURUSD**: pip_size = 0.0001 → entry=1.0800, price=1.0850 → distance = 0.005/0.0001 = 50 pips

### 4.11 `core/risk_manager.py` — Tính volume

| Function | Ý nghĩa |
|----------|---------|
| `calculate_volume(balance, entry, sl, pip_value)` | Entry point: chọn mode → tính → clamp |
| `_risk_based_volume(balance, entry, sl, pip_value)` | `risk_amount = balance × (risk_percent/100)` → `volume = risk_amount / (|entry-sl| × pip_value)` |
| `_clamp_volume(volume)` | Floor xuống lot_step → clamp [lot_min, lot_max] → round |

### 4.12 `core/order_builder.py` — Quyết định loại lệnh

| Function | Ý nghĩa |
|----------|---------|
| `decide_order_type(signal, bid, ask, point)` | **CORE**: So sánh entry vs giá live → trả `TradeDecision` |
| `_decide_buy(signal, ask, tolerance)` | BUY logic: entry=None→MARKET, \|entry-ask\|≤tol→MARKET, entry<ask→LIMIT, entry>ask→STOP |
| `_decide_sell(signal, bid, tolerance)` | SELL logic: entry=None→MARKET, \|entry-bid\|≤tol→MARKET, entry>bid→LIMIT, entry<bid→STOP |
| `build_request(signal, decision, volume, bid, ask)` | Xây dict request cho MT5: action, type, symbol, volume, sl, tp, deviation, magic |

**Ma trận quyết định đầy đủ**:

```
BUY:
  entry = None           → MARKET (giá ask hiện tại)
  |entry - ask| ≤ tol    → MARKET (gần giá hiện tại)
  entry < ask            → BUY_LIMIT (đặt chờ mua giá thấp hơn)
  entry > ask            → BUY_STOP (đặt chờ mua giá cao hơn)

SELL:
  entry = None           → MARKET (giá bid hiện tại)
  |entry - bid| ≤ tol    → MARKET (gần giá hiện tại)
  entry > bid            → SELL_LIMIT (đặt chờ bán giá cao hơn)
  entry < bid            → SELL_STOP (đặt chờ bán giá thấp hơn)

tolerance = MARKET_TOLERANCE_POINTS × point
  → XAUUSD: 5 × 0.01 = $0.05 = 0.5 pips
  → EURUSD: 5 × 0.00001 = 0.00005
```

### 4.13 `core/trade_executor.py` — Thực thi lệnh

| Function | Ý nghĩa |
|----------|---------|
| `init_mt5()` | Khởi tạo MetaTrader5 + login → True/False |
| `shutdown()` | Đóng kết nối MT5 |
| `get_tick(symbol)` | Lấy tick: bid, ask, spread_points, time |
| `check_symbol(symbol)` | Đảm bảo symbol visible + tradeable trong MT5 |
| `positions_total()` | Đếm tổng positions đang mở |
| `account_info()` | Lấy info: login, server, balance, equity, margin |
| `execute(request, fingerprint)` | **CORE**: Gửi lệnh → retry nếu retryable → trả `ExecutionResult` |
| `get_pending_orders(symbol)` | Lấy danh sách pending orders |
| `cancel_order(ticket, fingerprint)` | Hủy pending order theo ticket |

**Retry logic**:
- Thử tối đa `max_retries` lần (mặc định 3)
- **Retryable codes**: 10004 (requote), 10020 (price changed), 10021 (price off), 10024 (too many requests), 10031 (connection)
- **Success codes**: 10008 (placed), 10009 (done), 10010 (done partial)
- Delay = `retry_delay × attempt_number` (linear backoff)

### 4.14 `core/storage.py` — Lưu trữ SQLite

| Function | Ý nghĩa |
|----------|---------|
| `store_signal(signal, status)` | INSERT signal vào bảng signals |
| `update_signal_status(fingerprint, status)` | UPDATE status WHERE fingerprint |
| `is_duplicate(fingerprint, ttl_seconds)` | COUNT signals WHERE fingerprint trong TTL window |
| `store_order(ticket, fingerprint, ...)` | INSERT order result vào bảng orders |
| `store_event(fingerprint, event_type, ...)` | INSERT lifecycle event |
| `cleanup_old_records(retention_days)` | DELETE WHERE age > retention_days |

**3 bảng**:
- `signals` — fingerprint, symbol, side, entry, sl, tp, status, raw_text, timestamps
- `orders` — ticket, fingerprint, order_kind, price, sl, tp, retcode, success
- `events` — fingerprint, event_type, symbol, details (JSON), timestamp

### 4.15 `core/circuit_breaker.py` — An toàn khi lỗi liên tiếp

| Function | Ý nghĩa |
|----------|---------|
| `state` (property) | Trả state hiện tại + auto-transition OPEN→HALF_OPEN khi cooldown hết |
| `is_trading_allowed` (property) | CLOSED hoặc HALF_OPEN = True |
| `record_success()` | HALF_OPEN→CLOSED, reset failure counter |
| `record_failure()` | Tăng failure counter, ≥threshold→OPEN |
| `on_state_change(callback)` | Đăng ký callback khi state thay đổi |

**State machine**:
```
CLOSED ──(N fails)──► OPEN ──(cooldown)──► HALF_OPEN ──(1 success)──► CLOSED
                                               │
                                          (1 fail)
                                               │
                                               ▼
                                             OPEN
```

### 4.16 `core/order_lifecycle_manager.py` — Hủy lệnh pending hết hạn

| Function | Ý nghĩa |
|----------|---------|
| `start()` | Bắt đầu vòng lặp monitor |
| `stop()` | Dừng monitor |
| `_monitor_loop()` | Mỗi `check_interval_seconds`: gọi `_check_and_expire()` |
| `_check_and_expire()` | Lấy pending orders → so sánh age vs TTL → cancel expired |

### 4.17 `core/mt5_watchdog.py` — Giám sát kết nối MT5

| Function | Ý nghĩa |
|----------|---------|
| `_health_check()` | Gọi `account_info()`, nếu null → connection lost |
| `_is_market_closed()` | Saturday/Sunday UTC → bỏ qua false alarm |
| `_attempt_reinit()` | shutdown() → sleep (exponential backoff) → init_mt5() |

### 4.18 `core/telegram_listener.py` — Nhận signal

| Function | Ý nghĩa |
|----------|---------|
| `start()` | Kết nối Telegram, đăng ký handlers |
| `_connect()` | Tạo TelegramClient, resolve chat entities, đăng ký `NewMessage` + `MessageEdited` |
| `_handle_new_message(event)` | Gọi `_pipeline_cb(raw_text, chat_id, message_id)` |
| `_handle_edited_message(event)` | Gọi `_edit_cb(raw_text, chat_id, message_id)` |
| `run_until_disconnected()` | Chạy vô hạn, auto-reconnect with exponential backoff (max 10 retries) |
| `_session_reset_loop()` | Mỗi N giờ: disconnect → reconnect |

### 4.19 `utils/symbol_mapper.py` — Map alias

| Function | Ý nghĩa |
|----------|---------|
| `resolve(alias)` | Map "GOLD" → "XAUUSD", "BITCOIN" → "BTCUSD", etc. |
| `is_known(alias)` | Kiểm tra alias có trong map |

Alias map bao gồm: Metals, Major forex, Cross pairs, Indices, Oil, Crypto.

### 4.20 `utils/logger.py` — Logging

| Function | Ý nghĩa |
|----------|---------|
| `setup_logger(level, file_path, rotation)` | Cấu hình 2 sinks: console (human-readable) + file (JSON structured) |
| `log_event(event, fingerprint, symbol, **extra)` | Log structured event với timestamp UTC |

---

## 5. Bản đồ phụ thuộc — đổi dòng nào ảnh hưởng cái nào

### 5.1 Biến ENV → Code bị ảnh hưởng

```
MAX_SPREAD_PIPS ─────────── ► signal_validator._validate_spread()
                             ► main.py banner display

MAX_ENTRY_DISTANCE_PIPS ──── ► signal_validator._validate_entry_distance()
                             ► main.py banner display

SIGNAL_AGE_TTL_SECONDS ───── ► signal_validator._validate_signal_age()
                             ► storage.is_duplicate() (TTL window)
                             ► main.py banner display

MAX_OPEN_TRADES ──────────── ► signal_validator._validate_max_trades()
                             ► main.py banner display

PENDING_ORDER_TTL_MINUTES ── ► order_lifecycle_manager._check_and_expire()
                             ► main.py banner display

MARKET_TOLERANCE_POINTS ──── ► order_builder.decide_order_type()
                               tolerance = MARKET_TOLERANCE_POINTS × point
                               → Quyết định MARKET vs LIMIT vs STOP

DEVIATION_POINTS ─────────── ► order_builder.build_request() → request["deviation"]
                               → MT5: max slippage cho phép

BOT_MAGIC_NUMBER ─────────── ► order_builder.build_request() → request["magic"]
                               → MT5: nhận diện lệnh bot

RISK_MODE ────────────────── ► risk_manager.calculate_volume()
  FIXED_LOT_SIZE ───────────    → Nếu FIXED_LOT: dùng fixed
  RISK_PERCENT ─────────────    → Nếu RISK_PERCENT: tính theo balance

DRY_RUN ──────────────────── ► main.py: toàn bộ pipeline
                               → Nếu true: simulate tick, skip MT5 init,
                                 balance=10000, không gửi lệnh thật

CIRCUIT_BREAKER_THRESHOLD ── ► circuit_breaker.record_failure()
CIRCUIT_BREAKER_COOLDOWN ─── ► circuit_breaker._transition() → auto HALF_OPEN
```

### 5.2 Function → Function dependency

```
_do_process_signal()
  ├── parser.parse()
  │     ├── cleaner.clean()
  │     ├── symbol_detector.detect()
  │     │     └── SymbolMapper.resolve()
  │     ├── side_detector.detect()
  │     ├── entry_detector.detect()
  │     ├── sl_detector.detect()
  │     ├── tp_detector.detect()
  │     └── generate_fingerprint()
  │
  ├── circuit_breaker.is_trading_allowed
  │     └── circuit_breaker.state (property)
  │
  ├── storage.is_duplicate()
  │
  ├── executor.get_tick()          ◄── chỉ LIVE mode
  │     └── mt5.symbol_info_tick()
  │
  ├── validator.validate()
  │     ├── _validate_sl_coherence()
  │     ├── _validate_tp_coherence()
  │     ├── _validate_entry_distance()
  │     ├── _validate_signal_age()
  │     ├── _validate_spread()
  │     └── _validate_max_trades()
  │
  ├── risk_manager.calculate_volume()
  │     ├── _risk_based_volume()
  │     └── _clamp_volume()
  │
  ├── order_builder.decide_order_type()
  │     ├── _decide_buy()
  │     └── _decide_sell()
  │
  ├── order_builder.build_request()
  │
  └── executor.execute()           ◄── chỉ LIVE mode
        └── mt5.order_send()
```

### 5.3 Thay đổi → Hiệu ứng lan truyền

| Thay đổi | Hiệu ứng trực tiếp | Hiệu ứng gián tiếp |
|----------|-------------------|-------------------|
| Sửa `entry_detector.py` regex | Thay đổi cách detect entry price | → Thay đổi entry → Thay đổi fingerprint → Thay đổi duplicate logic → Thay đổi entry distance validation → Thay đổi order type decision |
| Sửa `side_detector.py` | Thay đổi cách detect BUY/SELL | → Thay đổi SL/TP coherence check → Thay đổi order type → Thay đổi bid/ask reference |
| Sửa `symbol_mapper.py` alias map | Thay đổi symbol mapping | → Thay đổi fingerprint → Thay đổi point/pip_size → Thay đổi spread/distance validation |
| Sửa `signal_validator.py` rules | Thay đổi signal nào bị reject | → Ít/nhiều signal pass → Nhiều/ít lệnh được vào |
| Sửa `order_builder.py` tolerance | Thay đổi ngưỡng MARKET vs LIMIT | → Nhiều/ít MARKET trades → Thay đổi execution speed |
| Sửa `risk_manager.py` formula | Thay đổi lot size | → Trực tiếp ảnh hưởng $ risk mỗi lệnh |
| Sửa `trade_executor.py` retry codes | Thay đổi code nào được retry | → Nhiều/ít retry → Thay đổi success rate |

---

## 6. Hướng dẫn Refactor — tùy biến linh hoạt chiến lược

### 6.1 Vấn đề hiện tại

Hiện tất cả logic nằm cứng trong `Bot._do_process_signal()` — một function 240 dòng chạy tuần tự. Nếu muốn:
- Thêm chiến lược mới (vd: multi-timeframe)
- Thay đổi điều kiện vào lệnh
- Lấy data từ nguồn khác (không chỉ MT5 tick)
- Thêm logic hủy lệnh phức tạp

→ Phải sửa trực tiếp `main.py` → rủi ro cao, khó mở rộng.

### 6.2 Kiến trúc refactor đề xuất: Strategy Pattern + Pipeline Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                     NEW ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ IDataProvider│     │ IStrategy    │     │ IOrderCancel │    │
│  │  (interface) │     │  (interface) │     │  (interface)  │    │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘    │
│         │                    │                     │             │
│    ┌────┴────┐         ┌─────┴─────┐        ┌─────┴─────┐      │
│    │MT5Data  │         │SimpleEntry│        │TTLCancel  │      │
│    │Provider │         │Strategy   │        │Strategy   │      │
│    ├─────────┤         ├───────────┤        ├───────────┤      │
│    │MockData │         │MultiTF    │        │PriceCancel│      │
│    │Provider │         │Strategy   │        │Strategy   │      │
│    ├─────────┤         ├───────────┤        └───────────┘      │
│    │APIData  │         │Scalper    │                            │
│    │Provider │         │Strategy   │                            │
│    └─────────┘         └───────────┘                            │
│                                                                  │
│  Pipeline: DataProvider → Strategy → Validator → Risk → Execute │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 Bước 1: Tạo interface cho Data Provider

```python
# core/interfaces/data_provider.py [NEW]
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class MarketSnapshot:
    """Tất cả data cần thiết cho quyết định vào lệnh."""
    bid: float
    ask: float
    spread_pips: float
    point: float
    pip_size: float
    open_positions: int
    balance: float
    current_price: float  # ask for BUY, bid for SELL


class IDataProvider(ABC):
    """Interface lấy market data — có thể thay thế nguồn data."""

    @abstractmethod
    def get_snapshot(self, symbol: str, side: str) -> MarketSnapshot:
        """Lấy snapshot thị trường cho symbol + side."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Kiểm tra data provider có sẵn sàng."""
        ...
```

**Implementations**:
- `MT5DataProvider` — lấy từ MT5 (logic hiện tại)
- `DryRunDataProvider` — simulate (logic `_simulate_tick()` hiện tại)
- `APIDataProvider` — lấy từ REST API bên ngoài (tương lai)

### 6.4 Bước 2: Tạo interface cho Strategy (quyết định vào lệnh)

```python
# core/interfaces/entry_strategy.py [NEW]
from abc import ABC, abstractmethod
from dataclasses import dataclass
from core.models import ParsedSignal, TradeDecision

@dataclass
class StrategyContext:
    """Context truyền vào strategy."""
    signal: ParsedSignal
    snapshot: MarketSnapshot  # từ DataProvider
    settings: dict  # any extra config


class StrategyResult:
    """Kết quả từ strategy."""
    should_enter: bool
    decision: TradeDecision | None = None
    reason: str = ""
    volume: float = 0.0


class IEntryStrategy(ABC):
    """Interface cho chiến lược vào lệnh — dễ swap strategy."""

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> StrategyResult:
        """Đánh giá signal → nên vào lệnh không, loại lệnh gì."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Tên chiến lược để log."""
        ...
```

**Implementations**:
- `SimpleEntryStrategy` — logic hiện tại (validator + order_builder)
- `MultiTimeframeStrategy` — kiểm tra trend trên H4/D1 trước khi vào
- `ScalperStrategy` — chỉ vào MARKET, không LIMIT/STOP
- `ConservativeStrategy` — thêm điều kiện RSI, volume, etc.

### 6.5 Bước 3: Tạo interface cho Cancel Strategy (hủy lệnh)

```python
# core/interfaces/cancel_strategy.py [NEW]
from abc import ABC, abstractmethod

class ICancelStrategy(ABC):
    """Interface cho chiến lược hủy lệnh."""

    @abstractmethod
    def should_cancel(self, order: dict, current_time: int, **kwargs) -> tuple[bool, str]:
        """Kiểm tra order có nên hủy không.

        Returns:
            (should_cancel, reason)
        """
        ...
```

**Implementations**:
- `TTLCancelStrategy` — hủy nếu quá TTL (logic hiện tại)
- `PriceCancelStrategy` — hủy nếu giá đi xa quá ngưỡng
- `NewsEventCancelStrategy` — hủy trước tin tức quan trọng
- `CompositeCancelStrategy` — kết hợp nhiều strategy

### 6.6 Bước 4: Refactor Pipeline

```python
# core/pipeline.py [NEW]
class TradePipeline:
    """Orchestrate toàn bộ pipeline — pluggable."""

    def __init__(
        self,
        parser: SignalParser,
        data_provider: IDataProvider,
        strategy: IEntryStrategy,
        cancel_strategy: ICancelStrategy,
        storage: Storage,
        executor: TradeExecutor,
        circuit_breaker: CircuitBreaker,
    ):
        self._parser = parser
        self._data = data_provider
        self._strategy = strategy
        self._cancel = cancel_strategy
        self._storage = storage
        self._executor = executor
        self._breaker = circuit_breaker

    def process(self, raw_text: str, chat_id: str, msg_id: str) -> None:
        # Step 1: Parse
        signal = self._parser.parse(raw_text, chat_id, msg_id)
        if isinstance(signal, ParseFailure):
            return

        # Step 2: Circuit breaker
        if not self._breaker.is_trading_allowed:
            return

        # Step 3: Get market data
        snapshot = self._data.get_snapshot(signal.symbol, signal.side.value)

        # Step 4: Strategy evaluation (THAY THẾ validator + order_builder)
        ctx = StrategyContext(signal=signal, snapshot=snapshot, settings={})
        result = self._strategy.evaluate(ctx)

        if not result.should_enter:
            self._storage.store_signal(signal, SignalStatus.REJECTED)
            return

        # Step 5: Execute
        request = build_mt5_request(signal, result.decision, result.volume, ...)
        exec_result = self._executor.execute(request)
        ...
```

### 6.7 Bước 5: Cấu hình strategy qua ENV

```ini
# Thêm vào .env
ENTRY_STRATEGY=simple            # simple, multi_tf, scalper, conservative
CANCEL_STRATEGY=ttl              # ttl, price_based, composite
DATA_PROVIDER=mt5                # mt5, api, dry_run
```

```python
# core/strategy_factory.py [NEW]
def create_strategy(name: str, settings: Settings) -> IEntryStrategy:
    match name:
        case "simple":
            return SimpleEntryStrategy(settings)
        case "multi_tf":
            return MultiTimeframeStrategy(settings)
        case "scalper":
            return ScalperStrategy(settings)
        case _:
            raise ValueError(f"Unknown strategy: {name}")
```

### 6.8 Tóm tắt refactor path

| Bước | File thay đổi | Mô tả | Ưu tiên |
|------|--------------|-------|---------|
| 1 | `core/interfaces/data_provider.py` [NEW] | Interface lấy data | HIGH |
| 2 | `core/interfaces/entry_strategy.py` [NEW] | Interface chiến lược vào lệnh | HIGH |
| 3 | `core/interfaces/cancel_strategy.py` [NEW] | Interface hủy lệnh | MEDIUM |
| 4 | `core/providers/mt5_data_provider.py` [NEW] | Extract logic MT5 data từ main.py | HIGH |
| 5 | `core/providers/dry_run_data_provider.py` [NEW] | Extract `_simulate_tick()` | HIGH |
| 6 | `core/strategies/simple_entry.py` [NEW] | Extract validator + order_builder logic | HIGH |
| 7 | `core/strategies/ttl_cancel.py` [NEW] | Extract lifecycle_manager logic | MEDIUM |
| 8 | `core/pipeline.py` [NEW] | Orchestrator mới thay `_do_process_signal()` | HIGH |
| 9 | `core/strategy_factory.py` [NEW] | Factory tạo strategy từ ENV config | MEDIUM |
| 10 | `main.py` [MODIFY] | Dùng pipeline mới, bỏ logic cũ | HIGH |
| 11 | `config/settings.py` [MODIFY] | Thêm ENTRY_STRATEGY, CANCEL_STRATEGY | LOW |
| 12 | `.env` [MODIFY] | Thêm biến cấu hình mới | LOW |

### 6.9 Lợi ích sau refactor

| Trước | Sau |
|-------|-----|
| Muốn đổi strategy = sửa `main.py` 240 dòng | Tạo class mới implement `IEntryStrategy` |
| Muốn thêm data source = sửa Step 4 trong main | Tạo class mới implement `IDataProvider` |
| Muốn đổi logic hủy = sửa `order_lifecycle_manager.py` | Tạo class mới implement `ICancelStrategy` |
| Toàn bộ logic nằm 1 file | Tách biệt rõ ràng, swap dễ |
| Không thể A/B test strategy | Chạy 2 strategy song song so sánh |
| Khó unit test pipeline | Mỗi phần test độc lập |

---

> **⚠️ LƯU Ý QUAN TRỌNG**: Refactor này nên làm từng bước, mỗi bước tạo 1 PR riêng. KHÔNG refactor toàn bộ cùng lúc.rser: Nếu đổi Regex ở Parser, mọi thứ sẽ sập do Missing Fields `None` dồn vào hàm Validator -> bị drop lệnh ngay cửa ải đầu tiên.

---