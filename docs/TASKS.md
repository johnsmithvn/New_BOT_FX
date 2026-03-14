# TASKS

## Current Phase
- `P1 - Signal Understanding (R2)`

## High Priority
- [x] Define `ParsedSignal` schema in code (`symbol`, `side`, `entry`, `sl`, `tp`, source metadata).
- [x] Implement message cleaner for uppercase normalization and noise cleanup.
- [x] Implement symbol detector with alias map and broker symbol normalization.
- [x] Implement side detector for BUY/SELL and LONG/SHORT mapping.
- [x] Implement entry detector for market, explicit entry, LIMIT, STOP patterns.
- [x] Implement SL detector with strict numeric extraction.
- [x] Implement TP detector supporting `TP`, `TP1`, `TP2`, `TP3`.
- [x] Implement parser orchestrator that returns normalized output or explicit parse failure reason.
- [x] Implement signal fingerprint generator (hash of normalized fields).
- [x] Add parser guard for extremely large or malformed messages.
- [x] Implement entry distance validation logic.
- [x] Implement signal fingerprint generator.
- [x] Add structured logging for signal_received event.
- [x] Add structured logging for parse_success and parse_failed.
- [x] Add structured logging for validation_rejected.
- [x] Add structured logging for order_submitted and order_result.
- [x] Implement signal age validation logic
- [x] Implement risk manager for trade volume calculation
- [x] Add configuration for fixed lot or risk percent
- [x] Ensure order decision uses correct Bid/Ask reference prices

## Medium Priority additions
- [x] Create signal format dataset for parser testing.
- [x] Implement MessageEdited handler prototype.
- [x] Ensure every log entry contains signal fingerprint.
- [x] Add database event storage for signal lifecycle.

## Medium Priority
- [x] Add structured parser logs: `parse_success`, `parse_failed`, reason code.
- [x] Add deterministic ordering for multiple TP values.
- [x] Add TODO list for unsupported formats discovered during testing.

## Low Priority
- [x] Add parser benchmark script for throughput and latency snapshot.
- [x] Add parser debug CLI to parse a local text sample file.

## Completed
- [x] Create `docs/PROJECT.md`.
- [x] Create `docs/ARCHITECTURE.md`.
- [x] Create `docs/RULES.md`.
- [x] Create `docs/ROADMAP.md`.
- [x] Create `docs/PLAN.md`.
- [x] Create `docs/AGENT.md`.
- [x] Create `README.md`.
- [x] Create `CHANGELOG.md`.
- [x] Create project virtual environment.
- [x] Create `config/settings.py`.
- [x] Create `core/models.py`.
- [x] Create `utils/logger.py`.
- [x] Create `utils/symbol_mapper.py`.
- [x] Create `core/storage.py`.
- [x] Create `core/signal_validator.py`.
- [x] Create `core/risk_manager.py`.
- [x] Create signal parser pipeline (7 modules).
- [x] Create `main.py`.
- [x] Create `tools/parse_cli.py`.
- [x] Create `docs/SIGNAL_DATASET.md`.
- [x] Create `core/message_update_handler.py`.
- [x] Create `docs/UNSUPPORTED_FORMATS.md`.
- [x] Create `tools/benchmark.py`.

## Note
- Parser unit tests not generated per project rule: "Do NOT generate automated tests".
- User is responsible for manual testing via `tools/parse_cli.py` and `docs/SIGNAL_DATASET.md`.
