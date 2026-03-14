# CHANGELOG

## 0.1.0 - 2026-03-14

### Added
- Project foundation: `requirements.txt`, `.env.example`, `.gitignore`, `main.py`, `README.md`
- Configuration: `config/settings.py` with typed env loading and validation
- Data contracts: `ParsedSignal`, `ParseFailure`, `TradeDecision`, `ExecutionResult`, enums (`Side`, `OrderKind`, `SignalStatus`) in `core/models.py`
- Signal parser pipeline:
  - `core/signal_parser/cleaner.py` — message normalization
  - `core/signal_parser/symbol_detector.py` — symbol alias detection
  - `core/signal_parser/side_detector.py` — BUY/SELL/LONG/SHORT detection
  - `core/signal_parser/entry_detector.py` — entry/market/limit/stop detection
  - `core/signal_parser/sl_detector.py` — SL extraction
  - `core/signal_parser/tp_detector.py` — TP extraction (TP, TP1-TP3)
  - `core/signal_parser/parser.py` — orchestrator with fingerprint generation
- Signal validation: `core/signal_validator.py` — SL/TP coherence, entry distance, signal age
- Risk management: `core/risk_manager.py` — fixed lot + risk-based sizing
- Storage: `core/storage.py` — SQLite for signals, orders, events
- MessageEdited handler: `core/message_update_handler.py` — prototype for edit detection
- Utils:
  - `utils/logger.py` — structured JSON logging via loguru
  - `utils/symbol_mapper.py` — alias→broker symbol mapping (50+ symbols)
- Tools:
  - `tools/parse_cli.py` — parser debug CLI
  - `tools/benchmark.py` — parser throughput/latency benchmark
- Documentation:
  - `docs/SIGNAL_DATASET.md` — signal format samples
  - `docs/UNSUPPORTED_FORMATS.md` — tracked unsupported formats
