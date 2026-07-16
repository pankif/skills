---
name: simulate
description: >-
  Stress-test a spec, RFC, PRD, or design before implementation by executing a bounded inventory of
  stateful, concurrent, failure, and adversarial scenarios. Use when the user asks to simulate or
  challenge a design, walk through system states, find missing transitions, or test invariants in
  auth, money, persistence, queues, caches, or external integrations. Supports targeted, standard,
  deep, and attacks-only modes. Do not use to diagnose an implemented bug, write or rewrite the spec,
  implement code, perform a generic code review, or analyze a trivial stateless document. It produces
  evidence-oriented findings, not proof that the design is correct.
---

# Simulate

Stress-test a design before implementation. Build one shared state-transition model, execute a bounded
scenario inventory against it, and produce deduplicated findings without changing the source spec or
writing implementation code.

The simulation is a review model, not a runtime proof. A clean run means only that the documented
inventory found no further issues under its stated assumptions.

## Modes and budgets

Choose the smallest mode that fits the request. `standard` is the default.

| Mode | Use when | Total scenario budget |
|---|---|---:|
| `targeted` | The user names a flow, invariant, transition, or risk to examine | 4-8 |
| `standard` | General pre-implementation review | 8-12 |
| `deep` | A complex stateful or high-consequence design needs broader coverage | 12-20, hard max 20 |
| `attacks-only` | The user wants only failure, abuse, race, and adversarial paths | 6-12 |

At least 30% of `standard` and `deep` scenarios must be edge, failure, race, or attack scenarios.
`targeted` requires `--focus=<phrase>`. `attacks-only` queues no golden-path scenarios. Do not expand a
budget just to make open findings disappear.

## Arguments

- `<spec-path>` - target spec; required unless a single source is unambiguous from context.
- `--mode=targeted|standard|deep|attacks-only` - default `standard`.
- `--focus=<phrase>` - required for `targeted`, optional otherwise.
- `--out <dir>` - default `<spec-dir>/<spec-stem>.sim/`.
- `--parallel=K` - maximum concurrent scenario workers, default 3, max 6.
- `--attacks-only` - compatibility alias for `--mode=attacks-only`.

Reject the old `--depth` argument with a short migration hint instead of silently changing its meaning:
use `--mode=standard` or `--mode=deep`.

## Artifacts

All generated files live in one output directory:

