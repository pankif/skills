---
name: spec
description: >-
  Turn a fuzzy or contested product idea into a reviewable SPEC.md before implementation. Use when the user asks to write a PRD or spec, formalize requirements, design a multi-step flow, define observable behavior, or resolve product ambiguity for a non-trivial feature. Supports quick and deep discovery while deriving implementation guidance from repository evidence. Do not use for direct coding requests with settled requirements, small bug fixes, incident diagnosis, code explanation, or documentation that only describes existing code; use a build, diagnose, or documentation workflow instead.
---

# spec

Produce a standalone product contract with implementation guidance separated into a technical appendix. Ask the user about observable behavior and guarantees; derive implementation details from evidence in the current repository.

Do not write implementation code. Do not require a particular agent platform, subagent API, or repository stack.

## Operating contract

- Treat explicit user decisions as the authority for product behavior.
- Treat the repository as technical evidence and a default, not infallible truth. Record provenance, uncertainty, legacy signals, and conflicts.
- Ask about observable consequences, never implementation preferences. Timing, retention, loss tolerance, auditability, downtime behavior, rollback experience, and external data handling are valid product questions.
- Keep the product contract above one `## Technical appendix`; keep derived implementation guidance below it.
- Put private working notes under `.planning/` by default. Publish only `SPEC.md` unless the user explicitly requests the scratch trail.
- Use verification labels honestly: `syntax-validated` only after the bundled structural validator passes, and `human-reviewed` only after the user accepts the contract. Neither label implies semantic correctness or implementation feasibility.

## Choose a mode

Use `quick` unless the user requests depth or the feature has high product or operational blast radius.

| Mode | Use for | Evidence budget | Interview budget |
|---|---|---|---|
| `quick` | Bounded, reversible features with a known surface | Rules and manifests, one analogous path, nearest tests or contract | 3-6 questions, at most 2 rounds |
| `deep` | Payments, identity, permissions, public contracts, migrations, multi-party state, irreversible actions, or an explicit deep request | Rules, 2-3 analogous paths, affected producers and consumers, tests, contracts, migration policy | 8-18 questions, at most 5 rounds |

At the budget limit, preserve unresolved matters under `Open questions`; do not silently invent answers or continue interviewing indefinitely.

## Paths

Choose a stable slug before writing:

- Final spec: `--out <dir>/SPEC.md`, otherwise `specs/<slug>/SPEC.md`.
- Scratch: `--scratch <dir>`, otherwise `.planning/spec/<slug>/`.
- Original intent: `<scratch>/_intent.md`.
- Run manifest: `<scratch>/_run.json`.
- Context evidence: `<scratch>/_context.md`.
- Interview notes: `<scratch>/_interview.md`.

Treat scratch files as local working state. If `.planning/` is tracked, warn the user and leave it unstaged unless they explicitly ask to publish it.

Never silently reuse a non-empty scratch directory. Resolve `<skill-dir>` as
the directory containing this `SKILL.md`, and resolve one available Python 3
launcher in the same way as the validation step below.

For a new run:

1. Require an absent or empty scratch directory.
2. Save the user's original request exactly, without summarizing or rewriting
   it, to `<scratch>/_intent.md`.
3. Initialize the versioned manifest with the bundled validator:

   ```text
   <python-launcher> "<skill-dir>/scripts/validate_run.py" "<scratch>/_run.json" --initialize --slug "<slug>" --mode "<mode>" --intent-file "<scratch>/_intent.md" --source-root "<repository-root>" --exclude "<final-SPEC-path>"
   ```

   The validator also excludes the scratch directory itself. The resulting
   `spec-run/v1` manifest binds the exact normalized intent, source remote and
   commit when Git is available, and a deterministic fingerprint of tracked
   plus untracked non-ignored source files.

For a non-empty scratch directory:

1. Ask the user to choose `resume`, `restart`, or `new path` before consuming
   any scratch content.
2. Permit `resume` only after this command succeeds:

   ```text
   <python-launcher> "<skill-dir>/scripts/validate_run.py" "<scratch>/_run.json" --intent-file "<scratch>/_intent.md" --source-root "<repository-root>"
   ```

