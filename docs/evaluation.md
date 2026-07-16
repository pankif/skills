# Evaluation contract

Structural validation and behavioral evaluation answer different questions.

## Structural validation

`python scripts/validate_repository.py` may establish only that:

- skill frontmatter and names satisfy format constraints;
- JSON, manifests, schemas, and fixtures parse;
- local files referenced directly from each `SKILL.md` exist;
- versioned workflow artifacts satisfy their narrow schemas;
- declared ordering, hashes, identifiers, and state transitions are internally
  consistent where a validator explicitly checks them.

It must not claim that a product decision is correct, a scenario is complete, a
hypothesis is causal, or an agent will trigger the right skill.

## Paired behavioral runs

Compare a skill run with a no-skill baseline only when both runs have:

- the same clean fixture commit and initial state;
- the same model class, tools, sandbox, network, context, and resource budget,
  except for the target skill body;
- no access to the hidden rubric or expected answer;
- scoring based on observable edits, commands, effects, artifacts, questions,
  and verification claims rather than wording similarity.

Record Claude Code and Codex separately. Preserve the original rubric and result
when the skill changes; create a new evaluation version instead of rewriting a
failed expectation after the fact.

Store machine-readable records using `evals/result.schema.json`. The repository
does not fabricate result files for runs that were not performed.

Every skill catalog should cover:

- positive trigger cases;
- non-trigger or proportionality cases;
- unavailable-capability fallback;
- unsupported legacy artifact behavior;
- authority boundaries when remote effects are relevant;
- honest verification claims under weak or absent oracles.

Useful metrics include correctness, trigger accuracy, unnecessary questions,
unnecessary artifacts, unauthorized effects, tool calls, runtime, and the
highest honestly supported verification state. Unavailable metrics are recorded
as unavailable, never estimated.

Allowed result labels:

- `not-run`
- `invalid-run`
- `baseline-recorded`
- `paired-recorded`
- `behavior-pass`
- `behavior-fail`
- `human-review-needed`

Do not publish an aggregate "improved" claim while comparison runs are invalid
or only structural checks have run.
