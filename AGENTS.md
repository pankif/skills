# Repository instructions

This repository publishes portable AI-agent skills from
`plugins/skills/skills/`.

## Canonical workflow source

- A skill's `SKILL.md`, references, role prompts, schemas, fixtures, and scripts
  are platform-neutral source.
- Platform-specific files are adapters only: Claude manifests, Codex manifests,
  and `agents/openai.yaml` may describe discovery or UI behavior but must not
  contain a second copy of the workflow.
- Preserve the public skill names and explicit invocation forms unless a
  breaking change is intentionally versioned and documented.

## Skill changes

1. Keep YAML `name` equal to the skill directory name and `description` within
   the Agent Skills limit of 1024 characters.
2. State positive triggers and important non-triggers in the description.
3. Prefer proportional defaults. Put expensive proof machinery behind a named
   `strict` or `deep` mode.
4. State capability fallbacks. Never assume a particular subagent, worktree,
   hook, or parallel-execution API exists.
5. Keep persisted artifacts versioned. Reject unsupported versions explicitly;
   do not reinterpret or overwrite them silently.
6. Keep deterministic validator claims narrow: syntax, schema, enums, ordering,
   hashes, and references only. LLM-authored semantics require independent
   behavioral evidence.
7. Add or update public trigger, non-trigger, authority, and failure-path evals.

## Verification

Run from the repository root:

```bash
python scripts/validate_repository.py
```

The validator is a structural gate, not proof that a skill improves agent
behavior. Behavioral comparisons must use the paired-run contract in
`docs/evaluation.md` and record Claude Code and Codex separately.

## Git and publishing

Inspect the active remote before publishing. Commit and push only to the
repository and branch explicitly authorized by the user. Never treat a skill
mode such as `ship` as authority for a repository-maintainer action.
