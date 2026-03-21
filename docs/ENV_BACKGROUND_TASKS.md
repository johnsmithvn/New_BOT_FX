# Hướng dẫn cấu hình hệ thống & Cơ chế chạy ngầm (Background Tasks)

Tài liệu này giải thích chi tiết hai phần quan trọng của Bot:
1. Cơ chế hoạt động của các tiến trình chạy ngầm (Polling Intervals).
2. Ý nghĩa và cách cấu hình toàn bộ biến môi trường trong file `.env`.

---

## 1. Cơ chế tiến trình chạy ngầm (Background Tasks Polling)

Hệ thống Bot của chúng ta được thiết kế theo chuẩn Production-Grade Async Architecture. Thay vì sử dụng vòng lặp vô tận (tight-loop) kiểu `while True: pass` gây ngốn 100% CPU, tất cả các tác vụ ngầm đều lặp lại dựa trên cơ chế nghỉ ngơi theo chu kỳ `asyncio.sleep()`.

Dưới đây là chi tiết nhịp đập (interval) của từng module:

### 1.1 Position Manager (Quản lý lệnh đang mở)
- **Nhiệm vụ**: Theo dõi giá để dời Stop Loss (Breakeven), kích hoạt chốt lời động (Trailing Stop), và chốt lời từng phần (Partial Close) tại TP1.
- **Biến điều khiển**: `POSITION_MANAGER_POLL_SECONDS`
- **Tần suất lặp mặc định**: `5` giây / lần.
- **Cơ chế**: Vòng lặp lấy danh sách các vị thế (positions) hiện tại, tính toán PnL, kiểm tra các mức Trigger, rồi ngủ 5 giây. Không gây quá tải API của MT5.

### 1.2 Order Lifecycle Manager (Dọn dẹp lệnh chờ quá hạn)
- **Nhiệm vụ**: Huỷ bỏ các lệnh Pending (Limit/Stop) đã tồn tại quá thời gian cho phép mà chưa khớp giá Entry.
- **Biến điều khiển**: `LIFECYCLE_CHECK_INTERVAL_SECONDS` và `PENDING_ORDER_TTL_MINUTES`
- **Tần suất lặp mặc định**: `30` giây / lần.
- **Cơ chế**: Module chỉ kiểm tra danh sách lệnh chờ 30 giây một lần. Nếu phát hiện lệnh tồn tại lâu hơn ngưỡng TTL (Time-To-Live), nó sẽ gửi Request Hủy lệnh.

### 1.3 MT5 Watchdog (Bảo vệ kết nối MT5)
- **Nhiệm vụ**: Liên tục bắt nhịp tim (Ping) để xác minh tài khoản MT5 đang duy trì kết nối. Nếu đứt mạng, nó tự động ép MT5 Terminal Re-connect lại.
- **Biến điều khiển**: `WATCHDOG_INTERVAL_SECONDS`
- **Tần suất lặp mặc định**: `30` giây / lần.
- **Cơ chế**: Nó cũng tính toán được cuối tuần (Thứ Bảy, Chủ Nhật) sàn đóng cửa để tránh tung cảnh báo giả (False Alarm) gửi về Telegram Admin.

### 1.4 Daily Risk Guard (Quản lý kỷ luật Trader)
- **Nhiệm vụ**: Tổng hợp Profit/Loss trong ngày để phát hiện hiện tượng cháy tài khoản và lập tức khoá tính năng vào lệnh mới, cắt chuỗi thua lỗ liên tiếp.
- **Biến điều khiển**: `DAILY_RISK_POLL_MINUTES`
- **Tần suất lặp mặc định**: `5` phút / lần (hoặc 300 giây).
- **Cơ chế**: Đọc Data từ History Deals của Terminal. Do dữ liệu về lệnh Đã Đóng (Closed) không cần phản ứng bằng Mili-giây, việc quét mỗi 5 phút giúp tiết kiệm cực lớn tài nguyên rảnh cho VPS.

