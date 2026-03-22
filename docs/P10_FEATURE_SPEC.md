# P10 — Smart Signal Group Management: Feature Spec

> **Target version**: v0.10.0 (shipped)
> **Previous**: v0.9.0 (P9 — Channel-Driven Strategy)
> **Created**: 2026-03-21

---

## Tong Quan

### Truoc P10 (v0.9.0)
Bot la **fire-and-forget**: tin hieu vao -> parse -> vao lenh -> xong.
PositionManager chi trailing per-position, khong biet signal group.

### Sau P10 (v1.0.0)
**Moi signal deu tao GROUP** (group of 1 hoac group of N).
`PositionManager` duoc **nang cap** thanh group-aware — KHONG tao module moi.

```
                    POSITION MANAGER (NANG CAP)
                    +-----------------------------------------+
                    |                                         |
Tin hieu -> Parse -> Pipeline -> orders -> Register Group     |
                                                  |           |
                                           +------+------+   |
                                           | Group of 1   |   |
                                           | Group of N   |   |
                                           +------+------+   |
                                                  |           |
                                        Trail SL (group)      |
                                        Reply close highest   |
                                        Auto BE               |
                                        Individual BE/trail   |
                                        Completion -> DB      |
                    +-----------------------------------------+
```

### Moi signal = 1 Group

| Channel mode | Orders | Group size | PositionManager behavior |
|---|---|---|---|
| `single` | 1 signal -> 1 order | Group of 1 | Trailing/BE/partial nhu cu |
| `range` | 1 signal -> 1-3 orders | Group of N | Group trailing, reply selective, auto BE |
| `scale_in` | 1 signal -> 1-3 orders | Group of N | Same as range |

---

## Chuc Nang DA CO (truoc P10)

> Nhung chuc nang nay da hoat dong — P10 KHONG thay doi chung.

### 1. Reply Management (v0.8.0 — P7)

Khi user **reply vao tin nhan tin hieu goc** trong Telegram:

| Reply message | Hanh dong | Status |
|---------------|-----------|--------|
| `close` / `dong` / `exit` | Dong TAT CA orders cua tin hieu do | CO |
| `close 50%` | Dong 50% volume | CO |
| `SL 2020` | Move SL toi 2020 cho tat ca orders | CO |
| `TP 2050` | Move TP toi 2050 | CO |
| `BE` / `breakeven` | Move SL toi entry (breakeven) | CO |

**Flow hien tai:**
```
User reply "close" vao tin nhan tin hieu
  -> telegram_listener detect reply_to_msg_id
  -> main.py._process_reply()
  -> storage.get_orders_by_message(message_id) -> list tickets
  -> reply_action_parser.parse("close") -> ReplyAction(CLOSE)
  -> reply_command_executor.execute(ticket) cho TUNG ticket
  -> Telegram response: "Da dong 3 orders"
```

### 2. Message Edit (v0.7.0)

| Tinh huong | Hanh dong |
|------------|-----------|
| Edit nhung SL/TP/entry giong (cung fingerprint) | IGNORE |
| Edit thay doi entry/SL/TP (fingerprint khac) | CANCEL pending order -> re-process signal |

### 3. Zone Entry + Re-entry (v0.9.0 — P9)

| Feature | Status |
|---------|--------|
| Zone parse: "BUY GOLD 4040-4042" | CO |
| Multi-order: 3 entries across zone | CO |
| RangeMonitor: background price polling -> re-entry khi price cross level | CO |
| Max entries per channel (config) | CO |
| Volume split: equal / pyramid / risk_based | CO |

### 4. Position Management (v0.5.0) — per-position

| Feature | Status | Luu y P10 |
|---------|--------|-----------|
| Breakeven tu dong (trigger pips) | CO | Giu cho group of 1, GROUP BE cho group of N |
| Trailing stop per-position | CO | Giu cho group of 1, GROUP trail cho group of N |
| Partial close % near TP | CO | Giu nguyen |

---

## Chuc Nang MOI trong P10

