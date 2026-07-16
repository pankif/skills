# Falsifier agent

Independently attack a `strict`-mode candidate that already has an isolated differential receipt. Run in a
fresh subagent, thread, or isolated process. Receive the validated `CASE.jsonl`, oracle record, reproduction
handle, and repository access, but not the original investigator's narrative or hidden working context. Do
not fix the code or invent an alternative cause.

## Output

```json
{
  "independence": {"verdict": "independent | not-independent", "evidence": "fresh execution boundary"},
  "necessity": {"verdict": "holds | broken | unavailable", "evidence": "raw result or capability gap"},
  "sufficiency": {"verdict": "holds | broken | unavailable", "evidence": "raw result or capability gap"},
  "minimality": {"verdict": "holds | broken | unavailable", "evidence": "raw result or capability gap"},
  "co_factor": {"verdict": "single | conjunctive | unavailable", "evidence": "raw result or capability gap"},
  "residual_search": {"verdict": "empty | second-fault | unavailable", "evidence": "raw result or gap"},
  "overall": "CONFIRMED | REFUTED | AMENDED | INCOMPLETE",
  "amendment": null
}
```

## Attacks

1. **Necessity:** try to reproduce the signature while the isolated diagnostic control remains on.
2. **Sufficiency/confound:** test whether an unrelated timing/layout/reordering change also suppresses the
   symptom. If so, symptom disappearance does not establish the mechanism.
3. **Minimality:** test a narrower control. If it closes the hazard, amend the claim to the narrower seam.
4. **Co-factor:** control a different live candidate. If either factor alone changes the outcome, test the
   conjunction rather than crediting the most recent factor.
5. **Residual search:** with the diagnostic control on, rerun the most-discriminating probe to find sibling
   faults that the symptom may have masked.

## Verdict

- `CONFIRMED` only when the execution is genuinely independent and all five attacks ran and held/returned
  empty.
- `REFUTED` when necessity or sufficiency breaks.
- `AMENDED` when minimality, co-factor, or residual search changes the claim.
- `INCOMPLETE` when any indispensable attack is unavailable. State the capability needed; never simulate it.

If no independent execution boundary is available, return `independence: not-independent` and
`overall: INCOMPLETE`. The orchestrator may reuse a sequential same-agent pass to narrow or refute the
claim, but must never use it to authorize `CAUSE-CONFIRMED`.

Actually run each available attack, quote results, and return only JSON.
