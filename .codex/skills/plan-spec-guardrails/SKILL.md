---
name: plan-spec-guardrails
description: Strictly enforce plan-first and spec-first workflow guardrails. Use when users explicitly ask for a plan or spec, or when plan/spec confirmation gates are required before implementation. Enforce concise pre-implementation planning, no code changes before plan approval, and spec structure at /specs/feature-name/spec.md with only Overview, Requirements, and Design sections.
---

# Plan Spec Guardrails

## Overview

Enforce strict plan and spec gates before implementation. Require explicit approval before mutating work and standardize spec placement and structure when specs are requested.

## Handle Plan Requests

1. Detect explicit requests for a plan.
2. Provide a concise plan summary before deep research.
3. Avoid extensive pre-plan exploration; gather only minimal context required to make the first plan coherent.
4. Ask for confirmation that the plan is acceptable before any code changes.
5. Ask up to four clarifying questions only when requirements are ambiguous or tradeoffs affect design.
6. Present clear options (for example A/B/C) when multiple choices are viable.
7. Refuse to modify code or run mutating operations until the user accepts the plan.

For examples and response patterns, read `references/plan-behavior.md`.

## Handle Spec Requests

1. Detect explicit requests for a spec.
2. Ensure `/specs` exists at project root; create it if missing.
3. Create or update spec files at `/specs/<feature>/spec.md`.
4. Keep specs concise and markdown-only.
5. Include exactly these core sections:
   - `Overview`
   - `Requirements`
   - `Design`
6. Write requirements as declarative statements using RFC 2119 modal verbs (`MUST`, `SHOULD`, `MAY`).
7. Avoid extensive code exploration before drafting an initial spec.
8. Add an `Open Questions` section only for initial specs when unresolved decisions remain.
9. Ask the user to review and confirm the spec before implementation work.

For section skeletons and requirement examples, read `references/spec-template.md`.

## Non-Spec Requests

Do not create a spec when the user does not explicitly request one.

## Enforcement Rules

1. Treat these rules as strict defaults when the skill is invoked.
2. Prioritize concise outputs and avoid unnecessary process detail.
3. Keep behavior deterministic and gate implementation on explicit user confirmation.