### Chuc nang 1: Signal Group Tracking

**Mo ta**: Sau khi vao lenh, tat ca orders tu 1 tin hieu duoc gop thanh 1 **group** TRONG PositionManager. Group duoc theo doi lien tuc cho den khi TAT CA orders dong.

**Cach hoat dong**:
```
1. Pipeline execute 3 orders -> tickets [101, 102, 103]
2. PositionManager.register_group(signal, tickets, config)
3. Group state:
   - fingerprint: "abc123"
   - tickets: [101, 102, 103]
   - entry_prices: {101: 4042, 102: 4041, 103: 4040}
   - status: "active"
   - sl_mode: "zone"
   - zone_low: 4040, zone_high: 4042
4. _poll_loop (moi 5s) -> _check_positions() -> group detected -> _manage_group_position()
```

**Khi nao group ket thuc?**
- Tat ca orders hit SL -> group COMPLETED (loss)
- Tat ca orders hit TP -> group COMPLETED (profit)
- Tat ca orders da close qua reply -> group COMPLETED
- Signal TTL expired + no orders filled -> group EXPIRED

**Routing logic moi trong _check_positions():**
```python
for pos in bot_positions:
    group = self._get_group_for_ticket(pos.ticket)
    if group:
        # GROUP mode: SL/trailing managed at group level
        _manage_group_position(group)
    else:
        # INDIVIDUAL mode: legacy per-position (channel khong dung group)
        _manage_individual(pos, rules)
```

---

### Chuc nang 2: Group Trailing SL

**Mo ta**: SL duoc tu dich theo gia cho **CA GROUP** orders, khong chi per-position.

**Config**: `rules.group_trailing_pips` (default: 0 = disabled)

**Logic** (moi 5 giay):
```
Vi du: BUY group, group_trailing_pips = 50, zone_low = 4040

Gia hien tai: 4050
  -> Trail SL = 4050 - 50pip x 0.1 = 4045
  -> Zone SL = 4040 - 50pip x 0.1 = 4035
  -> Current SL = 4035 (from register)
  -> New SL = max(4045, 4035, 4035) = 4045 -> Dich SL len 4045

Gia tang len 4060:
  -> Trail SL = 4060 - 5 = 4055
  -> New SL = max(4055, 4035, 4045) = 4055 -> Dich SL len 4055

Gia giam lai 4057:
  -> Trail SL = 4057 - 5 = 4052
  -> New SL = max(4052, 4035, 4055) = 4055 -> KHONG dich xuong! Giu 4055
```

**Rule vang**: SL chi dich CO LOI (len cho BUY, xuong cho SELL). Khong bao gio keo nguoc.

---

### Chuc nang 3: Zone SL Mode

**Mo ta**: SL tinh **tu dong** tu zone thap nhat, thay vi lay SL tu signal.

**Config**:
- `rules.sl_mode`: `"zone"` / `"signal"` / `"fixed"`
- `rules.sl_max_pips_from_zone`: `50` (default)

**3 che do SL:**

| Mode | SL tinh tu | Vi du (BUY, zone 4040-4042) |
|------|-----------|-----------|
| `signal` | SL tu signal goc (parser detect) | SL = 3990 (tu "SL 3990") |
| `zone` | zone_low - sl_max_pips | SL = 4040 - 50x0.1 = 4035 |
| `fixed` | lowest entry - sl_max_pips | SL = 4040 - 50x0.1 = 4035 |

---

### Chuc nang 4: Reply Close Selective

**Mo ta**: Khi reply "close", thay vi dong TAT CA orders, chi dong order co **entry price cao nhat** (BUY) hoac thap nhat (SELL).

**Config**: `rules.reply_close_strategy`

| Gia tri | Hanh vi |
|---------|---------|
| `"all"` | Dong TAT CA orders (behavior hien tai) |
| `"highest_entry"` | BUY: dong entry cao nhat. SELL: dong entry thap nhat |
| `"lowest_entry"` | BUY: dong entry thap nhat. SELL: dong entry cao nhat |
| `"oldest"` | Dong order vao som nhat |

