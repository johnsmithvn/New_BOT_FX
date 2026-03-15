# PLAN

## Current Phase
- Phase: `P3 - Reliability for 24/7 Runtime (aligned to R4)`
- Goal:
  - Ensure runtime resilience and state continuity.

## Execution Phases

### P0 - Foundation and Safety Baseline
- Roadmap reference: `R1`
- Goal:
  - Establish project baseline, rules, and documentation contracts.
- Major deliverables:
  - Documentation system in `docs/`
  - Initial safety and anti-hallucination rules
  - Base repository structure decisions
- Status: `complete`

### P1 - Signal Understanding
- Roadmap reference: `R2`
- Goal:
  - Implement robust parsing and normalization pipeline.
- Major deliverables:
  - Message cleaner and detectors (symbol, side, entry, SL, TP)
  - Normalized `ParsedSignal` contract
  - Parser test coverage for major message variants
- Status: `complete`
Success Criteria:
- Parser handles at least 90% of known signal formats.
- Unknown formats must produce explicit parse failure reason.
- Parser must never crash on malformed or noisy messages.
- Signal message dataset for parser testing
Parser Safety Rule

All parser detectors must be exception-safe.

Malformed or incomplete messages must never crash the parser.
Instead, the parser must return a structured parse_failed result
with an explicit failure reason.

Examples:
- missing numeric values
- malformed price formats
- unexpected text structure

### P2 - Trade Decision and Execution
- Roadmap reference: `R3`
- Goal:
  - Build deterministic order decision and MT5 execution flow.
- Major deliverables:
  - Order type decision matrix using live bid/ask
  - MT5 request builder and executor with bounded retry
  - Execution result normalization and logging
- Status: `complete`

### P3 - Reliability for 24/7 Runtime
- Roadmap reference: `R4`
- Goal:
  - Ensure runtime resilience and state continuity.
- Major deliverables:
  - SQLite dedupe + audit storage
  - Reconnect/retry hardening
  - Operational error handling and incident-ready logs
- Status: `complete`

### P4 - Production Operations
- Roadmap reference: `R5`
- Goal:
  - Prepare repeatable deployment and operations lifecycle.
- Major deliverables:
  - VPS deployment runbook
  - Monitoring/alerting strategy
  - Release/update procedure
  - Daily risk guard (MAX_DAILY_TRADES, MAX_DAILY_LOSS, MAX_CONSECUTIVE_LOSSES)
  - Startup position sync
- Status: `in progress`

### P5 - Controlled Expansion
- Roadmap reference: `R6`
- Goal:
  - Add features while preserving safety baseline.
- Major deliverables:
  - Extended parser support for additional formats/symbols
  - Optional advanced execution behaviors
  - Compatibility and regression safeguards
- Status: `pending`

## Phase Completion Rule
- Current phase is complete only when all `High Priority` and `Medium Priority` tasks in `docs/TASKS.md` are checked.
- On completion:
  - Mark current phase `complete`
  - Move next phase to `in progress`
  - Regenerate `docs/TASKS.md` for the new current phase
