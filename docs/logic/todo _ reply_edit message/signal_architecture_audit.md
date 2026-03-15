# 🧠 Audit: Signal-Message Architecture

## Desired Architecture (từ user)

```
Telegram message → telegram_listener → message_router
                                         ↓
                              ┌──────────┼──────────┐
                              │          │          │
                         NEW SIGNAL  MSG EDIT  REPLY CMD
                              │          │          │
                              └──────────┼──────────┘
                                         ↓
                                   order manager
                                         ↓
                                   mt5 executor
```

**Yêu cầu cốt lõi:**
1. Signal ↔ Message linking (chat_id + message_id + ticket)
2. 3 loại message: NEW / EDIT / REPLY
3. State machine: `received → parsed → pending → executed → cancelled → closed → failed`
4. Edge cases: duplicate reply, reply sai signal, cancel sau khi khớp

---

## Đánh giá hiện tại (v0.5.1)

### ✅ CÓ — Đang hoạt động

| Feature | File | Status |
|---------|------|--------|
| NEW SIGNAL flow | [telegram_listener.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/telegram_listener.py) → `main.py._do_process_signal()` | ✅ Hoàn chỉnh |
| Signal lưu `chat_id` + `message_id` vào DB | [storage.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/storage.py) signals table | ✅ Có cột |
| MESSAGE EDIT detection | [telegram_listener.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/telegram_listener.py) events.MessageEdited | ✅ Handler registered |
| Edit diff logic | [message_update_handler.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/message_update_handler.py) | ✅ Có (so sánh fingerprint) |
| Command parsing | [command_parser.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/command_parser.py) + [command_executor.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/command_executor.py) | ✅ CLOSE/MOVE SL/BREAKEVEN |
| Signal dedup (fingerprint) | `storage.is_duplicate()` | ✅ TTL window |

### ⚠️ CÓ NHƯNG KHÔNG HOẠT ĐỘNG

