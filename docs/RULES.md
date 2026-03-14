# AI_AGENT_RULES.md

Rules for AI coding agents working on this repository.
These rules control **agent behavior**, not project architecture or business logic.

---

# 1. Knowledge Honesty

The agent MUST never invent or assume information about the repository.

Rules:

* Never fabricate facts about:

  * repository files
  * APIs
  * broker behavior
  * runtime state
  * external systems

* If required information is missing, write:

```
TODO: missing input
```

* If unsure about execution impact, write:

```
TODO: decision needed
```

Always distinguish clearly between:

* **Observed facts** – verified from repository files
* **Assumptions** – clearly labeled guesses
* **Proposed changes** – modifications suggested by the agent

Do not present assumptions as facts.

---

# 2. Anti-Hallucination Safeguards

Before writing or modifying code:

1. Verify that the target file exists.
2. If it does not exist, explicitly create it.
3. Inspect related files before making changes.

Before claiming task completion:

* confirm modified files
* verify expected content
* run tests or checks if available

Never claim external side effects unless verified in code or logs.

If validation cannot be completed, record:

```
TODO: pending validation
```

---

# 3. Scope Control

The agent MUST work **only within the current task scope**.

---

# Workflow

## Before Writing Code

1. Read `rules.md`.

2. If context is missing or the project behavior is unclear, read the following documents:

   - `docs/PROJECT.md`
   - `docs/ROADMAP.md`
   - `docs/ARCHITECTURE.md`

3. Read `docs/PLAN.md` to understand the current phase of development.

4. Read `docs/TASKS.md`.

5. Update `docs/TASKS.md` to mark the current task as:


IN PROGRESS


6. Implement **only the current task**.






---

## After Implementation

1. Update `docs/TASKS.md`

   - Mark the task as completed.
   - Add follow-up tasks if necessary.

2. Update `docs/PLAN.md` if the phase or milestone progress has changed.

3. Update `docs/ARCHITECTURE.md` if:

   - module behavior changed
   - data flow changed
   - interfaces changed

---

# Restrictions

The agent MUST NOT:

- Refactor unrelated modules
- Change architecture without explicit instruction
- Rename files across the repository
- Modify configuration defaults unnecessarily
- Introduce large refactors

If a larger change appears necessary, record:


TODO: architectural change required


Do NOT implement architectural changes automatically.

---

# Mandatory Practices

The agent MUST:

- Mark unknown decisions as `TODO` in documentation.
- Do NOT hide important TODO decisions only inside code comments.
- Keep documentation concise.
- Avoid duplicate long explanations.
- Modify **only files relevant to the current task scope**.
- Do NOT delete or rewrite unrelated files.
- Keep changes **minimal and reversible**.
- Preserve naming consistency with architecture documentation.

---

# Documentation Synchronization

Any behavior change MUST be reflected in the documentation.

Required updates:

- `docs/ARCHITECTURE.md`  
  If module structure or data flow changes.

- `docs/PLAN.md`  
  If phase or milestone progress changes.

- `docs/TASKS.md`  
  For task completion and new tasks.

---

# Missing Context Handling

If required information is missing:


TODO: missing input


The agent MUST NOT guess implementation details.

Stop implementation until the missing input is clarified.

---

# File Verification Rule

Before modifying a file:

1. Verify the file exists in the repository.
2. If the file does not exist, explicitly create it.
3. Inspect related files before making modifications.

---

# Task Completion Verification

Before marking a task as completed, the agent MUST verify:

- All relevant files were modified correctly
- No unrelated files were changed
- Documentation was updated where necessary
- `docs/TASKS.md` status was updated
- `docs/PLAN.md` was updated if phase progress changed
---

# 4. File Modification Rules

When modifying the repository:

* Change **only files relevant to the task**
* Keep modifications **minimal**
* Avoid deleting files unless explicitly required
* Preserve naming conventions
* Avoid rewriting entire files unless necessary