### 1.5 Storage Cleanup (Gom rác Database)
- **Nhiệm vụ**: Xoá bỏ các Log cũ và dữ liệu rác lưu trong Data giúp chống tràn ổ cứng.
- **Biến điều khiển**: Bị ép cứng trong Source Code ở hàm `_storage_cleanup_loop`. Giữ lại Data số ngày cấu hình ở `STORAGE_RETENTION_DAYS`.
- **Tần suất lặp mặc định**: `24 * 3600` giây (Mỗi 24 giờ / lần).

### 1.6 Range Monitor — Giám sát giá để Re-entry (v0.9.0)
- **Nhiệm vụ**: Theo dõi giá thị trường real-time để phát hiện khi giá **xuyên qua** (cross through) một mức entry đã lên kế hoạch. Khi phát hiện → emit event cho Pipeline tạo lệnh re-entry.
- **Biến điều khiển**: `poll_seconds=5` và `debounce_seconds=30` (cấu hình trong code, chưa expose ra `.env`).
- **Tần suất lặp mặc định**: `5` giây / lần.
- **Cơ chế**:
  - Chỉ chạy khi có signal active ở mode `range` hoặc `scale_in`.
  - **Price-cross detection**: Chỉ trigger khi giá đi **xuyên qua** level (prev > level → current ≤ level cho BUY). Không trigger khi giá chỉ "gần" level.
  - **Debounce 30 giây**: Sau khi trigger 1 level, tạm bỏ qua level đó trong 30 giây để tránh spam order.
  - Group tất cả pending levels theo symbol → gọi `get_tick()` 1 lần per symbol (tiết kiệm API calls).
  - Emit callback → `Pipeline.handle_reentry()` thực thi lệnh với đầy đủ risk guards.


---

## 2. Giải thích chi tiết Biến Môi Trường (.env)

Mọi cấu hình hệ thống đều được bóc tách từ Code Base ra File `.env` để Deployers thay đổi dễ dàng mà không càn chọc ngoáy vào kịch bản Python.

### 2.1 Telegram Cấu Hình
- `TELEGRAM_API_ID`: ID của Telegram App (Lấy từ my.telegram.org)
- `TELEGRAM_API_HASH`: Hash bí mật của App
- `TELEGRAM_PHONE`: Số điện thoại đăng nhập Acc Telegram nhận tín hiệu.
- `TELEGRAM_SESSION_NAME`: Tên file lưu session login.
- `TELEGRAM_SOURCE_CHATS`: Các Channel/Nhóm VIP mà bạn muốn bot hóng tín hiệu.
- `TELEGRAM_ADMIN_CHAT`: Nhóm/Chat riêng của admin để Bot báo cáo (Báo lỗi, Cảnh báo Limit, Debug...).

### 2.2 MetaTrader 5 Thông Số
- `MT5_PATH`: Đường dẫn khởi động file `terminal64.exe` trong VPS.
- `MT5_LOGIN`: Account ID của sàn.
- `MT5_PASSWORD`: Mật khẩu tài khoản (Thường là Password Master để có quyền Trade).
- `MT5_SERVER`: Tên máy chủ môi giới của Sàn.

### 2.3 Quản Lý Vốn (Risk Management)
- `RISK_MODE`: Trạng thái rủi ro, `FIXED_LOT` (Đánh lot tĩnh không đổi) hoặc `RISK_PERCENT` (Tính toán tự động theo % Balance thực).
- `FIXED_LOT_SIZE`: Khối lượng Fix nếu ở Mode Cố Định.
- `RISK_PERCENT`: Phần trăm rủi ro mỗi lệnh (dùng cho Mode % Risk, VD 0.05 tương đương 5%).
- `LOT_MIN`: Ngưỡng chặn Lot nhỏ nhất không được vượt quá.
- `LOT_MAX`: Ngưỡng chặn Lot to nhất.
- `LOT_STEP`: Các hệ số bước Lot (0.01 cho ngoại hối/Vàng).

