# Behavioral evaluation records

The public catalogs under each skill define trigger and non-trigger prompts.
They are inputs, not evidence that a workflow is better than a baseline.

When running a paired comparison, save one record per arm using
`result.schema.json` and a path such as:

```text
evals/results/<skill>/v<evaluation-version>/<platform>/<case>/<baseline|skill>.json
```

The baseline arm must not receive the skill body, expected output, hidden rubric,
or holdout identifier. Both arms must use the same fixture commit, model class,
tools, sandbox, network, and budget. If any of those differ, label the comparison
`invalid-run` instead of interpreting it.

Do not commit private prompts, credentials, proprietary fixture contents, or
hidden holdout rubrics. A public result may reference an immutable external
fixture identifier and include only observable commands, edits, effects, and
claims.

Claude Code and Codex are separate `platform` values. Never copy a pass from one
platform to the other.