```text
<spec>.sim/
|- _analysis.md
|- _queue.json
|- sim-001-<slug>.md
|- sim-002-<slug>.md
`- FINDINGS.md
```

The spec is read-only. `_analysis.md` owns the shared state-transition matrix; scenario files reference
its transition ids rather than rebuilding independent models. `_queue.json` follows
[`schemas/queue-v2.schema.json`](schemas/queue-v2.schema.json).

## Roles

Load the role prompt before performing that role. If subagents are unavailable, the orchestrator adopts
the same roles sequentially; role boundaries and artifacts do not change.

| Role | Prompt | Responsibility |
|---|---|---|
| Analyzer | [`agents/spec-analyzer-agent.md`](agents/spec-analyzer-agent.md) | Extract the model, transition matrix, invariants, and bounded queue |
| Simulator | [`agents/scenario-simulator-agent.md`](agents/scenario-simulator-agent.md) | Execute exactly one queued scenario |
| Aggregator | [`agents/findings-aggregator-agent.md`](agents/findings-aggregator-agent.md) | Dedupe findings, update coverage and queue, decide continuation |

## Workflow

### 0. Resolve input and capabilities

Resolve an explicit path, an `@path` reference, or an inline spec. Ask for a path only when more than
one source remains plausible. For inline text, ask before persisting it unless the user already requested
artifacts.

Discover capabilities rather than assuming a platform:

1. A SHA-256 facility that can apply the text normalization below; prefer the bundled checker.
2. Python 3 for the bundled queue checker, if available.
3. Concurrent independent workers, sequential workers, or no subagent facility.

Parallel execution is an optimization, never a semantic requirement. If concurrent dispatch is
unavailable, execute the same batch sequentially in `(priority ASC, id ASC)` order. If subagents are
unavailable, adopt each role in that order. Never claim parallel execution when it was sequential.

### 1. Establish provenance or resume

Compute the source file's portable lowercase SHA-256: decode UTF-8, convert CRLF
and CR to LF, normalize Unicode to NFC, then hash the resulting UTF-8 bytes.
With the bundled checker:

```text
<python-launcher> "<skill-dir>/scripts/validate_queue.py" --print-spec-sha256 "<spec>"
```

The `_analysis.md` header uses:

```text
Analysis version: simulate-analysis/v2
Queue schema: 2
Spec SHA-256: <64 lowercase hex characters>
Mode: <targeted|standard|deep|attacks-only>
```

After `_analysis.md` is complete, compute its normalized digest with the same
UTF-8/line-ending/NFC rules and store that value only in the queue's
`analysis_sha256` field. Do not embed an analysis digest into `_analysis.md`;
that would be self-referential.

They also declare the only legal model references in two canonical lines:

```text
Declared transition IDs: T01, T02
Declared invariant IDs: I01, I02
```

Use exactly one line of each kind, comma-space separators, and numeric ascending
order. `Declared invariant IDs: none` is allowed; transitions cannot be `none`.
These bound lines, not ad-hoc Markdown table parsing, are the stable registry
used by `--resume`.

If no artifacts exist, continue to analysis. If any artifacts exist, inspect before writing:

- A v2 queue is resumable only when its `spec_sha256` equals the current spec digest,
  `analysis_sha256` equals the normalized digest of `_analysis.md`, and its
  `analysis_version` is exactly `simulate-analysis/v2`.
- Resolve `<skill-dir>` as the directory containing the loaded `SKILL.md`. Before
  resume, run the bundled checker with an available Python 3 launcher
  (`python3`, `python`, or `py -3`):
  `<python-launcher> "<skill-dir>/scripts/validate_queue.py" "<out>/_queue.json" --resume --spec "<spec>" --analysis "<out>/_analysis.md" --artifacts-dir "<out>"`.
- If Python or the installed skill path is unavailable, do not resume or claim
  `syntax-validated`; preserve the run and use a fresh `--out` or request a
  manual validation handoff.
- If validation fails, stop without mutating artifacts. State what failed and suggest a fresh `--out`.
- A legacy queue with `"version": 1` is recognizable but read-only. Never resume or overwrite it.
  `--allow-legacy-read` checks its limited shape; use a fresh output directory for v2.
- Missing provenance, digest mismatch, unsupported schema, or changed analysis version is fail-closed.
  Never infer compatibility from mtimes and never silently re-analyze over an existing run.

For a valid v2 resume, the checker parses the declared ID registry and rejects
every queue or completed-artifact reference not present there. It verifies each
`done` scenario's exact `# <id> - <title>` first line, filename slug, final
completion sentinel, and digest.

Before any new work, reconcile every reported artifact without deleting it:

- a valid final file bound to `in_progress` can be promoted to `done` after its
  digest is recorded;
- an incomplete/missing `in_progress` artifact becomes `failed` with its
  reservation preserved;
- every `.tmp` file and unbound `sim-*.md` final is reported and preserved for
  explicit reconciliation; never auto-bind it by filename similarity;
- a final file without the exact header/sentinel is a hard artifact error.

After reconciliation, rerun `--resume`. Never rerun or overwrite a verified
`done` artifact.

`next_counter` is monotonic reservation state. It must be strictly greater than
every numeric prefix in `in_progress`, `done`, or `failed` reservations and
every on-disk final or `.tmp` scenario file. Gaps are valid; reuse is not.

The checker proves only mechanical properties: JSON shape, supported versions,
queue ordering/uniqueness, bound declared-ID references, counter monotonicity,
and optional digest/header/sentinel/artifact inventory agreement. It does not
prove scenario quality, semantic correctness, or that a finding is true.

Queue state contract:

| Bucket | Attempts | Error | Artifact reservation | Digest |
|---|---:|---|---|---|
| `pending` | exactly 0 | null | null | null |
| `in_progress` | at least 1 | null | required | null |
| `done` | at least 1 | null | required | required |
| `failed` | at least 1 | required | preserved | null |