Prefer **small, reversible patches**.

---

# 5. Code Safety Principles

Generated code should follow these principles:

* Prefer small single-responsibility modules
* Use explicit types when possible
* Validate all external inputs
* Fail fast on invalid configuration
* Avoid hidden side effects
* Keep logs structured and actionable

Preferred command:
Avoid:

* silent failures
* magic constants without explanation
* hidden global state

## 5a. Unit Consistency — Pips vs Points

All distance/spread thresholds in this project use **PIPS** as the standard unit.

**NEVER** compare raw price difference against pip-based config directly.
Always convert: `distance_pips = abs(price_a - price_b) / pip_size`

| Symbol | point (MT5) | pip_size | 1 pip = | Example |
|--------|-------------|----------|---------|---------|
| XAUUSD | 0.01 | 0.1 | $0.10 | 2030.0 → 2030.1 = 1 pip |
| EURUSD | 0.00001 | 0.0001 | 1 pip | 1.08500 → 1.08510 = 1 pip |
| USDJPY | 0.001 | 0.01 | 1 pip | 150.000 → 150.010 = 1 pip |

Config keys using pips:
- `MAX_SPREAD_PIPS` (default 5.0)
- `MAX_ENTRY_DISTANCE_PIPS` (default 50.0)

Config keys using points (MT5 native):
- `DEVIATION_POINTS` (default 20 — passed directly to MT5)
- `MARKET_TOLERANCE_POINTS` (default 5.0 — multiplied by `point` in code)


# Environment

Python dependencies must be installed in a project virtual environment.

---

# 6. Configuration and Secret Safety

The agent MUST NOT place secrets inside the repository.

Never hardcode:

* API keys
* tokens
* passwords
* broker credentials

Credentials must come from:

* environment variables
* secure runtime configuration

Example:

```
ENV variables
config files outside repository
secret managers
```

---

# 7. Retry and Loop Safety

Automated retry logic must always be bounded.

Never generate:

* infinite loops
* uncontrolled retries
* recursion without limits

All retry systems must include:

* maximum retry count
* backoff delay
* failure logging

---

# 8. Versioning and Change Log Rule

After completing **any task that modifies the repository**, the agent MUST update the change log.

Steps:

1. Update `CHANGELOG.md`
2. Record the change under the correct version
3. Include a short description

Each entry must contain:

* date
* version number
* changed files or modules
* short description of the change

Example:

```
## 0.3.2 - 2026-03-14

Changed
- signal_parser.py
- order_router.py

Description
Fix duplicate signal filtering logic.
```

---

# 9. Version Numbering

Use **Semantic Versioning**:

```
MAJOR.MINOR.PATCH
```

Rules:

PATCH changes include:

- bug fixes
- small improvements
- internal logic fixes

MINOR

* new features
* new modules
* non-breaking behavior changes

MAJOR

* architecture changes
* breaking interface changes

If unsure which version level to use:

```
TODO: version decision needed
```

---

# 10. Documentation Integrity

If code behavior changes, documentation must be updated.

This includes:

* module behavior
* interfaces
* configuration structure
* data flow

Documentation must reflect the **current repository state**.

Never silently change behavior without documenting it.

---

# 11. Completion Checklist

Before declaring a task finished, verify:

* relevant files modified correctly
* no unrelated files changed
* TODO markers added for uncertainties
* CHANGELOG updated
* version updated if required

Only then mark the task as complete.
- `docs/ARCHITECTURE.md`  
  If module structure or data flow changes.

- `docs/PLAN.md`  
  If phase or milestone progress changes.

- `docs/TASKS.md`  
  For task completion and new tasks.
---

# Goal of These Rules

These rules exist to ensure the AI agent:

* does not hallucinate
* does not silently break the project
* keeps changes traceable
* maintains repository safety
* behaves predictably during automated coding tasks

---

# README Requirement

The repository MUST contain a README.md explaining how to run the project from a clean machine.