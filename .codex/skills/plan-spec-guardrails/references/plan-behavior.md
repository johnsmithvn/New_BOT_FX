# Plan Behavior Reference

Use this reference when the user explicitly asks for a plan.

## Required Flow

1. Provide a concise plan summary first.
2. Avoid extensive research before presenting that first plan.
3. Ask for plan confirmation before mutating work.
4. Ask clarifying questions only when necessary, up to four total.
5. Present option-based choices when clear alternatives exist.

## Output Pattern

```md
Summary:
- <short task summary>
- <main requirements>

Proposed Plan:
1. <step 1>
2. <step 2>
3. <step 3>

Questions (only if needed):
- A) <option A>
- B) <option B>
- C) <option C>

Confirmation:
Does this plan look good before I make any code changes?
```

## Hard Gates

- Do not edit files before plan acceptance.
- Do not run mutating commands before plan acceptance.
- Do not do deep exploratory work before giving the first concise plan.
