# ROADMAP

## Milestone R1 - Foundation and Safety Baseline ✅
- Goal:
  - Establish a stable project base and explicit safety constraints.
- Expected outcomes:
  - Clear architecture and operating rules documented.
  - Core repo structure prepared for bot runtime.
  - Baseline observability and safety policy defined.

## Milestone R2 - Signal Understanding ✅
- Goal:
  - Reliably transform Telegram signal text into normalized trade intent.
- Expected outcomes:
  - Parser pipeline handles primary message variants.
  - Symbol alias normalization is consistent.
  - Parse quality and failure reasons are observable.

## Milestone R3 - Trade Decision and Execution ✅
- Goal:
  - Convert validated signals into correct MT5 order actions.
- Expected outcomes:
  - Deterministic market/pending order decisions.
  - SL/TP and spread gates enforced before order send.
  - MT5 execution outcomes captured and traceable.

## Milestone R3.5 - Order Lifecycle Safety ✅

Goal:
- Prevent stale or delayed signal execution.

Expected outcomes:
- Pending order expiration logic implemented.
- Signal age validation before execution.
- Entry distance protection enforced.

## Milestone R4 - Reliability for 24/7 Runtime ✅
- Goal:
  - Operate continuously with recoverable failures and state continuity.
- Expected outcomes:
  - Duplicate filtering and audit persistence active.
  - Bounded retry and reconnect behavior validated.
  - Runtime logging supports incident diagnosis.

## Milestone R5 - Production Operations ✅
- Goal:
  - Reach repeatable deployment and maintenance quality.
- Expected outcomes:
  - VPS deployment runbook and operating playbook ready.
  - Monitoring and alerting strategy documented.
  - Controlled release process for updates defined.

## Milestone R6 - Controlled Expansion ✅
- Goal:
  - Extend capabilities without reducing safety and determinism.
- Expected outcomes:
  - Additional symbols/formats added via modular parser updates.
  - Advanced execution options evaluated (example: multi-TP split).
  - Backward-compatible evolution strategy documented.

## Milestone R7 - Channel-Driven Multi-Order Strategy ✅
- Goal:
  - Support per-channel trading strategies with multi-order execution from a single signal.
- Expected outcomes:
  - Entry strategy engine: single, range, and scale_in modes.
  - Volume split algorithms: equal, pyramid, risk_based.
  - Signal state machine for multi-order lifecycle tracking.
  - Background price-cross re-entry monitor with debounce.
  - Pipeline refactor: sole orchestrator for all order execution.
  - Backward compatible: single mode = existing behavior.

## Milestone R8 - Smart Signal Group Management ✅
- Goal:
  - Manage all orders from one signal as a coordinated group.
  - Coordinated SL, selective close, auto-breakeven across group.
- Expected outcomes:
  - Every signal creates a managed OrderGroup (1 or N orders).
  - Group trailing SL with multi-source calculation (zone, signal, fixed, trail).
  - Reply-based selective close (highest/lowest entry, oldest).
  - Auto-breakeven after partial group close.
  - DB persistence (signal_groups table) for restart recovery.
  - STOP order filter: MARKET/LIMIT fallback when STOP not allowed.