3. Treat any schema or analysis-version mismatch, changed intent, source-tree
   drift, malformed manifest, or missing file as a fail-closed resume failure.
   Preserve the existing scratch state and offer a confirmed restart or a new
   path; do not edit the old manifest to make it match.
4. If Python 3 is unavailable, deterministic resume validation is unavailable.
   Preserve the scratch directory and use a new path, or restart only after
   explicit user confirmation.
5. `restart` may replace scratch contents only after explicit user confirmation.
   Never delete or overwrite non-empty scratch state merely because the caller
   selected the same slug.

The run validator checks identity and structure only. It does not validate the
scratch notes or the semantic quality of the resulting specification. Its data
contract is documented by `schemas/run-v1.schema.json`.

## Portable orchestration

The files under `agents/` are capability prompts, not mandatory platform agents:

1. `agents/codebase-context-agent.md` gathers repository evidence.
2. `agents/product-interviewer-agent.md` proposes the next questions and tracks coverage.
3. `agents/spec-writer-agent.md` assembles `SPEC.md` without inventing behavior.

If isolated workers are available, delegate these capabilities. Run the context scan concurrently with the first interview round when useful. If workers or concurrency are unavailable, follow the same prompts sequentially in the current session. Missing orchestration features must not block the skill.

Keep all user-facing questions and approvals in the main conversation.

## Workflow

### 1. Capture intent

From the request, identify:

- working feature name and slug;
- intended actors and outcome;
- why the change is needed now;
- selected mode, final path, and scratch path.

Ask one open product question only when the request does not establish these basics. Announce the selected mode and final path.

Apply the scratch policy before starting context gathering or interview notes. A stale directory is a decision point, not an implicit resume signal.

### 2. Gather repository evidence

Apply `agents/codebase-context-agent.md`. Read repository instructions first, then the smallest evidence set allowed by the selected mode.

For every derived technical claim, record a source and one status:

- `documented` - an active repository policy or approved contract states it;
- `observed` - current code or configuration demonstrates it;
- `tested` - an executable test enforces it;
- `assumption` - plausible but not established;
- `conflict` - credible sources disagree;
- `unknown` - the repository does not answer it.

Look for legacy signals before treating current code as a default: deprecation notices, migration plans, compatibility shims, dead or unreferenced paths, TODOs with an owner, and newer competing patterns.

When sources conflict:

1. Ask the user only if the conflict changes observable product behavior or a product guarantee.
2. Otherwise preserve the conflict in the technical appendix with the evidence on both sides.
3. Never turn an isolated implementation detail into a product requirement.

### 3. Interview for observable behavior

Apply `agents/product-interviewer-agent.md` with the mode, remaining question budget, context, intent, and prior answers.

Ask short questions in the user's vocabulary. Cover only gaps that materially affect the contract:

- actors, permissions, and ownership;
- golden path and meaningful states;
- conflicts, partial failure, abandonment, and recovery;
- always-true invariants;
- observable timing and visibility;
- retention, deletion, audit, and loss expectations;
- downtime and rollback experience;
- external processing or data-sharing policy;
- measurable acceptance and success criteria.

Do not ask which database, queue, cache, schema, HTTP method, library, file, or deployment mechanism to use. When an implementation choice has a user-visible consequence, ask for that consequence instead.

Append answers to `<scratch>/_interview.md`. If the budget expires with gaps, record them explicitly and continue to the draft.

### 4. Check convergence

For `quick`, require:

- actors and golden path;
- the primary failure or conflict behavior;
- key invariants;
- acceptance or success criteria;
- no unresolved issue that would reverse the core product behavior.

For `deep`, additionally require:

- meaningful lifecycle states and transitions;
- edge, concurrency, abuse, and partial-failure behavior where applicable;
- operational guarantees relevant to the feature;
- all affected surfaces and external actors;
- explicit treatment of any unresolved conflict.

Convergence means the selected coverage is addressed, not that every imaginable question was asked. Anything unresolved belongs in `Open questions`.

### 5. Assemble the spec

Apply `agents/spec-writer-agent.md` to the original intent, `_interview.md`, and `_context.md`. Write only the final `SPEC.md` to the public output directory.

Use this exact H2 order:

