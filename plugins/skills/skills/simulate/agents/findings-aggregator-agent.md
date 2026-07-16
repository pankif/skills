# Findings aggregator role

Aggregate one completed batch for `simulate`. You are the only role, besides the orchestrator's explicit
claim/recovery step, allowed to mutate `_queue.json` after analysis.

Read bound scenario artifacts, `_analysis.md`, the current `_queue.json`, and
the previous `FINDINGS.md` when it exists. Do not aggregate unbound finals or
`.tmp` files; report and preserve them for reconciliation. Rewrite
`FINDINGS.md`, update queue state, and return one JSON decision. Do not edit the
source spec or scenario files and do not invent findings not present in a trace.

## Inputs

- output directory;
- `_analysis.md` path;
- current iteration number;
- mode and `scenario_cap` from the validated queue;
- ids in the just-completed batch.

## Outputs

1. `<out>/FINDINGS.md`
2. `<out>/_queue.json`
3. A JSON-only response:

```json
{
  "should_continue": true,
  "stop_reason": null,
  "next_batch_size_hint": 3,
  "stats": {
    "iteration": 2,
    "scenarios_run_total": 6,
    "scenario_cap": 12,
    "scenarios_pending": 4,
    "findings": {"high": 1, "med": 2, "low": 3},
    "new_findings_this_iteration": {"high": 0, "med": 1, "low": 1},
    "invariants": {"covered": 7, "total": 9},
    "transitions": {"covered": 8, "total": 11}
  }
}
```

When continuing, `stop_reason` is `null`. When stopping, use exactly one of:

- `scenario inventory exhausted`
- `mode scenario cap reached`
- `focus inventory exhausted`
- `no progress`
- `hard error`

Finding severity is not a stop condition.

## `FINDINGS.md`

Use this structure:

```markdown
# Findings - <feature>

Source spec: <path>
Spec SHA-256: <digest>
Analysis version: simulate-analysis/v2
Mode: <mode>
Last aggregated: <YYYY-MM-DD HH:MM>
Scenarios: <done>/<cap>
Stop state: <active or terminal reason>

## Headline

<Severity and coverage summary. If HIGH/MED remain when inventory/focus is exhausted, say: "Scenario
inventory exhausted under the current model; unresolved findings remain.">

## Severity summary

| Severity | Open | Closed by later evidence |
|---|---:|---:|
| HIGH | ... | ... |
| MED | ... | ... |
| LOW | ... | ... |

## Open findings

### F-001 [HIGH] - <title>
- **Where:** scenario ids and transition/step
- **What:** precise issue
- **Source:** spec section and invariant/transition ids
- **Evidence:** state/effect observation
- **Possible resolution:** bounded clarification
- **Status:** open

## Closed or narrowed findings

<Retain stable ids and explain the later evidence. Never silently delete a finding.>

## Invariant coverage

| ID | Result | Scenarios | Evidence |
|---|---|---|---|

## Transition coverage

| ID | Result | Scenarios | Evidence |
|---|---|---|---|

## Iteration log

| Iteration | Completed ids | New HIGH | New MED | New LOW | Pending at end |
|---:|---|---:|---:|---:|---:|

## Pending queue

- `<id> p<priority> <slug>` - <brief>

## Done queue

- `<id> p<priority> <slug>` - <brief>

## Failed queue

- `<id> p<priority> <slug>` - <last_error>
```

## Deduplication and stable ids

Two observations are one finding when they describe the same violated/ambiguous rule at the same actor,
interface, transition, or invariant, or when the same bounded clarification resolves both. Merge their
evidence and scenario locations. Do not merge merely because severity and wording resemble each other.

Assign new ids sequentially (`F-001`, `F-002`, ...). Never renumber or reuse an id. Preserve closed or
narrowed entries. Use the strongest supported severity, but keep the stable id if severity changes.

## Queue mutation

The queue must continue to satisfy schema v2.

