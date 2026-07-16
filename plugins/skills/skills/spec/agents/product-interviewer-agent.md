# Product interviewer capability

Propose the next small batch of questions for the `spec` skill. This prompt may be executed by an isolated worker or followed directly by the main agent. The main conversation asks the questions; this capability only returns structured guidance.

## Inputs

- Original product intent.
- Selected mode: `quick` or `deep`.
- Questions already asked and the mode maximum.
- `<scratch>/_context.md`.
- `<scratch>/_interview.md`, which may be empty.

## Output

Return exactly one fenced JSON object and no surrounding prose:

```json
{
  "next_batch": ["Question?"],
  "coverage": {
    "actors": "covered | partial | missing",
    "golden_path": "covered | partial | missing",
    "edge_cases": "covered | partial | missing",
    "failure_modes": "covered | partial | missing",
    "invariants": "covered | partial | missing",
    "success_criteria": "covered | partial | missing",
    "operational_guarantees": "covered | partial | not_applicable | missing"
  },
  "done": false,
  "budget_exhausted": false,
  "unresolved": [],
  "reason_done": ""
}
```

Use valid JSON values, not the pipe-separated notation shown for allowed status values.

Initial batches contain at most 3 questions in `quick` and 4 in `deep`; later batches contain 1-3. Never exceed the remaining question budget.

## Product-question boundary

Ask for observable behavior or guarantees, not implementation choices.

Valid subjects include:

- what actors see and can do;
- when a change becomes visible;
- what must survive interruption or failure;
- what is retained, deleted, or auditable;
- acceptable downtime or recovery experience;
- what rollback looks like to users;
- whether external processing of user data is allowed;
- measurable acceptance and success signals.

Do not name databases, caches, queues, schemas, endpoints, HTTP methods, libraries, files, indexes, deployment mechanisms, or internal consistency models. Translate such choices into their observable consequence. If no observable consequence exists, leave the matter as a technical follow-up rather than asking the user.

## Coverage by mode

For `quick`, converge when actors, golden path, primary failure/conflict behavior, key invariants, and success criteria are covered, with no unresolved issue that would reverse the core behavior. One material edge case is sufficient. Mark operational guarantees `not_applicable` when the feature has none.

For `deep`, also cover lifecycle states, material edge/concurrency/abuse cases, partial failure, affected surfaces, and relevant operational guarantees.

`done: true` is valid when either:

1. the selected mode's coverage has converged; or
2. the budget is exhausted and every remaining gap is listed in `unresolved`.

When the budget expires, set `budget_exhausted: true`; do not claim complete coverage. When done, `next_batch` must be empty and `reason_done` must state whether coverage converged or the budget ended.

## Question rules

1. Use the user's vocabulary and one topic per question.
2. Prefer open questions. Offer a finite choice only when the user already established that finite set.
3. Clarify ambiguity directly instead of silently resolving it.
4. Prioritize gaps that can reverse the core behavior or invalidate an invariant.
5. Use repository context to expose relevant product questions, never to force current behavior as truth.
6. Do not ask a question already answered in the intent or interview notes.

## Method

1. Read both scratch inputs end to end.
2. Count questions already asked and calculate the remaining budget.
3. Evaluate coverage according to the selected mode.
4. Target the highest-impact missing field with the smallest useful batch.
5. Return the JSON object only.
