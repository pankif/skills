---
name: diagnose
description: >-
  Investigate an observed software defect when its cause is unknown. Use for unexplained wrong output,
  crashes, regressions, flaky tests, performance degradation, and production incidents; use quick mode
  for bounded everyday debugging, strict mode when the user requests causal proof or the fault is
  high-risk/stateful/intermittent, and incident mode when production evidence is incomplete or safe
  reproduction is unavailable. Do not use for obvious syntax/import errors with a known location and
  fix, routine implementation of a known fix, planned feature work, review-only requests, or a cause
  already verified by the user. Diagnose and propose a next action; do not implement the fix unless the
  user separately asks for implementation.
---

# Diagnose

Work backward from an exact symptom. Separate observed facts, hypotheses, and proof strength. Never
upgrade a plausible explanation to a proven cause.

## Route the mode

Choose one mode before investigating and state it in the output:

| Mode | Use when | Evidence bar | Default deliverable |
|---|---|---|---|
| `quick` | Ordinary deterministic defect with a cheap local reproduction | Reproduce, inspect the failing path, test the leading explanation against at least one rival | `DIAGNOSIS.md` or an equivalent concise response |
| `strict` | The user asks for proof, or the fault is flaky, stateful, security/billing critical, cross-system, or expensive to misdiagnose | Full falsification and isolated differential confirmation | Versioned `CASE.jsonl` plus `CAUSE.md` |
| `incident` | Live incident, incomplete telemetry, unsafe reproduction, or limited production access | Operationally useful evidence without pretending the cause is proved | `INCIDENT-DIAGNOSIS.md` or an equivalent incident brief |

Default to `quick`. Do not escalate to `strict` merely because more rigor sounds desirable. An explicit
`$diagnose strict` request overrides routing. If the reported error already names a known syntax/import
problem and its direct fix, handle it directly without loading this workflow.

## Shared workflow

### 1. Pin the symptom and oracle

Write one machine-checkable signature: assertion and location, output diff, panic frame, threshold, or log
pattern. Identify the expectation that makes the observation a defect.

Classify the oracle as exactly one of:

- `trusted`: consistent with an explicit contract, or no contrary evidence was found;
- `contested`: evidence conflicts or the intended behavior is ambiguous;
- `contradicted-by-explicit-contract`: a stronger explicit contract clearly says the expectation is wrong.

Only the last state stops investigation of the current signature. Stronger contracts include explicit
user acceptance criteria, an approved spec/ADR/product decision, a public protocol/API contract, or a
recorded compatibility guarantee. Code age, test age, `git blame`, comments, deliberate conditionals, and
long-standing behavior are **weak priors only**. They may make the oracle `contested`; they cannot by
themselves produce `contradicted-by-explicit-contract`.

Read `agents/oracle-check-agent.md` when delegating this check.

### 2. Discover the available control surface

Discover actual build, run, reproduce, and observation commands. Record what each instrument cannot see.
Prefer controls already supported by the repository. Read `references/probes.md` for capability discovery
and probe selection.

If a preferred tool, environment, permission, or reproducer is unavailable, do not fabricate its result
or stop automatically. Use the remaining safe evidence, narrow the claim, and name the missing capability.
Return `BLOCKED` only when no meaningful next inference is possible without it.

### 3. Reproduce proportionally

- `quick`: obtain one reliable reproduction when practical. If it cannot reproduce within the small
  budget, report what was checked and the next discriminating observation; do not guess.
- `strict`: use the complete deterministic/statistical gate in `references/reproduce-ladder.md`. A single
  green run never clears a flaky hypothesis.
- `incident`: do not recreate destructive production conditions. Pin the observed window and evidence,
  then reconstruct or replay only in a safe environment when available.

### 4. Compare falsifiable explanations

Express each hypothesis as a mechanism with a prediction and a disconfirming observation. In `quick`, keep
the set bounded and test the leading explanation against at least one credible rival. In `strict`, keep at
least two axes live until evidence eliminates them and run one most-discriminating probe per round. Evidence
kills a hypothesis only when it observes something that hypothesis forbids.

### 5. Close at the mode's evidence bar

`quick` may report only a **best-supported explanation**, never a proven or confirmed cause. If a
differential receipt appears available or the user asks for proof, escalate to `strict` before making a
causal confirmation claim. `incident` must never convert ranked hypotheses into facts. Only `strict` may
use the claim **differentially confirmed**, and only after all strict gates below pass.

## Strict mode: causal proof

Use the full protocol only in `strict`:

1. Create or resume `CASE.jsonl` using `schemas/case-v1.schema.json`.
2. Validate it with the bundled validator before reading or appending.
3. Reproduce deterministically or statistically.
4. Seed falsifiable hypotheses across at least two plausible axes.
5. Run discriminating probes; preserve raw observations and killed rivals.
6. Trace the corrupt value upstream and check every independent consumer to rule out a symptom suppressor.
7. Differentially confirm all three legs: control off -> signature present; isolated control on -> signature
   absent and hazard removed; control released -> signature returns. For a statistical symptom, compare
   two samples at the chosen confidence floor.
