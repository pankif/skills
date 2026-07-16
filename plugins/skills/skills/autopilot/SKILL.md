---
name: autopilot
description: >-
  Drive a substantial software feature or project from a prompt or existing spec through local implementation and evidence-backed verification. Use when the user asks to build, implement, finish, or ship an entire multi-file feature autonomously, says autopilot/one-shot/end-to-end, or wants coordinated work across components. Includes a premise check, proportional planning, bounded convergence, capability fallbacks, honest verification states, and explicit outward-action authority. Do not use for a one-line edit, a review-only request, pure diagnosis, or a request whose main output is a product spec; use the ordinary edit flow, diagnose, or spec instead. The default is local `build --standard`; strict machinery is reserved for public contracts, persistent formats, security boundaries, destructive changes, and remote or real-world effects.
---

# Autopilot

Deliver substantial work autonomously without turning procedural ceremony into a
substitute for correctness. Optimize for a useful verified result, not code
volume or the appearance of rigor.

## Invocation

Interpret explicit forms as:

```text
autopilot [plan|build|ship] [--quick|--standard|--strict] <request-or-spec>
```

- Mode defaults to `build`.
- Depth defaults to `--standard`.
- Preserve explicit user choices unless safety or missing capabilities force a
  stronger gate or a weaker verification claim.

### Modes

- `plan`: inspect, challenge the premise, identify affected boundaries, and
  produce a reviewable plan. Do not implement behavior or perform outward
  actions.
- `build`: make in-scope local changes and verify them. It is unconditionally
  local and never commits, pushes, opens a PR, or performs another outward
  action. If the current request explicitly names a repository delivery action
  and target, route that final boundary through `ship` instead.
- `ship`: run the build workflow and then perform only repository delivery
  actions (`commit`, `branch`, `push`, `pull-request`) explicitly named with a
  target in the current request. The word `ship` is not authority by itself.
  Merge, publish, deploy, apply, send, and production mutation remain handoff
  boundaries even when requested; this skill does not execute them.

### Depth

- `--quick`: bounded, low-blast, well-understood work. Inline decisions; use the
  smallest relevant checks and no run artifacts unless resume is needed.
- `--standard`: normal multi-file feature. Keep a concise decision ledger,
  implement vertical slices, and run relevant tests plus repository checks.
- `--strict`: public contracts, persistent formats or migrations, trust and
  security boundaries, destructive operations, external effects, or explicitly
  requested proof. Use the versioned BUS protocol in `references/bus.md`.

Escalate from quick/standard to strict when evidence reveals high blast radius.
State the escalation; do not silently add a large apparatus.

## Runtime capability probe

Before planning, identify whether the runtime can:

1. read/search the target;
2. run commands and capture actual output;
3. persist local artifacts;
4. create isolated or parallel workers;
5. pause for a human decision;
6. perform a specifically authorized outward action.

Use capabilities, not platform tool names. If isolated/parallel workers are
missing, run roles sequentially in the current agent and disclose the loss of
independence. If execution is missing, do not describe commands as run. If local
persistence is missing, return resumable state inline. If a required outward or
human-gate capability is missing, stop at that boundary. See
`../../../../docs/runtime-compatibility.md` when working from this repository;
installed copies may instead use the equivalent contract summarized here.

## Workflow

### 0. Check the premise

Use cheap target-local evidence to try to disprove three assumptions:

- the requested behavior is not already present;
- the request does not contradict the current contract or itself;
- important stated facts about the target are true.

If the request is already satisfied, show the evidence and avoid a redundant
change. If the corrected intent is obvious and safe, state the correction and
continue with it. Ask one focused question only when correction requires a
material product choice, an irreversible action, or unavailable authority.

### 1. Bound scope, authority, and risk

Identify affected repositories, components, contracts, persistence, trust
boundaries, tests, and external systems. Separate:

- facts confirmed by current code/config/tests or explicit user statements;
- derived conclusions with cited evidence;
- defaults chosen for reversible local details;
- open decisions that require the user.

Remote credentials, an existing branch, a mode name, or wording such as “ready
to ship” never expands authority. Record each authorized outward action and its
target separately.

For strict/high-blast work, create a version-2 BUS record. Resolve
`<skill-root>` as the directory containing this loaded `SKILL.md`, then use an
available Python 3 launcher (`python`, `python3`, or `py -3`):

