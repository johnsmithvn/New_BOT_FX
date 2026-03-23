# Forex Trading Bot — Test Cases

> Comprehensive test case documentation for the entire Python bot system.
> Organized by module with test purpose, input/output, and expected behavior.

---

## Table of Contents

1. [Signal Parser Pipeline](#1-signal-parser-pipeline)
2. [Signal Validator](#2-signal-validator)
3. [Risk Manager](#3-risk-manager)
4. [Order Builder](#4-order-builder)
5. [Entry Strategy](#5-entry-strategy)
6. [Circuit Breaker](#6-circuit-breaker)
7. [Exposure Guard](#7-exposure-guard)
8. [Command Parser](#8-command-parser)
9. [Reply Action Parser](#9-reply-action-parser)
10. [Channel Manager](#10-channel-manager)
11. [Models & Data Contracts](#11-models--data-contracts)
12. [Storage (DB Operations)](#12-storage)
13. [Trade Executor](#13-trade-executor)
14. [Trade Tracker](#14-trade-tracker)
15. [Position Manager](#15-position-manager)
16. [Daily Risk Guard](#16-daily-risk-guard)
17. [Telegram Listener](#17-telegram-listener)
18. [Telegram Alerter](#18-telegram-alerter)
19. [Pipeline Orchestration](#19-pipeline-orchestration)
20. [Order Lifecycle Manager](#20-order-lifecycle-manager)
21. [MT5 Watchdog](#21-mt5-watchdog)
22. [Reply Command Executor](#22-reply-command-executor)
23. [Message Update Handler](#23-message-update-handler)
24. [Range Monitor](#24-range-monitor)
25. [Signal State Manager](#25-signal-state-manager)

---

## 1. Signal Parser Pipeline

**Module:** `core/signal_parser/`
**Purpose:** Convert raw Telegram message text into a structured `ParsedSignal` or `ParseFailure`.

### 1.1 `cleaner.clean(raw_text, max_length)` — Text normalization

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 1 | Empty string → None | `""` | `None` | Guard: reject empty |
| 2 | Whitespace only → None | `"   "` | `None` | Guard: no content |
| 3 | Exceeds max_length → None | `"A" * 2001` | `None` | Guard: oversized message |
| 4 | Normal text uppercase | `"buy gold"` | `"BUY GOLD"` | Uppercase normalization |
| 5 | Strip emoji | `"BUY 🚀 GOLD"` | `"BUY GOLD"` | Remove emoji characters |
| 6 | Collapse whitespace | `"BUY   GOLD   2030"` | `"BUY GOLD 2030"` | Multiple spaces → single |
| 7 | Strip blank lines | `"BUY\n\n\nGOLD"` | `"BUY\nGOLD"` | Remove empty lines |
| 8 | Tab replacement | `"BUY\tGOLD"` | `"BUY GOLD"` | Tab → space |
| 9 | Non-printable chars removed | `"BUY\x00GOLD"` | `"BUYGOLD"` | Control chars stripped |

### 1.2 `side_detector.detect(text)` — BUY/SELL detection

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 10 | Detect BUY | `"BUY XAUUSD"` | `"BUY"` | Basic BUY |
| 11 | Detect SELL | `"SELL EURUSD"` | `"SELL"` | Basic SELL |
| 12 | Detect LONG alias | `"LONG GOLD"` | `"BUY"` | LONG → BUY |
| 13 | Detect SHORT alias | `"SHORT GOLD"` | `"SELL"` | SHORT → SELL |
| 14 | Detect BUY STOP | `"BUY STOP 2030"` | `"BUY"` | Order type suffix |
| 15 | Detect SELL LIMIT | `"SELL LIMIT 2020"` | `"SELL"` | Order type suffix |
| 16 | No side → None | `"XAUUSD 2030"` | `None` | No direction keyword |
| 17 | Empty text → None | `""` | `None` | Guard: empty |
| 18 | First match wins | `"BUY SELL"` | `"BUY"` | Priority: first keyword |

### 1.3 `symbol_detector.detect(text, mapper)` — Symbol detection

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 19 | Direct symbol | `"BUY XAUUSD 2030"` | `"XAUUSD"` | Full broker symbol |
| 20 | Slash-separated pair | `"BUY XAU/USD"` | `"XAUUSD"` | Combined pair format |
| 21 | Alias resolution (GOLD) | `"BUY GOLD 2030"` | `"XAUUSD"` | Alias → broker name |
| 22 | No symbol → None | `"BUY AT 2030"` | `None` | No recognizable symbol |
| 23 | Empty text → None | `""` | `None` | Guard: empty |
| 24 | Multiple symbols: first wins | `"BUY EURUSD SL GBPUSD"` | `"EURUSD"` | Return first match |

### 1.4 `entry_detector.detect(text, side)` — Entry price detection

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 25 | Explicit ENTRY keyword | `"ENTRY 2030"` | `(2030.0, None, False)` | Standard entry |
| 26 | ENTRY with colon | `"ENTRY: 2030.50"` | `(2030.5, None, False)` | Colon separator |
| 27 | @ symbol | `"BUY GOLD @ 2030"` | `(2030.0, None, False)` | @ notation |
| 28 | PRICE keyword | `"PRICE: 2030"` | `(2030.0, None, False)` | Price keyword |
| 29 | Range detection | `"ENTRY 2030 - 2035"` | `(2030.0, [2030,2035], False)` | Range with dash |
| 30 | Range with slash | `"BUY GOLD 2030/2035"` | BUY: `(2030.0, [2030,2035], False)` | Range with slash |
| 31 | Range BUY picks low | `"BUY GOLD 2030 - 2035"` | entry=`2030.0` | BUY uses lowest |
| 32 | Range SELL picks high | `"SELL GOLD 2030 - 2035"` | entry=`2035.0` | SELL uses highest |
| 33 | Market keyword NOW | `"BUY GOLD NOW"` | `(None, None, True)` | Market execution |
| 34 | Market keyword CMP | `"BUY GOLD CMP"` | `(None, None, True)` | Current market price |
| 35 | No entry, no market → None | `"BUY GOLD"` | `(None, None, False)` | No price and no keywords |
| 36 | Side+price in same line | `"BUY GOLD 2030"` | `(2030.0, None, False)` | Price near side keyword |
| 37 | Range value over NOW | `"BUY GOLD ZONE 4963 - 4961 NOW"` | Range detected first | Range takes priority |
| 38 | Empty text | `""` | `(None, None, False)` | Guard |

### 1.5 `sl_detector.detect(text)` — Stop Loss detection

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 39 | SL with colon | `"SL: 2020"` | `2020.0` | Standard SL |
| 40 | STOP LOSS keyword | `"STOP LOSS 2020"` | `2020.0` | Full keyword |
| 41 | STOPLOSS single word | `"STOPLOSS 2020.5"` | `2020.5` | Combined keyword |
| 42 | S/L format | `"S/L: 2020"` | `2020.0` | Slash notation |
| 43 | No SL → None | `"BUY GOLD 2030"` | `None` | Not found |
| 44 | SL value 0 → None | `"SL: 0"` | `None` | Zero rejected |
| 45 | Decimal SL | `"SL 2019.75"` | `2019.75` | Float precision |

### 1.6 `tp_detector.detect(text)` — Take Profit detection

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 46 | Single TP | `"TP: 2050"` | `[2050.0]` | Basic TP |
| 47 | Numbered TPs (ordered) | `"TP1: 2040\nTP2: 2050\nTP3: 2060"` | `[2040, 2050, 2060]` | Multi-TP indexed |
| 48 | TP out of order → sorted by index | `"TP3: 2060\nTP1: 2040"` | `[2040, 2060]` | Sort by TP number |
| 49 | TAKE PROFIT keyword | `"TAKE PROFIT 2050"` | `[2050.0]` | Full keyword |
| 50 | T/P slash format | `"T/P: 2050"` | `[2050.0]` | Slash notation |
| 51 | Skip relative (PIPS) | `"TP: 30 PIPS"` | `[]` | Filter pip offsets |
| 52 | Skip relative (POINTS) | `"TP: 50 POINTS"` | `[]` | Filter point offsets |
| 53 | No TP → empty | `"BUY GOLD 2030"` | `[]` | Not found |
| 54 | Mixed (absolute + relative) | `"TP1: 2050\nTP2: 30 PIPS"` | `[2050.0]` | Keep absolute only |

### 1.7 `parser.SignalParser.parse()` — Orchestration

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 55 | Full signal → ParsedSignal | `"BUY GOLD 2030\nSL 2020\nTP 2050"` | ParsedSignal with all fields | End-to-end success |
| 56 | Market signal | `"BUY GOLD NOW\nSL 2020"` | entry=None, side=BUY | Market execution |
| 57 | Missing symbol → ParseFailure | `"BUY 2030\nSL 2020"` | ParseFailure("symbol not detected") | Required field missing |
| 58 | Missing side → ParseFailure | `"GOLD 2030\nSL 2020"` | ParseFailure("side not detected") | Required field missing |
| 59 | No entry, no market → ParseFailure | `"BUY GOLD\nSL 2020"` | ParseFailure("entry price not detected...") | Ambiguous intent |
| 60 | Fingerprint deterministic | Same signal twice | Same fingerprint | Dedup hash stability |
| 61 | Fingerprint includes chat_id | Same signal, different chat_id | Different fingerprint | Channel isolation |
| 62 | Exception safety | Adversarial input | ParseFailure (not crash) | Parser never throws |

### 1.8 `parser.generate_fingerprint()` — Signal hashing

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 63 | Deterministic output | Same fields → same hash | 16-char hex | SHA-256 truncated |
| 64 | Different entry → different hash | entry=2030 vs 2035 | Different fingerprints | Entry affects hash |
| 65 | None entry → "MARKET" in hash | entry=None | Contains "MARKET" in raw | Market encoding |
| 66 | chat_id affects hash | chat_id="A" vs "B" | Different hashes | Channel isolation |

---

## 2. Signal Validator

**Module:** `core/signal_validator.py`
**Purpose:** Enforce safety rules before trade execution.

### 2.1 `validate()` — Full validation chain

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | Missing symbol → reject | `reason="missing symbol"` | Rule 1 |
| 2 | Missing side → reject | `reason="missing side"` | Rule 1 |
| 3 | Missing SL → reject | `reason="missing Stop Loss"` | Rule 1 |
| 4 | Duplicate signal → reject | `reason="duplicate signal"` | Rule 2 |
| 5 | BUY SL above entry → reject | BUY, SL=2040, entry=2030 | Rule 3: SL coherence |
| 6 | SELL SL below entry → reject | SELL, SL=2020, entry=2030 | Rule 3: SL coherence |
| 7 | BUY SL below entry → pass | BUY, SL=2020, entry=2030 | Rule 3: valid |
| 8 | BUY TP below entry → reject | BUY, TP=2020, entry=2030 | Rule 4: TP coherence |
| 9 | SELL TP above entry → reject | SELL, TP=2050, entry=2030 | Rule 4: TP coherence |
| 10 | Entry too far from price → reject | 60 pips distance, max=50 | Rule 5: entry distance |
| 11 | Entry within range → pass | 30 pips, max=50 | Rule 5: valid |
| 12 | Signal age > TTL → reject | age=120s, TTL=60s | Rule 6 |
| 13 | Max trades reached → reject | open=5, max=5 | Rule 8 |
| 14 | All rules pass → valid | Valid signal | Full pass |
| 15 | No entry + no price → skip Rule 5 | entry=None, price=None | Skip distance check |

### 2.2 `validate_entry_drift()` — MARKET order drift guard

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 16 | Drift within threshold → pass | drift=5 pips, max=10 | Acceptable drift |
| 17 | Drift exceeds threshold → reject | drift=15 pips, max=10 | Too much price movement |
| 18 | No entry → pass | entry=None | Skip check |
| 19 | pip_size=0 → raw distance used | pip_size=0 | Division guard |

---

## 3. Risk Manager

**Module:** `core/risk_manager.py`
**Purpose:** Calculate trade volume (lot size) with broker constraint enforcement.

### 3.1 `calculate_volume()` — Volume calculation

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | FIXED_LOT mode → fixed lot | fixed_lot=0.05 → 0.05 | Default mode |
| 2 | RISK_PERCENT — normal calc | balance=10000, risk=1%, SL=10 pips → calculated volume | Risk-based sizing |
| 3 | RISK_PERCENT — missing balance → fallback | balance=None → fixed_lot | Fallback to fixed |
| 4 | RISK_PERCENT — SL distance 0 → fallback | entry=SL → fixed_lot | Zero SL guard |
| 5 | Clamp to lot_min | Calculated < 0.01 → 0.01 | Broker minimum |
| 6 | Clamp to lot_max | Calculated > 100 → 100.0 | Broker maximum |
| 7 | Round to lot_step | lot_step=0.01, volume=0.0345 → 0.03 | Floored to step |
| 8 | Zero balance → fallback | balance=0 → fixed_lot | Guard |
| 9 | Negative pip_value → fallback | pip_value=-1 → fixed_lot | Guard |

---

## 4. Order Builder

**Module:** `core/order_builder.py`
**Purpose:** Decide order type and build MT5-compatible request payloads.

### 4.1 `decide_order_type()` — Order classification

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | BUY entry=None → MARKET | MARKET | No entry = market |
| 2 | BUY entry ≈ ask (within tolerance) → MARKET | MARKET | Near-market = market |
| 3 | BUY entry < ask → BUY_LIMIT | BUY_LIMIT | Entry below market |
| 4 | BUY entry > ask → BUY_STOP | BUY_STOP | Entry above market |
| 5 | SELL entry=None → MARKET | MARKET | No entry = market |
| 6 | SELL entry ≈ bid → MARKET | MARKET | Near-market = market |
| 7 | SELL entry > bid → SELL_LIMIT | SELL_LIMIT | Entry above market |
| 8 | SELL entry < bid → SELL_STOP | SELL_STOP | Entry below market |
| 9 | STOP not allowed, price in zone → MARKET | MARKET | P10d fallback |
| 10 | STOP not allowed, price outside zone → LIMIT at zone_mid | BUY_LIMIT at midpoint | P10d: zone midpoint |
| 11 | STOP not allowed, no zone → MARKET | MARKET | P10d: safest fallback |

### 4.2 `compute_deviation()` — Dynamic deviation

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 12 | Multiplier=0 → base deviation | base_deviation=20 | Static mode |
| 13 | Multiplier>0, spread>0 → max(base, dynamic) | max(20, 50*0.5)=25 | Dynamic mode |
| 14 | Dynamic < base → use base | max(20, 5)=20 | Floor at base |

### 4.3 `build_request()` — MT5 payload construction

| # | Test Case | Verify | Purpose |
|---|-----------|--------|---------|
| 15 | MARKET BUY → price=ASK, type=BUY | `action=DEAL, type=BUY` | Correct price ref |
| 16 | MARKET SELL → price=BID | `price=bid` | Correct price ref |
| 17 | Pending order → price=decision.price | `action=PENDING` | Pending payload |
| 18 | Comment includes fingerprint | `comment="signal:a1b2c3d4"` | Traceability |
| 19 | Magic number from config | `magic=234000` | Bot identification |
| 20 | SL/TP=None → 0.0 | `sl=0.0, tp=0.0` | Default to zero |

---

## 5. Entry Strategy

**Module:** `core/entry_strategy.py`
**Purpose:** Generate multi-entry plans with configurable volume splitting.

### 5.1 `plan_entries()` — Entry plan generation

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | Single mode → 1 plan | `[EntryPlan(level_id=0)]` | Default behavior |
| 2 | Range mode, 3 entries BUY [2020,2030] | 3 plans: 2030, 2025, 2020 | BUY range descending |
| 3 | Range mode, 3 entries SELL [2020,2030] | 3 plans: 2020, 2025, 2030 | SELL range ascending |
| 4 | Range mode, no entry_range → fallback single | 1 plan | Graceful degradation |
| 5 | Scale_in mode, BUY, step=20 pips | Plans at entry, entry-step, entry-2*step | Stepped re-entries |
| 6 | Scale_in mode, SELL, step=20 pips | Plans at entry, entry+step, entry+2*step | Ascending for SELL |
| 7 | Scale_in, step=0 → fallback single | 1 plan | Guard: zero step |
| 8 | Max 10 entries hard cap | max_entries=20 → capped at 10 | Safety cap |
| 9 | Order kind decision: within tolerance → MARKET | OrderKind.MARKET | Near-price detection |
| 10 | Order kind decision: BUY below ask → BUY_LIMIT | OrderKind.BUY_LIMIT | Limit order |

### 5.2 `split_volume()` — Volume allocation

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 11 | Empty plans → empty list | `[]` | Guard |
| 12 | Single plan → full volume | `[0.10]` | No split |
| 13 | Equal split 3-way, 0.09 → [0.03, 0.03, 0.03] | Each = total/n | Equal division |
| 14 | Pyramid split 3-way | First > second > third | Weighted front |
| 15 | Risk-based split: farther from SL → larger | Largest volume for farthest entry | Distance weighting |
| 16 | Round to lot_step, enforce lot_min | All volumes ≥ lot_min | Broker compliance |
| 17 | Zero total_distance → fallback to equal | Equal split | Edge case guard |

---

## 6. Circuit Breaker

**Module:** `core/circuit_breaker.py`
**Purpose:** Pause trading after consecutive failures with auto-recovery.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | Initial state → CLOSED | `state=CLOSED, is_trading_allowed=True` | Start state |
| 2 | N failures → OPEN | After threshold failures | Auto-open |
| 3 | OPEN → trading blocked | `is_trading_allowed=False` | Block trades |
| 4 | OPEN + cooldown elapsed → HALF_OPEN | Auto-transition on state read | Cooldown logic |
| 5 | HALF_OPEN + success → CLOSED | Reset counters | Recovery test |
| 6 | HALF_OPEN + failure → OPEN (re-open) | Immediate re-open | Probe failed |
| 7 | Success resets failure counter | `_consecutive_failures=0` | Counter reset |
| 8 | State change callback fired | Callback(old, new) called | Observer pattern |
| 9 | Callback exception doesn't crash | Logs error, continues | Error safety |

---

## 7. Exposure Guard

**Module:** `core/exposure_guard.py`
**Purpose:** Prevent over-concentration on correlated symbols.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | No limits (0,0) → always allowed | `(True, "")` | Disabled state |
| 2 | Same-symbol limit reached → blocked | `(False, "same-symbol limit...")` | Same-symbol block |
| 3 | Same-symbol under limit → allowed | `(True, "")` | Under limit |
| 4 | Correlated group limit → blocked | XAUUSD blocked if XAGUSD at limit | Correlation block |
| 5 | Symbol not in any group → allowed | No group match | No group check |
| 6 | Mixed: same OK, correlated blocked | Correct reason reported | Priority handling |

---

## 8. Command Parser

**Module:** `core/command_parser.py`
**Purpose:** Parse Telegram management commands (admin control).

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 1 | CLOSE ALL | `"CLOSE ALL"` | `CLOSE_ALL` | Close all positions |
| 2 | CLOSE ALL (alias) | `"CLOSE EVERYTHING"` | `CLOSE_ALL` | Alias support |
| 3 | CLOSE HALF | `"CLOSE HALF"` | `CLOSE_HALF` | 50% close |
| 4 | CLOSE SYMBOL | `"CLOSE XAUUSD"` | `CLOSE_SYMBOL, symbol="XAUUSD"` | Symbol-specific close |
| 5 | BREAKEVEN | `"BREAKEVEN"` | `BREAKEVEN` | Move SL to entry |
| 6 | BE alias | `"BE"` | `BREAKEVEN` | Short form |
| 7 | MOVE SL | `"MOVE SL 2035"` | `MOVE_SL, price=2035.0` | Specific SL price |
| 8 | MOVE SL decimal | `"MOVE SL 2035.50"` | `MOVE_SL, price=2035.5` | Decimal price |
| 9 | Not a command → None | `"BUY GOLD 2030"` | `None` | Falls through to parser |
| 10 | Empty text → None | `""` | `None` | Guard |
| 11 | Case insensitive | `"close all"` | `CLOSE_ALL` | Uppercase internally |

---

## 9. Reply Action Parser

**Module:** `core/reply_action_parser.py`
**Purpose:** Parse reply messages into trade management actions.

| # | Test Case | Input | Expected | Purpose |
|---|-----------|-------|----------|---------|
| 1 | Close | `"close"` | `CLOSE` | Full close |
| 2 | Exit alias | `"exit"` | `CLOSE` | English synonym |
| 3 | Vietnamese đóng | `"đóng"` | `CLOSE` | Vietnamese support |
| 4 | Close partial | `"close 30%"` | `CLOSE_PARTIAL, percent=30` | Partial close |
| 5 | Close 0% → None | `"close 0%"` | `None` | Invalid range |
| 6 | Close 101% → None | `"close 101%"` | `None` | Invalid range |
| 7 | Move SL | `"SL 2035"` | `MOVE_SL, price=2035.0` | SL modification |
| 8 | Move SL (long form) | `"move sl 2035.50"` | `MOVE_SL, price=2035.5` | Full keyword |
| 9 | Move TP | `"TP 2050"` | `MOVE_TP, price=2050.0` | TP modification |
| 10 | Breakeven | `"BE"` | `BREAKEVEN` | Short form |
| 11 | Breakeven (long) | `"breakeven"` | `BREAKEVEN` | Full keyword |
| 12 | SL entry alias | `"sl entry"` | `BREAKEVEN` | SL at entry = BE |
| 13 | Not actionable → None | `"nice trade!"` | `None` | Comment, not command |
| 14 | Empty/blank → None | `"  "` | `None` | Guard |
| 15 | Price ≤ 0 → None | `"SL 0"` | `None` | Invalid price |

---

## 10. Channel Manager

**Module:** `core/channel_manager.py`
**Purpose:** Per-channel configuration with cascading defaults.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | Load valid JSON | Channels populated | Normal load |
| 2 | Missing config file → empty defaults | No crash, graceful fallback | File-not-found safety |
| 3 | Invalid JSON → empty defaults | Logs error, no crash | Parse error safety |
| 4 | get_rules() — channel-specific override | Override values used | Per-channel rules |
| 5 | get_rules() — unknown channel → defaults | Default rules returned | Fallback lookup |
| 6 | get_strategy() — mode override | `"range"` for specific channel | Strategy per channel |
| 7 | get_strategy() — default → single | `"single"` mode | Default strategy |
| 8 | get_risk_config() — empty → global .env | `{}` (empty dict) | No channel override |
| 9 | get_channel_name() — known channel | Human-readable name | Display name |
| 10 | get_channel_name() — unknown → chat_id | Returns raw ID | Fallback |
| 11 | reload() — config hot-reload | Clears + re-reads file | Runtime reload |

---

## 11. Models & Data Contracts

**Module:** `core/models.py`
**Purpose:** Shared data structures for the pipeline.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | Side enum values | BUY="BUY", SELL="SELL" | Enum correctness |
| 2 | OrderKind enum — all 5 values | MARKET, BUY_LIMIT, BUY_STOP, SELL_LIMIT, SELL_STOP | Enum completeness |
| 3 | ParsedSignal defaults | tp=[], entry=None | Default factory |
| 4 | order_fingerprint(base, 0) | `"base:L0"` | Level 0 format |
| 5 | order_fingerprint(base, 3) | `"base:L3"` | Level N format |
| 6 | GroupStatus transitions | ACTIVE → COMPLETED/EXPIRED | Valid transitions |
| 7 | SignalLifecycle states | PENDING→PARTIAL→COMPLETED, PENDING→EXPIRED | State machine |
| 8 | OrderGroup defaults | status=ACTIVE, tickets=[] | Default values |
| 9 | EntryPlan defaults | status="pending" | Correct initial status |

---

## 12. Storage

**Module:** `core/storage.py`
**Purpose:** SQLite persistence with versioned migrations.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | store_signal() + is_duplicate() | First store → False, second → True | Dedup check |
| 2 | store_order() — all fields persisted | Row with channel_id, source_chat_id etc | Full audit trail |
| 3 | store_event() — lifecycle events | Events table populated | Event tracking |
| 4 | store_trade() — PnL record | Trade with pnl, commission, swap | Outcome storage |
| 5 | get_orders_by_message() | Returns all orders for message_id | Reply handler needs |
| 6 | get_signal_reply_info() | Returns (fingerprint, chat_id) | Reply threading |
| 7 | get_fingerprint_by_message() | Returns fingerprint for edit handler | Message → signal lookup |
| 8 | Migration V1 → V5 runs idempotently | All tables created | Schema versioning |
| 9 | cleanup_old_records() | Records older than retention deleted | Auto-cleanup |
| 10 | store_group() → get_active_groups() | Group persisted and retrieved | P10 group persistence |
| 11 | update_group_sl() | current_group_sl updated | SL modification |
| 12 | complete_group_db() | Status set to COMPLETED | Group lifecycle |
| 13 | WAL mode enabled | Journal_mode=WAL | Concurrent read safety |

---

## 13. Trade Executor

**Module:** `core/trade_executor.py`
**Purpose:** MT5 terminal connection and order execution.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | init_mt5() success | Connection established | Startup |
| 2 | init_mt5() failure → retry | Bounded retries | Resilience |
| 3 | execute() success → ExecutionResult(success=True) | Ticket returned | Normal execution |
| 4 | execute() failure → retry up to max_retries | Bounded retry | Retry safety |
| 5 | execute() all retries fail → ExecutionResult(success=False) | Error message | Final failure |
| 6 | is_connected property | True when MT5 connected | Health check |
| 7 | get_position_symbols() | List of open position symbols | Exposure guard needs |
| 8 | orders_total() | Count of pending orders | Heartbeat needs |
| 9 | close_position() | Position closed | Direct close |
| 10 | modify_position() | SL/TP modified | Position mgmt needs |

---

## 14. Trade Tracker

**Module:** `core/trade_tracker.py`
**Purpose:** Background polling for trade outcomes and PnL replies.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | Poll detects closed deal → store_trade() | PnL persisted | Outcome tracking |
| 2 | Ticket → position resolution (2-step) | Correct position_ticket | MARKET + pending |
| 3 | Pending fill detection (DEAL_ENTRY_IN) | position_ticket updated | Pending order fill |
| 4 | PnL reply sent under original signal | reply_to_message() called | Threaded replies |
| 5 | Reply-closed ticket suppressed | No duplicate PnL reply | TTL suppression |
| 6 | mark_reply_closed() + _is_reply_closed() | Correctly suppressed within 5min | Reply close tracking |
| 7 | Restart recovery — last_deal_poll_time | Resumes from last poll | State persistence |
| 8 | Partial close throttle (60s) | No spam for same position_id | Rate limiting |

---

## 15. Position Manager

**Module:** `core/position_manager.py`
**Purpose:** Background position management with group-aware logic.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | Breakeven trigger — profit ≥ trigger pips | SL moved to entry + lock_pips | BE logic |
| 2 | Breakeven — profit below trigger | SL unchanged | No premature BE |
| 3 | Trailing stop — price moves favorably | SL trails at fixed distance | Trail logic |
| 4 | Trailing — SL only moves in favorable direction | Never moves SL unfavorably | Direction guard |
| 5 | Partial close at TP1 | close_volume = position * percent | Volume calculation |
| 6 | Per-channel rules override global | Channel-specific trigger_pips | Channel config |
| 7 | Group management — _calculate_group_sl() | Best SL from zone/signal/fixed/trail | Multi-source SL |
| 8 | Group SL — only moves favorably | Never widens SL | Direction guard |
| 9 | close_selective_entry() — highest_entry strategy | Closes highest entry order | Selective close |
| 10 | apply_group_be() after partial close | SL set to min remaining entry | Auto-BE logic |
| 11 | register_group() — persists to DB | Group stored with tickets | Persistence |
| 12 | Per-ticket alert throttle (60s) | No duplicate alerts | Rate limiting |

---

## 16. Daily Risk Guard

**Module:** `core/daily_risk_guard.py`
**Purpose:** Daily trade/loss limits from real MT5 deal history.

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | MAX_DAILY_TRADES reached → blocked | `is_allowed()=False` | Trade count limit |
| 2 | MAX_DAILY_LOSS exceeded → blocked | Loss exceeds threshold | Loss limit |
| 3 | MAX_CONSECUTIVE_LOSSES → blocked | N consecutive losers | Losing streak |
| 4 | No limits (all 0) → always allowed | All checks return True | Disabled state |
| 5 | Alert sent on first breach only | 1 alert per day per limit | Alert dedup |
| 6 | Reset at UTC midnight | Counters refresh | Daily reset |
| 7 | Poll refreshes from MT5 deals | Real data, not stale counters | No manual state |

---

## 17–25. Integration & Infrastructure Modules

### 17. Telegram Listener
- Connect to configured source chats
- Forward new messages to signal parser
- Forward replies to reply handler
- Detect message edits → forward to edit handler
- Detect message deletes → forward to delete handler
- Auto-reconnect with exponential backoff
- Session reset after N hours

### 18. Telegram Alerter
- send_message() with rate limiting
- reply_to_message() for threading
- send_debug() bypasses cooldown
- Admin chat targeting

### 19. Pipeline Orchestration
- execute_signal_plans() — multi-order execution
- handle_reentry() — full risk guard gauntlet
- Risk guard chain: circuit_breaker → daily_guard → exposure_guard → validate
- Order fingerprint with level_id
- Group registration after execution

### 20. Order Lifecycle Manager
- Track pending order expiration
- Cancel orders exceeding TTL
- Magic number filtering

### 21. MT5 Watchdog
- Periodic connection health check
- Auto-reinit on connection loss
- Weekend/market-close detection
- Exponential backoff

### 22. Reply Command Executor
- Close position by ticket
- Partial close by percent
- Move SL on specific ticket
- Move TP on specific ticket
- Breakeven on specific ticket
- Position existence check before execute
- Symbol consistency guard

### 23. Message Update Handler
- Detect edit to processed signal
- CANCEL_ORDER if no filled positions
- CANCEL_GROUP_PENDING if mixed state
- ignore if all filled

### 24. Range Monitor
- Price-cross detection (not proximity)
- 30-second debounce per level
- Symbol-grouped tick requests
- Emit events to Pipeline via callback
- **G11**: SL breach cancels all pending plans

### 25. Signal State Manager
- State machine: PENDING → PARTIAL → COMPLETED → EXPIRED
- In-memory registry + DB persistence
- Query pending re-entry levels
- Only tracks range/scale_in (not single)
- Expire signals past TTL

---

## 26. Noval Channel Config (G7-G12)

**Module:** `tests/test_noval_config.py`
**Purpose:** Comprehensive tests for Noval channel config and G7-G12 features with Gold (XAUUSD).

### 26.1 G9: Step-based P2/P3 Levels (`reentry_step_pips=20`)

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 1 | SELL 3 levels step=20pip | P1=3340, P2=3342, P3=3344 | Level calculation |
| 2 | SELL levels ascending | P1 < P2 < P3 | Direction correctness |
| 3 | P1=initial, P2/P3=range_N labels | Correct labels | Plan identification |
| 4 | BUY 3 levels step=20pip | P1=3347, P2=3345, P3=3343 | BUY direction |
| 5 | BUY levels descending | P1 > P2 > P3 | Direction correctness |
| 6 | step=0 → zone-spread fallback | Legacy spread behavior | Fallback guard |
| 7 | No entry_range → single | 1 plan only | Missing data guard |
| 8 | max_entries=1 → single | 1 plan only | Config override |
| 9 | Narrow zone: steps exceed zone | P3 goes beyond zone_high | Expected behavior |

### 26.2 G12a: `per_entry` Volume Split

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 10 | 3 plans × 0.01 → each 0.01 | [0.01, 0.01, 0.01] | Core per_entry logic |
| 11 | 1 plan × 0.01 | [0.01] | Single plan |
| 12 | 5 plans × 0.02 → total 0.10 | Each 0.02, sum=0.10 | Total exposure check |
| 13 | equal: 0.03 / 3 → 0.01 each | Divides, not copies | Contrast with per_entry |
| 14 | equal: lot too small → lot_min | Each ≥ 0.01 | Minimum enforcement |
| 15 | Empty plans → empty | [] | Guard |

### 26.3 Noval Full Integration

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 16 | SELL 3 entries + per_entry volumes | 3 plans, each 0.01 | End-to-end SELL |
| 17 | BUY 3 entries + per_entry volumes | 3 plans, each 0.01 | End-to-end BUY |
| 18 | Level IDs sequential [0,1,2] | Proper tracking IDs | Re-entry tracking |

### 26.4 G1: Min SL Distance Boundary (`min_sl_distance_pips=20`)

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 19 | Price far from SL (120pip) → OK | ≥ 20 → accept | Normal case |
| 20 | Price close to SL (10pip) → REJECT | < 20 → reject | Guard fires |
| 21 | Price exactly at boundary (20pip) | ≥ 20 → accept | Boundary: exact |
| 22 | Price 1 pip inside (19pip) → REJECT | < 20 → reject | Boundary: just under |
| 23 | BUY distance check (190pip) → OK | ≥ 20 → accept | BUY side |

### 26.5 G7: Max Re-entry Distance Boundary (`max_reentry_distance_pips=10`)

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 24 | Price at level → drift=0 → OK | ≤ 10 → accept | Exact match |
| 25 | Price 5pip past → OK | ≤ 10 → accept | Within range |
| 26 | Price exactly at max (10pip) → OK | ≤ 10 → accept | Boundary: exact |
| 27 | Price 11pip past → REJECT | > 10 → reject | Boundary: just over |
| 28 | Price 80pip past → REJECT | >> 10 → reject | Far exceeded |
| 29 | Disabled (0) → skip check | No rejection | Feature toggle |

### 26.6 G5: Re-entry Tolerance (`reentry_tolerance_pips=5`)

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 30 | SELL eff_level = level - 0.50 | 3342→3341.5 | Calculation check |
| 31 | BUY eff_level = level + 0.50 | 3345→3345.5 | BUY direction |
| 32 | SELL price 3341.6 ≥ eff → TRIGGER | Early trigger | Within tolerance |
| 33 | SELL price 3341.4 < eff → NO | Not yet reached | Below tolerance |
| 34 | tolerance=0 → exact required | Level = eff_level | Disabled check |
| 35 | SELL P3 tolerance | 3343.7 ≥ 3343.5 → trigger | P3 validation |

### 26.7 G11: SL Breach → Cancel All

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 36 | SELL price=SL → BREACHED | price ≥ SL | Exact SL hit |
| 37 | SELL price < SL → not breached | In profit zone | No breach |
| 38 | SELL price > SL → BREACHED | Past SL | Beyond SL |
| 39 | BUY price=SL → BREACHED | price ≤ SL | Exact SL hit |
| 40 | BUY price > SL → not breached | In profit zone | No breach |
| 41 | SELL price far below SL → OK | In profit | False positive guard |

### 26.8 G12b: Reply BE Lock Pips (`reply_be_lock_pips=10`)

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 42 | BUY entry=3345 → SL=3346.0 | +$1.00 lock | BUY offset |
| 43 | SELL entry=3340 → SL=3339.0 | -$1.00 lock | SELL offset |
| 44 | lock=0 → SL=entry | No offset | Disabled |
| 45 | lock=1 (default) → SL=entry+0.1 | $0.10 offset | Default config |
| 46 | Lock distance math | 10×0.1=1.0 | Calculation |

### 26.9 Full Scenario: SELL XAUUSD 3340-3347 SL 3352

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 47 | Plan levels [3340, 3342, 3344] | Correct step calc | Integration |
| 48 | Volumes [0.01, 0.01, 0.01] | per_entry mode | Volume |
| 49 | P1 SL distance 120pip ≥ 20 | ACCEPT | Guard pass |
| 50 | P2 SL distance 100pip ≥ 20 | ACCEPT | Guard pass |
| 51 | P3 SL distance 80pip ≥ 20 | ACCEPT | Guard pass |
| 52 | P2 tolerance trigger (3341.6) | TRIGGER (≥3341.5) | Early trigger |
| 53 | P2 max distance boundary | 10→OK, 15→REJECT | Distance guard |
| 54 | SL breach at 3352 | Cancel all pending | SL guard |
| 55 | Reply BE lock SELL P1 | SL=3339.0 | Offset calc |
| 56 | P3 still inside zone | 3344 < 3347 | Zone check |

### 26.10 Full Scenario: BUY XAUUSD 3340-3347 SL 3328

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 57 | Plan levels [3347, 3345, 3343] | Correct step calc | Integration |
| 58 | All levels above SL=3328 | level > 3328 | Safety check |
| 59 | Reply BE lock BUY P1 | SL=3348.0 | Offset calc |
| 60 | SL breach at 3327 | price ≤ SL | BUY breach |

### 26.11 Guard Combinations

| # | Test Case | Expected | Purpose |
|---|-----------|----------|---------|
| 61 | Crossed + too far → REJECT | max_distance wins | Guard priority |
| 62 | Crossed + within distance + SL OK → TRIGGER | All pass | Happy path |
| 63 | Crossed + within distance + SL too close → REJECT | SL guard wins | SL priority |

---

## Summary Statistics

| Category | Modules | Functions | Test Cases (est.) |
|----------|---------|-----------|-------------------|
| Signal Parser | 7 detectors + parser | ~12 | ~66 |
| Validation | signal_validator | ~8 | ~19 |
| Risk & Order | risk_manager, order_builder | ~7 | ~29 |
| Strategy | entry_strategy | ~8 | ~17 |
| Safety | circuit_breaker, exposure_guard, daily_risk_guard | ~12 | ~22 |
| Commands | command_parser, reply_action_parser | ~2 | ~26 |
| Config | channel_manager, models | ~10 | ~20 |
| Storage | storage | ~20 | ~13 |
| Execution | trade_executor, pipeline | ~10 | ~10 |
| Background | trade_tracker, position_manager, range_monitor | ~15 | ~20 |
| Telegram | listener, alerter | ~8 | ~7 |
| Infrastructure | lifecycle_mgr, watchdog, update_handler, state_mgr | ~10 | ~5 |
| **Noval Config (G7-G12)** | **entry_strategy, pipeline guards, reply executor** | **~15** | **~63** |
| **Total** | **~28 modules** | **~135+** | **~317** |

```
tests/
├── conftest.py                      # Shared fixtures
├── __init__.py
├── TEST_CASES.md                    # Test case docs
├── signal_parser/
│   ├── test_cleaner.py              # 13 tests
│   ├── test_side_detector.py        # 12 tests
│   ├── test_symbol_detector.py      # 13 tests
│   ├── test_entry_detector.py       # 18 tests
│   ├── test_sl_detector.py          # 10 tests
│   ├── test_tp_detector.py          # 14 tests
│   └── test_parser.py              # 17 tests
├── test_signal_validator.py         # 24 tests
├── test_risk_manager.py             # 12 tests
├── test_circuit_breaker.py          # 11 tests
├── test_command_parser.py           # 17 tests
├── test_reply_action_parser.py      # 25 tests
├── test_models.py                   # 17 tests
├── test_entry_strategy.py           # 24 tests
├── test_channel_manager.py          # 11 tests
├── test_exposure_guard.py           # 8 tests
└── test_noval_config.py             # 63 tests (G7-G12)
```