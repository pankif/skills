# Scenario simulator role

Execute exactly one claimed scenario against the shared model produced by
`simulate`. Its queue state must be `in_progress`, with `attempts >= 1` and a
reserved `sim-NNN-<slug>.md` whose suffix exactly matches the scenario slug.
Write only that final file and its `.tmp` staging path. Do not mutate
`_queue.json`, `FINDINGS.md`, the source spec, or another scenario file. Do not
choose work or resolve product gaps.

The assigned path must equal the queue's reserved `artifact_path`. Write the
complete body to `<assigned-path>.tmp`, put the completion sentinel shown below
as the final non-empty line, then atomically replace the final path on the same
filesystem. Never publish a partial final file.

The first physical line of the final file is exactly `# <id> - <title>` with
the queue's id and title: no preamble, BOM, alternate dash, or extra spacing.
Use only transition and invariant IDs from the canonical `Declared ... IDs`
lines in the bound `_analysis.md`. If the queued scenario references an
undeclared id, do not write; return the contract error to the orchestrator.

## Inputs

- source spec path, read-only;
- `_analysis.md`, read-only and authoritative for transition and invariant ids;
- one v2 scenario object from `_queue.json`;
- assigned output file path.

Read `_analysis.md` first. Consult the source spec only to verify a citation or ambiguity; do not build a
second independent model.

## Fidelity decision

Start with a compact trace. Upgrade the file to a detailed trace when any of these is true:

- the scenario is priority 1 or otherwise explicitly high-risk;
- an invariant is violated;
- a required transition is contradictory or materially ambiguous.

Record `Trace level: compact` or `Trace level: detailed` in the header. Do not produce a detailed trace
merely because the scenario is long.

Use symbolic values by default: `USER_A`, `ORDER_1`, `REQ_1`, `T0`, `TOKEN_A`. Use a concrete value only
when it is the subject of the test, such as a money rounding boundary, maximum size, expiry instant,
encoding, or signature comparison. Never invent realistic-looking fields or values the spec does not
define.

## Output structure

~~~markdown
# <scenario id> - <title>

Category: <golden|edge|attack>
Priority: <1|2|3; 1 is highest>
Trace level: <compact|detailed>
Source spec: <path>
Transitions targeted: [T01, ...]
Invariants targeted: [I01, ...]
Actors: <names>

## Intent

<What this scenario challenges and its expected outcome if the spec is coherent.>

## Preconditions

- <symbolic state required before the first transition>

## Transition walk

| Step | Actor | Transition | Input/condition | State or effect diff | Result |
|---:|---|---|---|---|---|
| 1 | CLIENT | T01 | REQ_1 | no write | accepted |
| 2 | STORE | T02 | ORDER_1 absent | `+ ORDER_1.status = pending` | held |

## Detailed trace

<Required only at detailed fidelity. Otherwise write: Not required at compact fidelity.>

## Invariant checks

| Invariant | Result | Evidence |
|---|---|---|
| I01 | held/violated/not-reached | <transition and state/effect evidence> |

## Outcome

<Final symbolic state, externally visible result, and surviving side effects.>

## Findings

### [HIGH] S-<scenario-id>-01 - <title>
- **Where:** transition/step
- **What:** precise contradiction, invariant violation, or unsafe missing rule
- **Source:** spec section and/or invariant id
- **Evidence:** observed state/effect difference
- **Possible resolution:** one bounded clarification; do not rewrite the spec

### [MED] ...

### [LOW] ...

Write `(none)` under each severity with no findings.

## Spec gaps and assumptions

- [gap] <missing rule and where it was encountered>
- [assumption] <temporary branch used only to finish this simulation>

## Follow-up candidates

```json
[]
```

<!-- simulate-complete:<scenario-id> -->
~~~

Follow-up candidates omit global `id`; the aggregator assigns the next `FNN` id. A non-empty candidate
uses this shape:

```json
{
  "slug": "distinct-uncovered-transition",
  "category": "edge",
  "title": "Distinct uncovered transition",
  "brief": "Why this is not already represented in the bounded inventory.",
  "priority": 2,
  "actors_involved": ["SERVICE", "STORE"],
  "transitions_targeted": ["T04"],
  "invariants_targeted": ["I03"]
}
```

Priority 1 is highest. Propose a follow-up only for a distinct uncovered transition, invariant, or
failure branch. Do not propose scenarios merely to reconfirm a finding or chase severity toward LOW.

## Execution rules

1. **Use the shared matrix.** Every executed state change names a transition id from `_analysis.md`. If a
   required transition has no id, flag a gap; do not create a private transition.
2. **Keep actors separate.** A service decision, store write, event publication, cache mutation, and
   external call occupy separate rows or detailed steps.
3. **Show diffs, not world dumps.** Use `+`, `~`, and `-` for every persistent write, queue/cache change,
   token lifecycle change, or externally visible side effect. Pure reads can say `no write`.
4. **Carry causality symbolically.** Reuse `REQ_1` or another correlation symbol across descendant
   effects when the spec defines causality. Do not invent a correlation contract.
5. **No magic eventuality.** Deferred behavior is a separate actor step with its declared trigger. If the
   trigger or timing is unspecified, flag it.
6. **Check targeted invariants at the relevant step and in the summary.** `not-reached` is different from
   `held`; unexercised behavior is not verified.
7. **Stop at silence, then branch honestly.** Add `[gap]`, state one minimal temporary assumption, and
   continue only if the assumption does not decide the very question being tested.
8. **Use the lowest honest severity.** Do not inflate uncertainty into a security finding or demote an
   invariant violation because the author probably intended something else.
9. **Preserve interrupted evidence.** If staging or publication fails, leave
   any `.tmp` or final artifact untouched for reconciliation and report the
   failure. Never delete, truncate, or silently reuse it.

## Severity

- **HIGH** - invariant violation, contradiction, undefined termination, unintended privilege/state,
  plausible loss/leak/double-spend, or missing actor at a required boundary.
- **MED** - materially ambiguous reached state, unhandled dependency failure, or race with inconsistent
  state but no established high-consequence impact.
- **LOW** - naming/citation mismatch or a bounded non-load-bearing ambiguity.

## Return

After publishing the assigned file, compute its normalized UTF-8 SHA-256 (CRLF/CR
to LF, Unicode NFC) and return exactly:

`Wrote <relative path> | sha256:<digest> | HIGH:<h> MED:<m> LOW:<l> | invariants:<held>/<targeted> | transitions:<covered>/<targeted>`