**Vi du (BUY, 3 orders entry 4040, 4041, 4042):**
```
Reply "close" lan 1 (strategy=highest_entry):
  -> Dong order entry=4042
  -> Con lai: [4041, 4040]

Reply "close" lan 2:
  -> Dong order entry=4041
  -> Con lai: [4040]

Reply "close" lan 3:
  -> Dong order entry=4040
  -> Group COMPLETED
```

---

### Chuc nang 5: Auto BE After Partial Close

**Mo ta**: Sau khi dong 1 order qua reply, tu dong set SL = **entry thap nhat** cua orders con lai.

**Config**: `rules.group_be_on_partial_close` (default: false)

**Vi du:**
```
3 orders BUY: entry 4040, 4041, 4042. SL dang o 4035.

Reply close -> dong 4042.

group_be_on_partial_close = true:
  Remaining entries: [4041, 4040]
  BE target = min(4041, 4040) = 4040

  Nhung SL dang = 4055 (da trailing len) > 4040
  -> KHONG ha SL! Giu 4055.

group_be_on_partial_close = true, SL dang = 4035:
  BE target = 4040
  4040 > 4035 -> UPGRADE SL to 4040
  -> Bay gio worst case: 2 orders breakeven
```

---

### Chuc nang 6: No-STOP Order Mode

**Mo ta**: Tuy channel, co the **disable** BUY_STOP / SELL_STOP.

**Config**: `strategy.order_types_allowed` (default: `["MARKET", "LIMIT", "STOP"]`)

**Rule quan trong:**
- **Gia NGOAI zone** (cao hon zone cho BUY): BUY LIMIT tai **zone MID**
- **Gia TRONG zone**: **MARKET** luon
- Cac level con lai: LIMIT tai entry level

**Vi du 1 — Gia NGOAI zone:**
```
Zone BUY 4040-4042. Price ASK = 4050.
zone_mid = (4040 + 4042) / 2 = 4041

  Level 0: BUY_LIMIT tai zone_mid = 4041 (cho gia quay lai giua zone)
  Level 1: BUY_LIMIT tai 4041 <- trung Level 0 -> gop hoac skip
  Level 2: BUY_LIMIT tai 4040
  -> 2-3 LIMIT orders cho gia giam ve zone
```

**Vi du 2 — Gia TRONG zone:**
```
Zone BUY 4040-4042. Price ASK = 4041.

  Level 0: entry=4042 > ask=4041 -> gia dang trong zone -> MARKET luon
  Level 1: entry=4041, |4041-4041| <= tolerance -> MARKET
  Level 2: entry=4040, 4040 < 4041 -> BUY_LIMIT tai 4040
```

**Vi du 3 — Gia thap hon zone (hiem):**
```
Zone BUY 4040-4042. Price ASK = 4038.

  Level 0: entry=4042 > ask=4038 -> BUY_LIMIT tai zone_mid=4041
  Level 1: entry=4041 > 4038 -> BUY_LIMIT tai 4041
  Level 2: entry=4040 > 4038 -> BUY_LIMIT tai 4040
```

---

## Tat Ca Tinh Huong (Scenarios)

### Scenario 1: Happy Path — Full Lifecycle

```
Signal: "BUY GOLD 4040-4042, SL 3990, TP 4100"
Channel config: mode=range, max_entries=3, sl_mode=zone, sl_max_pips=50

1. Parse -> entry_range=[4040,4042], SL=3990, TP=[4100]
2. Validate -> PASS
3. Pipeline -> 3 entries: [4042, 4041, 4040]
4. Price ASK=4041 ->
   - Level 0 (4042): giá trong zone -> MARKET
   - Level 1 (4041): MARKET (trong tolerance)
   - Level 2 (4040): BUY_LIMIT tai 4040
5. PositionManager.register_group: zone_sl = 4040 - 5 = 4035
6. Gia giam -> 4040 FILLED -> 3 orders open
7. Gia tang 4060 -> trail SL = 4055
8. Reply "close" -> dong entry=4042 -> profit
9. Auto BE -> SL = min(4041,4040) = 4040. Nhung 4055 > 4040 -> giu 4055
10. Gia tang 4080 -> trail SL = 4075
11. Gia giam 4075 -> SL hit -> 2 orders closed -> profit
12. Group COMPLETED -> luu DB
```