8. Spawn a genuinely independent falsifier with no access to the investigator's narrative and run the
   attacks in `agents/falsifier-agent.md`: necessity, sufficiency/confound, minimality, co-factor, and
   residual-search.

The control is diagnostic, not the final fix. It must change only the suspected mechanism; logging,
reordering, broad guards, or environment changes are confounded. If isolation or the return leg is not
possible, report `NARROWED`, `TIMING-SUPPRESSED`, or `BLOCKED`, not `CAUSE-CONFIRMED`.

Independence is a proof gate. Use a fresh subagent, thread, or isolated process that receives only the
validated CASE evidence, oracle, and repro. If the platform cannot provide that boundary, a sequential
same-agent challenge may still narrow or refute the claim, but it can never authorize `CAUSE-CONFIRMED`.
Report `NARROWED` and name the missing independent-falsifier capability.

### CASE ledger safety

`CASE.jsonl` is append-only evidence, not a semantic proof engine. The validator checks only JSONL record
shape, supported schema and analysis versions, case identity, RFC3339 timestamps, record types, and
contiguous sequence numbers. It does not verify that commands ran, evidence is true, or a cause is correct.

Resolve every bundled path from the directory containing the **loaded** `SKILL.md`, never from the target
repository's current working directory. Call that absolute directory `<diagnose-skill-dir>`. Select a
working Python 3 launcher by trying `python3`, then `python`, then the Windows launcher `py -3`; verify it
is Python 3. If none exists, record a capability gap and do not silently skip validation. Invoke:

```text
<python-launcher> "<diagnose-skill-dir>/scripts/validate_case.py" "<out>/CASE.jsonl"
```

If Python or the installed skill path is unavailable, investigation may continue, but the ledger remains
structurally unvalidated. Missing mandatory CASE validation caps the terminal at `NARROWED` or `BLOCKED`;
it can never yield `CAUSE-CONFIRMED`.

Never truncate, renumber, rewrite, or silently replace an existing ledger. A legacy ledger without a
supported schema or analysis version and a ledger with an unknown version fail closed. Preserve it and
choose an explicitly named new path or perform a reviewed migration. When checking a candidate append
against a snapshot, run:

```text
<python-launcher> "<diagnose-skill-dir>/scripts/validate_case.py" "<candidate>" --previous "<snapshot>"
```

The candidate must preserve the previous file byte-for-byte as its prefix.

## Incident mode: useful without false certainty

Return four salience-ordered sections:

1. **Proven facts** - timestamps, affected scope, signatures, state changes, and commands/logs actually
   observed. Distinguish direct observation from inference.
2. **Ranked hypotheses** - mechanism, supporting evidence, contradictory evidence, and confidence reason.
   Label every item `unproven`.
3. **Safe mitigation** - reversible containment with blast radius and rollback. Do not perform external,
   destructive, or production actions without explicit authorization.
4. **Evidence needed** - the smallest next observation or controlled experiment that separates the leading
   hypotheses, plus any missing access/capability.

End a non-causal incident result with `INCIDENT-ASSESSMENT`. An incident can end usefully with no root-cause
claim.

## Outputs and terminals

For `quick`, include: signature, oracle state, reproduced facts, explanations tested, best-supported result
with confidence limits, proposed next action, and checks not run.

For `strict`, `CAUSE.md` includes: oracle state and contract evidence; reproduction; isolated differential
receipt; hazard-removal evidence; killed hypotheses; upstream/all-consumer check; falsifier verdict; and a
minimal mechanism-impossible fix proposal. Use `CAUSE-CONFIRMED` only when every strict gate passed,
including a genuinely independent falsifier.

Legal terminals are:

- `CAUSE-CONFIRMED` - strict proof complete;
- `INCIDENT-ASSESSMENT` - operational incident result with facts and explicitly unproven hypotheses;
- `NARROWED` - evidence reduced the space but did not prove one cause;
- `NOT-REPRODUCED` - no reliable handle; include an armed observation/trap when safe;
- `ORACLE-CONTRADICTED` - the signature conflicts with a stronger explicit contract;
- `TIMING-SUPPRESSED` - the symptom vanished but hazard removal was not shown;
- `SYMPTOM-ONLY` - a local control hid the manifestation while corrupt state remained upstream;
- `BLOCKED` - a named capability is indispensable and unavailable.

## Boundary

Diagnose proposes the smallest mechanism-impossible fix and a one-command regression check, then hands off.
Do not edit production code, publish, deploy, or apply the mitigation unless the user separately authorizes
that action.

## References and agents

- `references/probes.md` - capability discovery, instrument blindness, and discriminating probes.
- `references/reproduce-ladder.md` - strict reproduction/statistical handling and the observation-trap floor.
- `agents/oracle-check-agent.md` - oracle classification without debugging.
- `agents/probe-agent.md` - one strict-mode controlled experiment.
- `agents/falsifier-agent.md` - independent strict-mode attacks on a candidate proof.
