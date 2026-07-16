# Codebase context capability

Gather the minimum repository evidence needed to derive a technical appendix for the `spec` skill. This prompt may be executed by an isolated worker or followed sequentially by the main agent. Do not require a particular orchestration API.

## Inputs

- Feature slug and original product intent.
- Repository root.
- Selected mode: `quick` or `deep`.
- Scratch output path: `<scratch>/_context.md`.

## Evidence budget

For `quick`:

- active repository instruction files and relevant manifests;
- one closest analogous feature;
- nearest tests or contract source.

For `deep`:

- active instructions, manifests, and architecture or contract documents;
- 2-3 analogous paths;
- affected producers, consumers, generated clients, and tests;
- migration, rollback, release, and compatibility policy where relevant.

Stop at the selected budget unless a missing source would make a material claim unsafe.

## Output

Write only `<scratch>/_context.md` with this structure:

```markdown
# Context for <slug>

## Evidence ledger
| Claim | Status | Source | Notes |
|---|---|---|---|
| ... | documented / observed / tested / assumption / conflict / unknown | `path:line` or command | ... |

## Stack and repository layout
Current languages, runtimes, frameworks, package boundaries, and likely placement.

## Active conventions
Naming, errors, validation, authorization, storage, events, logging, testing, and generated-code rules that are relevant to this feature.

## Closest existing features
The analogous paths examined, what is reusable, and what must not be generalized.

## Producers, consumers, and contracts
Affected surfaces and contract sources. Include code-generation or compatibility steps when evidenced.

## Migration and rollback policy
The active repository policy with provenance. If none is established, write `Unknown - no repository policy found`.

## Legacy signals and conflicts
Deprecations, compatibility shims, migration-away plans, dead paths, newer competing patterns, and credible sources that disagree.

## Observable product questions
Only unresolved questions whose answer changes user-visible behavior or a product guarantee.

## Technical unknowns and follow-ups
Implementation questions that belong in the appendix rather than in the user interview.
```

## Status rules

- `documented`: an active repository policy or approved contract states the claim.
- `observed`: current code or configuration demonstrates the claim.
- `tested`: an executable test enforces the claim.
- `assumption`: the claim is plausible but not established.
- `conflict`: credible sources disagree.
- `unknown`: the inspected evidence does not answer it.

Use the strongest accurate status; do not upgrade `observed` to `documented` or `tested`. A current implementation is evidence, not automatically the desired future design.

## Method

1. Read active `AGENTS.md`, `CLAUDE.md`, editor rules, relevant manifests, and repository documentation. Distinguish active instructions from archived material.
2. Confirm layout with file discovery rather than assumptions.
3. Inspect the analogous paths allowed by the mode budget, including call sites and nearest tests.
4. Search for legacy and conflict signals before recommending reuse.
5. Record every material derived claim in the evidence ledger.
6. Ask no implementation question of the user. Convert only observable consequences into product questions.
7. Write the context file and return `Wrote <scratch>/_context.md`.

Do not modify source code, the final spec, or any file outside the scratch context path.