### Scenario 2: Gia Bay Luon — Khong Fill

```
Signal: "BUY GOLD 4040-4042"
Price ASK = 4050, dang bay len

1. 3 BUY_LIMIT orders tai 4042, 4041, 4040
2. Gia KHONG BAO GIO quay lai zone
3. signal_ttl_minutes = 60 -> sau 60 phut
4. RangeMonitor expired -> cancel all pending orders
5. Group status = EXPIRED
```

### Scenario 3: Chi 1 Order Fill

```
Signal: "BUY GOLD 4040-4042"
1. 3 LIMIT orders dat
2. Gia cham 4042 -> Level 0 FILLED
3. Gia tang luon -> Level 1, 2 KHONG fill
4. signal_ttl expired -> cancel Level 1, 2
5. Group co 1 order active -> tiep tuc trailing SL
6. Khi order cuoi cung dong -> Group COMPLETED
```

### Scenario 4: Reply Nhieu Lan

```
3 orders BUY entry: 4040, 4041, 4042

Reply 1: "close" -> dong 4042 -> con [4041, 4040]
Reply 2: "close" -> dong 4041 -> con [4040]
Reply 3: "close" -> dong 4040 -> Group COMPLETED

Telegram:
  Reply 1: "Dong 1/3 (entry 4042, +$15). Con 2 orders."
  Reply 2: "Dong 1/2 (entry 4041, +$8). Con 1 order."
  Reply 3: "Dong 1/1 (entry 4040, +$3). Group hoan tat. Total: +$26"
```

### Scenario 5: Reply Khi SL Da Trail Cao

```
3 orders BUY: 4040, 4041, 4042
SL da trail len 4055 (gia dang 4060)

Reply "close" -> dong 4042 (+$18)
Auto BE target = min(4041, 4040) = 4040
Nhung 4055 > 4040 -> KHONG ha SL -> giu 4055

-> User van protected: SL=4055 tren 2 orders con lai
```

### Scenario 6: Signal Khong Co Zone (Single Entry = Group of 1)

```
Signal: "BUY GOLD 4041" (KHONG co zone)
Channel config: mode=single

-> 1 order BUY tai 4041
-> PositionManager.register_group(1 ticket)
-> Group of 1 -> trailing/BE behavior nhu cu
-> sl_mode=zone -> zone_low = zone_high = 4041
-> Zone SL = 4041 - 50pip = 4036
```

### Scenario 7: Bot Restart

```
Bot crash/restart khi co 2 active groups

1. Startup -> PositionManager._rebuild_cache()
2. Query signal_groups table -> rebuild groups dict
3. Query MT5 positions by magic number -> verify tickets still open
4. Resume monitoring
```

### Scenario 8: Reply SL/TP (Khong phai close)

```
Reply "SL 4050" -> Move SL cho TAT CA orders trong group
Reply "TP 4100" -> Move TP cho tat ca
Reply "BE" -> Set SL = entry cho tat ca (per-order BE)

-> Nhung reply nay KHONG trigger close_highest, giu behavior hien tai
-> Chi reply "close" / "dong" moi trigger selective close
```

### Scenario 9: SELL Group

```
Signal: "SELL GOLD 4040-4042"
-> SELL range: Level 0 = 4040 (gan market), Level 1 = 4041, Level 2 = 4042
-> Zone SL = zone_high + 50pip = 4042 + 5 = 4047

Reply "close" (strategy=highest_entry):
  -> SELL -> "highest entry" = entry CAO nhat = 4042
  -> Dong order entry=4042

Trail SL (SELL):
  -> Trail = price + trail_pips (dang short -> SL phia TREN)
  -> Chi dich XUONG (co loi cho SELL)
```