| Feature | Vấn đề | Impact |
|---------|--------|--------|
| Edit callback wiring | `main.py:204` gọi `self.listener.set_edit_callback(self._process_edit)` nhưng **method [_process_edit](file:///d:/Development/Workspace/Python_Projects/Forex/main.py#660-668) KHÔNG TỒN TẠI** trong [main.py](file:///d:/Development/Workspace/Python_Projects/Forex/main.py) | 🔴 **RuntimeError khi edit xảy ra** |
| [message_update_handler.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/message_update_handler.py) Step 3 | TODO P2: query MT5 for actual order status (pending vs executed) | ⚠️ Luôn trả `CANCEL_ORDER` dù order đã executed |

### ❌ THIẾU HOÀN TOÀN

| Feature | Mô tả | Cần thiết? |
|---------|-------|------------|
| **REPLY MESSAGE handler** | Listener KHÔNG listen `reply_to_msg_id`. Không có handler cho reply. | 🔴 Critical |
| **Signal ↔ Ticket linking** | `signals` table KHÔNG có cột `ticket`. `ticket` chỉ ở [orders](file:///d:/Development/Workspace/Python_Projects/Forex/core/trade_executor.py#221-225) table, tách biệt. | 🔴 Critical |
| **Lookup signal by message_id** | [storage.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/storage.py) không có `get_signal_by_message_id()` | 🔴 Cần cho EDIT + REPLY |
| **State: [pending](file:///d:/Development/Workspace/Python_Projects/Forex/core/trade_executor.py#348-373)** | [SignalStatus](file:///d:/Development/Workspace/Python_Projects/Forex/core/models.py#27-34) thiếu. Hiện chỉ: received/parsed/rejected/submitted/executed/failed | 🟡 Important |
| **State: `cancelled`** | Không có cách đánh dấu signal bị cancel | 🟡 Important |
| **State: `closed`** | Không track position đã đóng | 🟡 Nice-to-have |
| **Edge case: cancel after exec** | Không check `status != pending` trước khi cancel | 🟡 Cần khi có reply |
| **Message router** | Không có. Mọi message đi thẳng vào [_do_process_signal()](file:///d:/Development/Workspace/Python_Projects/Forex/main.py#357-659) | 🟡 Architectural |

---

## Chi tiết từng gap

### 1. [_process_edit](file:///d:/Development/Workspace/Python_Projects/Forex/main.py#660-668) method missing — 🔴 BUG

```python
# main.py line 204
self.listener.set_edit_callback(self._process_edit)
# ^^^ self._process_edit KHÔNG CÓ trong class Bot
```

**Impact**: Nếu Telegram message bị edit → `AttributeError: 'Bot' object has no attribute '_process_edit'`\
**Fix**: Implement [_process_edit()](file:///d:/Development/Workspace/Python_Projects/Forex/main.py#660-668) method trong Bot class, wire vào [MessageUpdateHandler](file:///d:/Development/Workspace/Python_Projects/Forex/core/message_update_handler.py#39-154)

### 2. No REPLY handler — 🔴 Missing feature

[telegram_listener.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/telegram_listener.py) chỉ register:
- `events.NewMessage` → [_handle_new_message](file:///d:/Development/Workspace/Python_Projects/Forex/core/telegram_listener.py#173-205)
- `events.MessageEdited` → [_handle_edited_message](file:///d:/Development/Workspace/Python_Projects/Forex/core/telegram_listener.py#206-237)

**Không có**:
- `events.NewMessage` với check `event.message.reply_to_msg_id`
- Callback type cho reply messages
- Logic routing: message thường vs reply message

> Telethon `event.message.reply_to_msg_id` trả `int | None`\
> Nếu `!= None` → đây là reply → cần lookup signal gốc bằng message_id

### 3. [SignalStatus](file:///d:/Development/Workspace/Python_Projects/Forex/core/models.py#27-34) thiếu states

```python
# Hiện tại (models.py)
class SignalStatus(str, enum.Enum):
    RECEIVED  = "received"
    PARSED    = "parsed"
    REJECTED  = "rejected"
    SUBMITTED = "submitted"
    EXECUTED  = "executed"
    FAILED    = "failed"

# Cần thêm cho state machine đầy đủ:
    PENDING   = "pending"    # pending order placed, waiting for fill
    CANCELLED = "cancelled"  # user cancel via reply or edit
    CLOSED    = "closed"     # position closed (manual or TP/SL hit)
```

### 4. Signal ↔ Ticket linking

Hiện tại:
- `signals` table: fingerprint, symbol, side, entry, sl, tp, status, chat_id, message_id
- [orders](file:///d:/Development/Workspace/Python_Projects/Forex/core/trade_executor.py#221-225) table: ticket, fingerprint, order_kind, price, sl, tp, retcode, success

Join qua `fingerprint` nhưng **không direct**. Cần:
- Thêm `ticket` vào `signals` table, hoặc
- Method `get_ticket_by_fingerprint()` trong [storage.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/storage.py)

### 5. Lookup signal by message_id

Cần cho reply flow:
```python
# storage.py — CHƯA CÓ
def get_signal_by_message_id(self, chat_id: str, message_id: str) → dict | None:
    """Lookup signal record by original Telegram message."""
```

---

## Kết luận

| Tiêu chí | Match? |
|----------|--------|
| Signal ↔ message linking | ⚠️ Partial (chat_id + message_id có, nhưng không có ticket, không có lookup) |
| 3 loại message (NEW/EDIT/REPLY) | ❌ Chỉ có NEW. EDIT bị broken. REPLY không có. |
| State machine | ❌ Thiếu 3 states (pending/cancelled/closed) |
| Edge cases | ❌ Không thể check — chưa có reply flow |
| Message router | ❌ Không có. Flat pipeline. |
| Follow RULES.md | ✅ Code tuân thủ style/safety/naming rules |

> **Tổng quan**: Hệ thống hiện tại thiết kế cho **one-way signal flow** (Telegram → parse → execute). 
> Architecture cho **interactive signal management** (edit/reply/cancel) mới chỉ có skeleton ([message_update_handler.py](file:///d:/Development/Workspace/Python_Projects/Forex/core/message_update_handler.py)) nhưng **chưa wire** và **chưa có reply path**.
