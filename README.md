# Pankif Skills

Portable workflows for AI coding agents. The repository currently ships four
workflow skills for Claude Code and Codex from one shared source:

| Skill | Use it for | Default posture |
| --- | --- | --- |
| [`autopilot`](plugins/skills/skills/autopilot/) | Drive a substantial feature from intent to verified local work | `build --standard` |
| [`spec`](plugins/skills/skills/spec/) | Turn an ambiguous product idea into an implementable spec | `quick` interview |
| [`simulate`](plugins/skills/skills/simulate/) | Stress-test a spec before implementation | `standard` scenarios |
| [`diagnose`](plugins/skills/skills/diagnose/) | Investigate defects and incidents without guessing a cause | `quick` diagnosis |

`sketch` remains available as an experimental workflow, but it is not part of
the portability and validator redesign in this release.

## Design principles

- One canonical `SKILL.md` per workflow; Claude Code and Codex load the same
  instructions.
- Thin platform metadata only. Platform adapters do not fork the workflow.
- Practical defaults with explicit `deep` or `strict` modes for high-blast work.
- Missing platform capabilities cause a documented fallback and a weaker claim,
  never a silently skipped step.
- Structural validators prove structure only. They do not claim that an LLM's
  conclusions, classifications, or causal arguments are true.
- Remote writes require current, explicit user authority. A mode name is not
  permission to push, open a PR, merge, deploy, publish, or apply infrastructure.

The shared capability and verification contracts are documented in
[`docs/runtime-compatibility.md`](docs/runtime-compatibility.md). Evaluation
rules live in [`docs/evaluation.md`](docs/evaluation.md).

## Install

### Claude Code

```text
/plugin marketplace add pankif/skills
/plugin install skills@pankif
```

Update later with:

```text
/plugin marketplace update pankif
```

### Codex

```bash
codex plugin marketplace add pankif/skills
codex plugin add skills@pankif-skills
```

Restart Codex or open a new task after installation so the new skill metadata is
loaded. The repository also contains native Codex metadata in
`.agents/plugins/marketplace.json`, `plugins/skills/.codex-plugin/plugin.json`, and each
skill's `agents/openai.yaml`.

### Manual single-skill install

Copy one directory from `plugins/skills/skills/` into a supported skills directory.

```bash
# Claude Code
cp -R plugins/skills/skills/spec ~/.claude/skills/spec

# Codex user scope
cp -R plugins/skills/skills/spec ~/.agents/skills/spec
```

On Windows, use `Copy-Item -Recurse` and the equivalent directory under your
user profile. No symlink or shell-specific behavior is required by the skills.

## Development

Run the repository checks with Python 3.9 or newer; all scripts use only the
standard library. Use the Python 3 launcher available on the host (`python`,
`python3`, or `py -3` on Windows).

```bash
python scripts/validate_repository.py
```

The check validates frontmatter constraints, manifests, JSON/schema fixtures,
local paths referenced directly from each `SKILL.md`, and each skill's
deterministic artifact validator. It does not replace paired behavioral
evaluation.

When changing a skill:

1. Keep `SKILL.md` focused and move detailed protocols into `references/`.
2. Add trigger and non-trigger cases to its public eval catalog.
3. Add positive and negative fixtures for deterministic validators.
4. Run the repository validator on the target platforms.
5. Record behavioral runs separately for Claude Code and Codex; do not call a
   structural pass a behavioral improvement.

## Repository layout

```text
.agents/plugins/marketplace.json   Codex marketplace metadata
.claude-plugin/marketplace.json    Claude Code marketplace metadata
plugins/skills/
  .codex-plugin/plugin.json        Codex plugin manifest
  .claude-plugin/plugin.json       Claude Code plugin manifest
  skills/<name>/
    SKILL.md                        canonical portable workflow
    agents/openai.yaml              Codex UI/invocation metadata
    agents/*.md                     portable role prompts, when needed
    references/                     progressive-disclosure guidance
    schemas/                        versioned artifact schemas
    scripts/                        deterministic validators
    fixtures/                       validator examples
    evals/evals.json                public behavioral cases
scripts/validate_repository.py      repository-wide structural check
evals/result.schema.json            paired behavioral result format
```

This fork is maintained at <https://github.com/pankif/skills>.