`failed` is terminal within the run. A retry is a new explicitly queued
scenario, not a silent move back to `pending` that erases attempt history.

### 2. Analyze once

Run the analyzer synchronously. It writes `_analysis.md` and `_queue.json` with:

- actors, interfaces, persistent state, external effects, and assumptions;
- numbered invariants;
- one shared state-transition matrix;
- a mode-bounded scenario inventory;
- priority `1` as highest, with every queue sorted by `priority ASC, id ASC`.

Use zero-padded ids (`G01`, `E01`, `A01`, `F01`) so id ordering is stable. Validate the generated queue
before simulation when the checker is available. On failure, return it to the analyzer once; if it still
fails, stop honestly.

### 3. Execute bounded batches

Repeat while pending scenarios remain and the mode budget is not exhausted:

1. Select the next batch from `pending` in `(priority ASC, id ASC)` order.
2. Increment each selected entry's `attempts`, move it to `in_progress`, reserve a unique safe
   `sim-NNN-<slug>.md` in `artifact_path` with `artifact_sha256: null`, and
   persist a `next_counter` strictly above every reserved/on-disk prefix before dispatch; do not let two workers
   own the same id or path.
3. Run one simulator per scenario concurrently when supported, otherwise sequentially.
4. Wait for the entire batch, then run the aggregator once.
5. The aggregator moves completed entries to `done`, deduplicates findings, updates invariant and
   transition coverage, and may add a genuinely distinct follow-up within the original mode budget.
6. Validate `_queue.json` after each mutation when the checker is available.

Only the orchestrator or aggregator mutates `_queue.json`; scenario workers never
do. A failed attempt moves to `failed`, keeps its reservation, and records the
error. It never silently returns to `pending`.

### 4. Trace at the right fidelity

Symbolic values are the default: `USER_A`, `ORDER_1`, `REQ_1`, `T0`. Use concrete timestamps, money,
sizes, ids, encodings, or signatures only when the value itself participates in a boundary or invariant.
Do not manufacture realistic-looking schema details that the spec did not provide.

Compact traces reference transition ids and show only relevant preconditions, state/effect diffs, and
invariant results. A detailed actor-by-actor trace is required only when at least one is true:

- the scenario is priority 1 or otherwise explicitly high-risk;
- an invariant is violated;
- the run reaches a contradiction or materially ambiguous transition.

### 5. Stop honestly

Stop on the first applicable terminal condition:

- `scenario inventory exhausted` - no pending or justified follow-up scenarios remain;
- `mode scenario cap reached` - the bounded budget is exhausted;
- `focus inventory exhausted` - targeted scope is covered;
- `no progress` - a batch neither shrank actionable queue state nor added coverage;
- `hard error` - provenance, validation, or execution cannot safely continue.

HIGH and MED findings do **not** force another loop and do not prevent an inventory-exhausted terminal.
Never say findings "settled to LOW" unless that is literally true. The honest completion statement is:

> Scenario inventory exhausted under the current model; unresolved findings remain.

Use it when the inventory/focus is exhausted and HIGH or MED findings remain. For a cap, no-progress,
or hard-error stop, state that actual reason instead.

## Final report

Return only a compact summary; keep detail in `FINDINGS.md`:

```text
Simulation complete: <mode>, <M>/<cap> scenarios.
Execution: <parallel|sequential>; queue: <schema-validated|manually-shape-checked>.
Severity: HIGH <h> | MED <m> | LOW <l>.
Coverage: invariants <x>/<y>; transitions <a>/<b>.
Stop reason: <reason>.
Artifacts: <out>/

Top open findings:
- [HIGH] <summary> - <scenario ids>
```

If unresolved HIGH/MED findings remain, include the honest completion statement above. Do not paste the
entire findings file and do not edit the spec in response to findings.

## Non-negotiable boundaries

- Read the spec; never edit it.
- Produce review artifacts; never implementation code.
- Flag missing behavior and state the temporary simulation assumption; never promote it to spec truth.
- Preserve existing artifacts on incompatibility; never silently overwrite, upgrade, or renumber them.
- Treat generated, shape-validated, simulated, and semantically verified as different states.