```text
<python> "<skill-root>/scripts/validate_bus.py" path/to/BUS.json
```

If the runtime cannot expose the installed skill path or run Python, keep the
record unvalidated and report that `syntax-validated` was not reached.

Use `references/bus.md` for the schema and supported migration behavior. The
validator checks structure and integrity only; it cannot prove that an LLM's
classification is correct.

### 2. Choose the smallest useful plan

Produce an impact list and an executable order. Prefer vertical slices that can
be checked independently. Use a skeleton with explicit unfinished sentinels only
when multiple boundaries must be coordinated or interrupted work must remain
obviously incomplete.

For standard/strict work:

- name acceptance behavior before implementation;
- identify at least one negative or failure path;
- distinguish load/shape checks from behavior checks;
- identify any slice that requires human judgment or external realization.

In `plan` mode, stop here with `PLAN-READY`, open decisions, intended checks, and
the outward actions that remain unauthorized.

### 3. Implement proportionally

Follow repository-local instructions and preserve unrelated user changes.
Implement the smallest coherent vertical slice first, then extend. Parallelize
only genuinely independent work whose writes will not conflict; otherwise work
sequentially.

When an implementation exposes a wrong premise or missing material decision,
update the plan and decision ledger. Do not force code to fit an obsolete plan.

### 4. Build an evidence ladder

Track each important artifact or behavior on this ladder:

```text
designed -> generated -> syntax-validated -> executed -> behavior-verified -> human-reviewed
```

Advance only with evidence:

- compile, parse, schema, lint, and marker checks establish syntax/structure;
- an actual run establishes execution;
- an independent expected result, trusted fixture, real contract test, or
  equivalent non-self-referential oracle establishes behavior;
- explicit human feedback establishes human review.

Round-trip, idempotency, conservation, snapshot self-consistency, or tests
authored solely from the same interpretation can be useful but do not by
themselves prove the intended semantics. Label the highest supported state.

Run the narrowest relevant checks first, then the repository's required formatter,
lint, unit, integration, build, or E2E checks in proportion to risk. Capture the
actual command and result; never report an unexecuted command as passing.

### 5. Converge within a bound

On a failed check:

1. preserve the failure output;
2. identify the owning slice and current hypothesis;
3. make the smallest evidence-driven correction;
4. rerun the failed check, then any affected broader check.

Cap repeated attempts. If evidence stops narrowing the issue, stop with a mapped
blocker instead of cycling. Do not automatically repeat state-consuming or
irreversible checks; run them once unless an idempotent, explicitly authorized
procedure is proven.

For visual, prose-quality, UX, policy, or other human-judgment slices, provide
the review artifact and one falsifiable question per material slice. A missing
human verdict yields `UNVERIFIED`, not `GREEN`.

### 6. Finish cleanly

Before claiming completion, search the changed scope for the sentinel patterns
used by this run. The optional helper reports only marker presence:

```text
<python> "<skill-root>/scripts/check_unfinished.py" <changed-path> [<changed-path> ...]
```

A clean marker scan does not prove implementation completeness.

Finish with one terminal:

- `GREEN`: requested local result is complete and relevant behavior checks pass;
- `UNVERIFIED`: work is present, but a named slice lacks a runnable independent
  oracle or human verdict;
- `ESCALATE`: a material decision, authority boundary, non-repeatable failure,
  or convergence cap requires the user;
- `ABORTED-with-map`: incomplete work remains; list every known unfinished
  boundary, preserved artifact, and safe resume or rollback step.

Report, in this order:

1. outcome and terminal;
2. changed components;
3. checks actually run and their results;
4. highest verification state per material slice and what remains unverified;
5. material defaults/open decisions;
6. outward actions performed, each tied to current explicit authority.

## Resume and legacy artifacts

Resume only from artifacts whose `schema_version` and `analysis_version` are
supported and whose validator passes. Preserve unsupported artifacts unchanged
and return `ESCALATE` with a migration or clean-restart option. Never infer old
semantics from filenames or modification times, and never silently overwrite a
legacy run.

## References

- `references/bus.md`: strict-mode decision record and validation limits.
- `references/pillars.md`: proportional fallbacks for unusual substrates.
