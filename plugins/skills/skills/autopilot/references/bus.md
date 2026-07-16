# Strict decision bus (schema version 2)

The BUS is a strict-mode handoff record for work that crosses several stages or
workers. It prevents a material decision from being silently reclassified, but
it is not a truth oracle. Quick and ordinary standard work should use an inline
decision ledger instead of creating this file.

## Location and lifecycle

Use a run-local path such as:

```text
.skill-runs/autopilot/<run-id>/BUS.json
```

Seal the record before implementation starts. It is an immutable decision
snapshot; verification progress belongs in command receipts and the final
report, not in the BUS. Amendments are separate artifacts that name the
superseded `run_id`; they do not edit or extend the sealed BUS in place.
Keep run artifacts out of the product commit unless the user requests them.

Readers support `schema_version: 2` and `analysis_version: autopilot-0.6`.
An unsupported version is a fail-closed resume boundary: preserve the original,
report it, and offer a clean restart or explicit migration. Modification time is
never a compatibility signal.

## Record shape

The canonical machine-readable schema is `../schemas/bus.schema.json`. A record
contains:

- `schema_version` and `analysis_version`;
- stable `run_id`, requested `mode`, selected `depth`, and `target`;
- `prompt_sha256` for the exact normalized input used to classify the run;
- `decisions`, each with a unique ID, category, reach, disposition, statement,
  provenance, and blast rank;
- `unfinished_markers` used for this run;
- `disclosure_decision_ids`, which must reference existing decisions;
- `outward_authority`, a list of action-target-evidence receipts recorded from
  the current request;
- `integrity.canonical_sha256` over the canonical JSON with that digest replaced
  by 64 zeroes.

## Decision vocabulary

Categories:

- `public-contract`
- `persistent-format`
- `destructive`
- `trust-boundary`
- `outward-effect`
- `real-world-mutation`
- `internal`

Reach is `local`, `external`, or `unknown`. Unknown is never silently demoted to
local. Disposition is:

- `derived`: pinned by a cited current source;
- `defaulted`: a reversible local choice made for progress;
- `open`: requires a user or authoritative contract decision;
- `stop`: no work may cross this boundary yet.

Value provenance is explicit. A wire tag, unit, format version, default, field
name, auth model, or other serialized/computed value is not “derived” merely
because the agent prefers it. Cite the user statement, code, configuration,
test, or standard that pins it; otherwise mark it defaulted or open according to
blast radius.

## Authority vocabulary

Allowed action labels are deliberately limited to repository delivery:

```text
commit, branch, push, pull-request
```

Each receipt binds one action to one target and one exact current-request
evidence string. The validator can only check that fields and labels are well
formed. It cannot prove that the quoted request actually grants authority.
Runtime policy and the current user request remain decisive. Merge, publish,
deploy, apply, send, and production mutation are not legal BUS actions; stop at
a handoff.

## Verification vocabulary

Use the shared ordered states in command receipts and the final report:

```text
designed, generated, syntax-validated, executed, behavior-verified, human-reviewed
```

Evidence is a list of factual observations such as a command with exit status, a
fixture identifier, or a human verdict. Do not store “verified by agent” as
evidence.

## Validation

Resolve `<skill-root>` as the directory containing the loaded `SKILL.md`, and
choose an available Python 3 launcher:

```text
<python> "<skill-root>/scripts/validate_bus.py" path/to/BUS.json
<python> "<skill-root>/scripts/validate_bus.py" --seal path/to/BUS.json
```

`--seal` writes the canonical digest after all other fields are final. A normal
validation checks versions, required fields, enums, ID uniqueness, reference
integrity, digest format, and digest equality.

Prompt hashing first converts CRLF and CR to LF, normalizes Unicode to NFC, then
hashes the exact remaining text as UTF-8. Pass `--prompt-file` when the original
input is available to check the digest. Canonical BUS integrity uses UTF-8 JSON
with keys sorted, no insignificant whitespace, non-ASCII characters preserved,
and `integrity.canonical_sha256` replaced by 64 zeroes. The bundled validator is
the normative implementation.

Passing validation proves only that the record has supported syntax and is
internally intact. It does **not** prove:

- that evidence text is true;
- that a decision was classified correctly;
- that authority exists;
- that acceptance coverage is complete;
- that behavior or intent is correct.
