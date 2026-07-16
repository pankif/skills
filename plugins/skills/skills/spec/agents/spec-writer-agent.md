# Spec writer capability

Assemble the final public `SPEC.md` for the `spec` skill. This prompt may be executed by an isolated worker or followed sequentially by the main agent. Write no implementation code and do not require a particular orchestration platform.

## Inputs

- Original product intent.
- Selected mode.
- `<scratch>/_interview.md`.
- `<scratch>/_context.md`.
- Final output path `<out>/SPEC.md`.

Read every input end to end before drafting.

## Output

Write only `<out>/SPEC.md`, then return `Wrote <out>/SPEC.md`.

Use this exact structure:

```markdown
---
title: '<Feature name>'
domain: '<product area or unknown>'
last_updated: <YYYY-MM-DD>
---

# <Feature name>

## Purpose
...

## Glossary
...

## Actors
...

## User-facing behavior
...

## Flows
...

## States and transitions
...

## Invariants
...

## Edge cases
...

## Success criteria
...

## Out of scope
...

## Open questions
...

---

## Technical appendix
> Derived from repository evidence; this section is implementation guidance, not the product contract.

### Evidence and conflicts
...

### Stack & placement
...

### Data model and contracts
...

### Migration & rollback
...

### Integration points
...

### Risks & follow-ups
...
```

## Product-half rules

1. Use the user's vocabulary.
2. Trace every behavior to the intent or interview notes. Never derive product behavior from code alone.
3. Express states, failures, timing, retention, recovery, and external-data guarantees in observable terms.
4. Put unresolved matters in `Open questions` instead of filling gaps.
5. Use `(none captured)` for an intentionally empty section.
6. If the input contains multiple independent features, list the split as the first open question rather than silently merging them.
7. Keep implementation names, protocols, libraries, and file paths below the appendix boundary.

## Technical-appendix rules

1. Derive claims from `_context.md`; preserve its exact file paths and symbol names.
2. Give each material claim a provenance and status: `documented`, `observed`, `tested`, `assumption`, `conflict`, or `unknown`.
3. Treat code as evidence, not as an unquestionable future requirement. Preserve legacy warnings and competing patterns.
4. Never resolve an evidence conflict silently. State both sides and the follow-up needed.
5. Follow the repository's documented migration and rollback policy. Do not require both directions unless that policy does. If no policy was found, state `Unknown - no repository policy found` and record the risk.
6. Do not invent schemas, endpoints, services, or code-generation steps. Mark unsupported detail as unknown.

## Final pass

Before writing, verify:

- all required H2 headings exist exactly once and in order;
- a horizontal rule separates `Open questions` from `Technical appendix`;
- the appendix begins with a blockquote warning;
- no product claim lacks an intent/interview source;
- no technical claim lacks provenance and status;
- conflicts and unknowns remain visible.

This pass checks drafting discipline, not semantic correctness. Explicit user acceptance remains required before applying the `human-reviewed` label.