```markdown
## Purpose
## Glossary
## Actors
## User-facing behavior
## Flows
## States and transitions
## Invariants
## Edge cases
## Success criteria
## Out of scope
## Open questions

---

## Technical appendix
```

The appendix must identify evidence status and include:

- stack and placement;
- data and contract impacts;
- migration and rollback policy actually found in the repository;
- integration points;
- conflicts, assumptions, risks, and follow-ups.

Do not mandate up and down migrations. Follow the repository's documented migration and rollback policy. If none is established, say so and surface the risk.

### 6. Validate honestly

Resolve `<skill-dir>` as the directory containing the loaded `SKILL.md`; do not resolve scripts from the caller's working directory. Run `<skill-dir>/scripts/validate_spec.py` with an available Python 3 launcher:

```text
python3 "<skill-dir>/scripts/validate_spec.py" "<path-to-SPEC.md>"
python "<skill-dir>/scripts/validate_spec.py" "<path-to-SPEC.md>"
py -3 "<skill-dir>/scripts/validate_spec.py" "<path-to-SPEC.md>"
```

Use the first launcher that is actually available; do not run all three. If Python 3 is unavailable, perform the manual checklist below, say that automated structural validation was unavailable, and do not use the `syntax-validated` label.

The validator checks supported frontmatter syntax, required heading order, the product/technical boundary, and required appendix sections. It does **not** prove that behavior is correct, evidence is current, questions are complete, or the implementation guidance is feasible.

Then review manually:

- frontmatter contains only non-empty `title`, `domain`, and `last_updated`; quote free-form text and use a real `YYYY-MM-DD` calendar date;
- the single H1 exactly matches the decoded frontmatter title;
- every required H2 and technical-appendix H3 appears exactly once in the documented order;
- the appendix boundary and warning blockquote are present;
- every product behavior traces to the user's intent or interview;
- every technical claim has provenance and status;
- conflicts and unknowns are visible;
- no implementation language leaked into the product half;
- no product decision was invented in the appendix.

Report the artifact as `syntax-validated` only if the validator ran successfully. Call it `human-reviewed` only after the user explicitly accepts it.

### 7. Review with the user

Present the path and a compact list of open questions, conflicts, and assumptions. Ask whether the contract is accurate. If behavior changes, update the interview notes and regenerate the affected sections; do not patch technical guidance into the product half.

## Output structure

```markdown
---
title: '<Feature name>'
domain: '<product area or unknown>'
last_updated: <YYYY-MM-DD>
---

# <Feature name>

## Purpose
Who this is for, what it enables, and why now.

## Glossary
Product terms and definitions.

## Actors
Every human, machine, or external actor and its role.

## User-facing behavior
The end-to-end product story, split by surface when useful.

## Flows
Golden path followed by resolved alternate flows.

## States and transitions
Meaningful product states and visible transitions.

## Invariants
Always-true product rules.

## Edge cases
Resolved deviations and failure behavior.

## Success criteria
Measurable product or acceptance signals.

## Out of scope
Explicit exclusions and reasons.

## Open questions
Unresolved product matters. Use `(none)` when empty.

---

## Technical appendix
> Derived from repository evidence; this section is implementation guidance, not the product contract.

### Evidence and conflicts
Claim, source, status, and any competing evidence.

### Stack & placement
Observed locations and reusable patterns.

### Data model and contracts
Expected impacts without inventing unsupported details.

### Migration & rollback
The repository policy, or an explicit statement that none was found.

### Integration points
Affected producers, consumers, services, and generation steps.

### Risks & follow-ups
Assumptions, unknowns, feasibility risks, and required verification.
```

## Supported arguments

- `<idea>` - optional feature intent.
- `--mode quick|deep` - override mode selection.
- `--out <dir>` - public output directory.
- `--scratch <dir>` - private working directory.

## Never

- Write implementation code or publish changes.
- Ask the user to choose implementation technology.
- Treat one existing code path as a binding product decision.
- Hide evidence conflicts or label assumptions as repository facts.
- Commit `_context.md` or `_interview.md` by default.
- Reuse or overwrite non-empty scratch state without an explicit resume, restart, or new-path decision.
- Claim semantic correctness from structural validation.
