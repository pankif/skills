# Proportional substrate fallbacks

Use this reference only when the target cannot support the normal workflow.
Select the strongest honest rung for each slice; different slices may land on
different rungs.

## Shape and unfinished work

1. **Typed executable target:** compile-visible stub or explicit runtime raise.
2. **Untyped executable target:** failing assertion or reserved error path.
3. **Structured non-executable target:** schema-valid placeholder plus dry-run or
   parser check; never apply merely to validate shape.
4. **UI or asset target:** named component/frame/section plus visible sentinel.
5. **Prose target:** heading skeleton plus `TODO(autopilot:<id>)`.
6. **No boundary unit:** a flat checklist and grep-visible sentinel; disclose
   that completeness of shape is unverified.

A load/import/parse/render pass proves only that the shape resolves. Compare the
shape with an existing contract anchor when one exists. Without an anchor,
report `syntax-validated`, not “complete.”

## Behavior evidence

Prefer, in order:

1. existing acceptance or contract test with independent expected results;
2. trusted fixture or golden from a prior accepted run;
3. executable example against a declared contract;
4. safe smoke run with explicit output assertions;
5. type/schema/lint/build checks;
6. structural consistency only;
7. named human review or explicit `UNVERIFIED` handoff.

Properties such as round trip, idempotency, conservation, or “does not throw”
may detect defects but can stay green for the wrong intended transform. Record
them as supporting evidence below `behavior-verified` unless paired with an
independent semantic oracle.

## Side effects

- Prefer read-only probes, dry runs, plans, previews, and local fakes.
- If the only meaningful check consumes external state, do not loop it.
- Record external realization separately from local syntax/execution.
- A resource ID, migration version, published tag, or remote response is a
  realization receipt, not proof that the behavior is correct.
- Missing explicit authority stops at the local handoff regardless of available
  credentials.

## Human judgment

For visual quality, prose quality, UX feel, policy choice, or irreversible
tradeoffs, provide the smallest reviewable artifact and one falsifiable question
per material slice. A second model can critique the artifact but does not replace
the human verdict when the acceptance criterion is human judgment.

## Parallelism and independence

Use independent workers only when their inputs and write sets are separable.
When the runtime lacks workers, execute the same bounded roles sequentially. Do
not claim author independence in that fallback. Referential independence comes
from a genuinely different source of expected truth, not merely a second agent.
