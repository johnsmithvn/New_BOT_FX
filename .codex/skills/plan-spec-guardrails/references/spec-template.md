# Spec Template Reference

Use this reference when the user explicitly asks for a spec.

## Required Path

- Store each feature spec at `/specs/<feature>/spec.md`.

## Required Sections

Keep specs concise and include only these core sections:

1. `Overview`
2. `Requirements`
3. `Design`

Add `Open Questions` only for a new initial spec when decisions are missing.

## Skeleton

```md
# <Feature Name>

## Overview
- <feature intent>
- <motivation>

## Requirements
- The system MUST <required behavior>.
- The system SHOULD <recommended behavior>.
- The system MAY <optional behavior>.

## Design
- <high-level architecture choice>
- <key framework or dependency choices>
- <constraints and compatibility notes>
```

## Requirements Style

- Write declarative statements.
- Use RFC 2119 modal verbs: `MUST`, `SHOULD`, `MAY`.
- Avoid implementation-level detail unless necessary for intent clarity.
