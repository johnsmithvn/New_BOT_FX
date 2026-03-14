# AGENT

## Purpose
- Define mandatory operating protocol for AI coding agents in this repository.
- Minimize hallucination, reduce unnecessary file reads, and keep execution aligned to phase scope.

## Startup Procedure
1. Read `docs/PROJECT.md`.
2. Read `docs/ARCHITECTURE.md`.
3. Read `docs/RULES.md`.
4. Read `docs/ROADMAP.md`.
5. Read `docs/PLAN.md`.
6. Read `docs/TASKS.md`.
7. Confirm current phase and active priorities.
8. Select the next unchecked task from `High Priority`, then `Medium`, then `Low`.

## Required File Reading Order
1. `PROJECT.md`
2. `ARCHITECTURE.md`
3. `RULES.md`
4. `ROADMAP.md`
5. `PLAN.md`
6. `TASKS.md`

## Task Execution Rules
- Execute tasks for the current phase only.
- Keep changes minimal and scoped to selected task.
- Reuse existing contracts and module boundaries from `ARCHITECTURE.md`.
- If required information is missing, write `TODO` and stop guessing.
- After implementation, run relevant checks/tests when available.

## Workflow Lifecycle
1. Read docs in required order.
2. Choose next task.
3. Implement task.
4. Update `docs/TASKS.md` status.
5. Repeat until all current-phase tasks are complete.

## Phase Transition Rules
- Transition is allowed only when all `High Priority` and `Medium Priority` tasks are complete.
- On transition:
  - Update `docs/PLAN.md` statuses.
  - Set next phase to `in progress`.
  - Regenerate `docs/TASKS.md` for the new current phase.
- Do not skip phases without explicit documented decision.

## Documentation Update Rules
- Update docs whenever architecture, behavior, or scope changes.
- Required sync points:
  - `ARCHITECTURE.md` for module/data-flow changes
  - `PLAN.md` for phase status changes
  - `TASKS.md` for task state changes
- Keep updates concise and factual.

## Anti-Hallucination Safeguards
- Never claim a file/function exists without reading it.
- Never claim tests pass without running relevant checks.
- Never claim live MT5 execution success without verified result data.
- Mark uncertainty explicitly:
  - `TODO: missing input`
  - `TODO: pending verification`
  - `TODO: decision required`

## Context Discipline
- Prefer targeted reads over full-repo reads.
- Read only files needed for the active task plus required docs.
- Avoid loading unrelated docs/code into working context.