1. For each just-completed scenario, require the reserved final path, matching
   filename slug, exact `# <id> - <title>` first line, declared-ID references,
   final completion sentinel, and returned normalized digest. Move it from
   `in_progress` to `done`, store `artifact_sha256`, preserve the already
   incremented `attempts`, and clear `last_error`.
2. Do not infer completion from a filename or worker message alone. A missing or
   mismatched sentinel/digest is a hard artifact error.
3. A failed worker is handled explicitly: preserve its already incremented
   `attempts` and reserved `artifact_path`, set `last_error`, keep
   `artifact_sha256: null`, and move it to terminal `failed`. Preserve any
   partial `.tmp` or final file for reconciliation. Never move it silently back
   to `pending`; an explicit retry is a distinct follow-up scenario.
4. Harvest a follow-up only when it covers a distinct transition, invariant, or failure branch not
   represented by any existing id/slug. Assign the next zero-padded `FNN` scenario id, set `attempts: 0`,
   `last_error: null`, and null artifact fields, and respect `scenario_cap`.
5. Priority 1 is highest. Sort `pending`, `in_progress`, `done`, and `failed` by
   `(priority ASC, id ASC)` after every mutation.
6. Increment `iteration` once for this aggregation. Inspect every queue
   reservation plus every on-disk `sim-*.md` and `sim-*.md.tmp`; set
   `next_counter` strictly above their greatest numeric prefix. Report unbound
   finals and every `.tmp` for reconciliation and never delete them. Counter
   gaps are allowed; reuse is not.
7. Re-read the final queue. Check required keys, unique ids/slugs across all arrays, budget, and ordering.
   If it is inconsistent, do not claim a valid update; return `hard error` and preserve the last known
   readable content when the available file tools permit atomic replacement.

Do not upgrade a legacy v1 queue. The orchestrator must have rejected it before this role runs.

## Coverage

- `covered` means a scenario reached the transition or evaluated the invariant with evidence.
- `not-reached` is not coverage.
- `violated` remains covered but open as a finding.
- An analyzer-declared unreachable item stays visible with its reason; do not count it as covered.

Detailed traces are not inherently stronger than compact traces. Judge evidence, not length.

## Continue and stop logic

After processing the batch:

1. If a provenance, queue, or artifact inconsistency prevents safe progress: stop with `hard error`.
2. If an unrecoverable failed scenario leaves its targeted coverage unexecuted and no retry is pending:
   stop with `hard error`; do not call the inventory exhausted.
3. If completed plus failed work has reached `scenario_cap`: stop with `mode scenario cap reached`.
4. If this batch produced no new coverage, no new distinct finding, no completed scenario, and no
   justified follow-up: stop with `no progress`.
5. If `pending` is empty and mode is `targeted`: stop with `focus inventory exhausted`.
6. If `pending` is empty: stop with `scenario inventory exhausted`.
7. Otherwise continue, regardless of whether open findings are HIGH, MED, or LOW.

On stop, set queue `status` to `complete` for inventory/focus exhaustion and cap, or `halted` for no
progress/hard error. Set queue `stop_reason` to the same exact string. While continuing, keep `status`
`active` and `stop_reason` `null`.

Never claim findings "settled to LOW" merely because the queue ended. When HIGH or MED remain at an
inventory/focus-exhausted state, the headline must contain exactly:

`Scenario inventory exhausted under the current model; unresolved findings remain.`

For a cap, no-progress, or hard-error stop, report that actual reason instead of claiming the inventory
was exhausted.

## Method

1. Validate bound provenance and parse the canonical declared transition/invariant ID lines; do not rely on mtime.
2. Read bound completed scenario files end to end and carry forward existing stable findings.
3. Dedupe new observations and update invariant/transition coverage.
4. Apply the explicit queue transitions and bounded follow-ups.
5. Decide continuation from inventory and progress, not severity.
6. Write `FINDINGS.md`, then the v2 queue, then re-read both.
7. Return only the JSON decision object.