### Scenario 10: Channel Khac = Chien Thuat Khac

```
Channel A (Scalping):
  mode=range, max_entries=3, sl_mode=zone,
  group_trailing_pips=50, reply_close_strategy=highest_entry

Channel B (Swing):
  mode=single, max_entries=1,
  group_trailing_pips=100, reply_close_strategy=all

Channel C (Conservative):
  mode=range, max_entries=2, sl_mode=signal,
  group_trailing_pips=0 (disabled), reply_close_strategy=all
```

-> Moi channel hoat dong hoan toan khac nhau, tat ca config dynamic.

---

## Tom Tat Config Moi (Tat Ca Dynamic, Per-Channel)

| Config Key | Type | Default | Mo ta |
|------------|------|---------|-------|
| `strategy.order_types_allowed` | `list` | `["MARKET","LIMIT","STOP"]` | Loai order cho phep |
| `rules.sl_mode` | `str` | `"signal"` | Cach tinh SL: signal/zone/fixed |
| `rules.sl_max_pips_from_zone` | `float` | `50` | SL cach zone low N pips |
| `rules.sl_min_pips_from_entry` | `float` | `10` | SL toi thieu cach entry |
| `rules.group_trailing_pips` | `float` | `0` | Trail SL N pips tu gia (0=off) |
| `rules.group_be_on_partial_close` | `bool` | `false` | Auto BE khi partial close |
| `rules.reply_close_strategy` | `str` | `"all"` | Chon order nao dong khi reply |
| `rules.reply_be_target` | `str` | `"lowest_remaining_entry"` | BE dat o dau |

---

## Storage & Dashboard Data

### Group tracking: In-Memory + DB Persistence

**Tai sao in-memory + DB?**
- **In-memory**: dict `{fp: OrderGroup}` trong PositionManager -> poll moi 5s KHONG query DB -> nhanh
- **DB persist**: restart -> reload groups tu DB -> khong mat tracking
- **Dashboard**: query DB -> reports, win/loss, per-channel stats

### DB Tables

| Table | Du lieu | Dung cho |
|-------|---------|----------|
| `signals` (da co) | fingerprint, symbol, side, entry, chat_id, message_id | Link signal -> orders |
| `orders` (da co) | ticket, fingerprint, order_kind, price, retcode, success | Per-order audit |
| `trades` (da co) | ticket, pnl, commission, swap, close_reason | PnL tracking |
| `signal_groups` (NEW) | group_fp, channel_id, zone, total_orders, total_pnl, status | Group-level stats |
| `group_sl_history` (NEW) | group_fp, old_sl, new_sl, reason, timestamp | SL movement audit |

### Moi event -> log DB:

| Event | DB Action |
|-------|-----------|
| Group registered | `signal_groups` INSERT |
| SL modified | `group_sl_history` INSERT |
| Order closed (reply) | `orders` UPDATE + `signal_groups` UPDATE |
| Group completed | `signal_groups` UPDATE (total_pnl, status=completed) |

-> **Dashboard (P11)** chi can SELECT tu tables nay.

---

## Tuong Tac Voi Chuc Nang Hien Co

| Chuc nang hien tai | Tuong tac P10 |
|--------------------|---------------|
| **PositionManager** (trailing/BE/partial) | **NANG CAP**: them group logic, routing group vs individual |
| **RangeMonitor** (re-entry) | **Phoi hop**: re-entry -> PositionManager.add_order_to_group() |
| **TradeTracker** (PnL tracking) | **Phoi hop**: detect close -> PositionManager.on_order_closed() |
| **Reply handler** (v0.8.0) | **Nang cap**: "close" route qua PositionManager.close_highest_entry() |
| **SignalStateManager** (entry plans) | **Giu nguyen**: track entry plan status cho RangeMonitor |
| **Message Edit handler** | **Khong thay doi** |
