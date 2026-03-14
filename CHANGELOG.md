# CHANGELOG

## 0.2.0 - 2026-03-14

### Added
- Telegram listener: `core/telegram_listener.py` — Telethon user session with NewMessage and MessageEdited handlers
- Order builder: `core/order_builder.py` — BUY→ASK / SELL→BID price reference rule, decision matrix, MT5 request payload construction
- Trade executor: `core/trade_executor.py` — MT5 init/shutdown, bounded retry (3 attempts), 35+ retcode mappings, pending order management
- Order lifecycle manager: `core/order_lifecycle_manager.py` — async monitoring loop, auto-cancel pending orders exceeding TTL
- MT5 watchdog: `core/mt5_watchdog.py` — periodic health check with bounded reinit attempts
- Full pipeline wiring in `main.py` — listener→parser→validator→risk→builder→executor→storage with async lifecycle and graceful shutdown
- Multi-TP handling: first TP sent to MT5, remaining TPs logged for manual management

### Changed
- `core/signal_validator.py` — added spread threshold check, max open trades gate, duplicate signal filtering
- `main.py` — rewritten as async Bot class with full pipeline integration
- `requirements.txt` — pinned `numpy<2` for MetaTrader5 compatibility

## 0.1.0 - 2026-03-14

### Added
- Project foundation: `requirements.txt`, `.env.example`, `.gitignore`, `main.py`, `README.md`
- Configuration: `config/settings.py` with typed env loading and validation
- Data contracts: `ParsedSignal`, `ParseFailure`, `TradeDecision`, `ExecutionResult`, enums in `core/models.py`
- Signal parser pipeline (7 modules): cleaner, symbol/side/entry/SL/TP detectors, orchestrator with fingerprint
- Signal validation: `core/signal_validator.py` — SL/TP coherence, entry distance, signal age
- Risk management: `core/risk_manager.py` — fixed lot + risk-based sizing
- Storage: `core/storage.py` — SQLite for signals, orders, events
- MessageEdited handler prototype: `core/message_update_handler.py`
- Utils: `utils/logger.py` (structured JSON logging), `utils/symbol_mapper.py` (50+ aliases)
- Tools: `tools/parse_cli.py`, `tools/benchmark.py`
- Documentation: `docs/SIGNAL_DATASET.md`, `docs/UNSUPPORTED_FORMATS.md`