### 2.4 Cổng Bảo Vệ (Safety Gates - Tính bằng Pips)
- `MAX_SPREAD_PIPS`: Chặn cúp, từ chối nhận lệnh lúc giao phiên dãn Spread quá ngưỡng.
- `MAX_OPEN_TRADES`: Bot không mở rào thêm cho tín hiệu mới nếu đã có N lệnh đang chạy.
- `PENDING_ORDER_TTL_MINUTES`: Số phút cho phép Lệnh Chờ tồn tại.
- `SIGNAL_AGE_TTL_SECONDS`: Số giây độ trễ báo hiệu quá hẹn (Tránh tín hiệu từ Telegram chậm mất mười mấy phút).
- `MAX_ENTRY_DISTANCE_PIPS`: Phép thử đo lường tính khả thi khoảng cách Entry.
- `MAX_ENTRY_DRIFT_PIPS`: Chặn cú giật trượt giá lúc có tin mạnh (Slippage/Drift chặn vào lệnh).

### 2.5 Thực Thi Giao Dịch (Execution)
- `BOT_MAGIC_NUMBER`: Căn cước công dân của Bot. Bot chỉ tương tác và thu hồi các Lệnh do chính nó gắn cờ mã này.
- `DEVIATION_POINTS`: Điểm trượt giá cho phép đi kèm lệnh Order MT5.
- `MARKET_TOLERANCE_POINTS`: Độ dung sai cho phép chuyển từ Limit sang đấm thẳng giá Market vào mặt thị trường.
- `ORDER_MAX_RETRIES`: Số lần đấm cố đấm cửa lệnh rớt mạng / re-quote / lỗi sàn.
- `ORDER_RETRY_DELAY_SECONDS`: Số giây delay sau cú đấm trượt trước khi Retry lại.

### 2.6 Daily Risk Guard (Phòng vệ cháy Tài Khoản)
- `MAX_DAILY_TRADES`: Giới hạn nhát chặt chém mỗi ngày (0 = uýnh vô hạn).
- `MAX_DAILY_LOSS`: Số đô la Mỹ ($USD) rụng rời tối đa 1 ngày, lỗ quá là ngắt Bot.
- `MAX_CONSECUTIVE_LOSSES`: Chuỗi Stop-Loss liên tiếp (0 = tắt).
- `DAILY_RISK_POLL_MINUTES`: Số phút Quét Lịch Sử Lỗ.

### 2.7 Position Guard (Chăm lệnh thả nuôi)
- `BREAKEVEN_TRIGGER_PIPS`: Trạng thái ăn lãi bao nhiêu pips thì rời vị thế SL về giá mở vị thế Entry.
- `BREAKEVEN_LOCK_PIPS`: Quãng phí khóa cọc lãi (Dời về Entry + Lock pips dự phòng trả tiền Comm/Swap).
- `TRAILING_STOP_PIPS`: Khoảng cách rượt đuổi lãi linh hoạt đằng sau đích của giá.
- `PARTIAL_CLOSE_PERCENT`: Đụng TP1 chốt X % Volume thả cho nhịp khác nảy lộc.
- `POSITION_MANAGER_POLL_SECONDS`: Độ nhạy bắt nhịp đập quản trị nuôi lệnh ở đoạn 1.

### 2.8 System Runtime
- `DRY_RUN`: Bật `true` là Tàu chạy Test-mode (Mô phỏng 100% thật nhưng đoạn Execution thay bằng giả lập Log).
- `ALERT_COOLDOWN_SECONDS`: Số giây delay hạn chế dội Bomb Spam tin nhắn cảnh báo Admin lúc sàn sập.
- `CIRCUIT_BREAKER_THRESHOLD`: Đếm chuỗi vào lệnh bị chửi FAILED do Sàn Re-quote quá số N sẽ ngưng mẹ bot chục phút.
- `CIRCUIT_BREAKER_COOLDOWN`: Ngưng mấy chục phút để Market bình ổn rồi làm việc lại.
- `DEBUG_SIGNAL_DECISION`: Bật lên ăn no Log rác chi tiết để Fix Lỗi tính giá của Bot.
