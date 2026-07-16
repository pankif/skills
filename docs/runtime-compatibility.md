# Runtime compatibility contract

The four core workflows use a common capability vocabulary instead of naming a
platform-specific tool. A runtime may expose the capability under any name.

| Capability | Preferred behavior | Required fallback |
| --- | --- | --- |
| Read/search target | Inspect files, history, configuration, and evidence | Ask for the missing artifact if it is outside the accessible target |
| Execute command | Capture command, exit code, and actual output | Mark execution unavailable; do not report the command as run |
| Isolated worker | Give an independent role a bounded task and context | Run the role sequentially in the current agent and disclose lost independence |
| Parallel workers | Run independent scenarios concurrently | Run them sequentially with the same inputs and merge deterministically |
| Persistent local artifact | Save resumable state beside the requested output | Return the artifact inline and state that resume is unavailable |
| Human decision gate | Pause for an explicit judgment or authority decision | Stop at the gate; never infer approval from silence |
| Outward effect | Commit, push, PR, publish, deploy, apply, send, or mutate remote state | Perform only actions the active workflow permits and that the current request specifically names with a target; otherwise stop at a handoff |

Missing convenience capabilities reduce speed or confidence, not safety. A
workflow must never silently omit a required check because a named platform API
does not exist.

## Verification states

Artifacts advance only when evidence supports the next state:

```text
designed -> generated -> syntax-validated -> executed -> behavior-verified -> human-reviewed
```

- `designed`: intended shape has been described.
- `generated`: the artifact exists.
- `syntax-validated`: deterministic structure/schema checks passed.
- `executed`: the relevant command actually ran and its result was captured.
- `behavior-verified`: an independent behavior oracle passed. Round trips,
  self-consistency, and schema checks alone do not qualify.
- `human-reviewed`: the named human judgment was explicitly supplied.

No state may be skipped or inferred. A report can list several slices at
different states.

## Authority

Local analysis and reversible workspace edits are distinct from outward effects.

- `plan` never authorizes implementation or outward effects.
- `build` authorizes in-scope local implementation, not remote mutation.
- `ship` is a compatibility label for a requested delivery workflow. It does
  not itself authorize any outward action. Autopilot limits execution to
  repository delivery (`commit`, `branch`, `push`, `pull-request`); merge,
  publish, deploy, apply, send, and production mutation remain handoffs.
- An outward action is allowed only when the current user request explicitly
  names both the action and its target. Authority does not cascade: permission
  to commit is not permission to push; permission to open a PR is not permission
  to merge; permission to prepare deployment is not permission to deploy.

Destructive actions and production mutation always keep their normal platform
approval boundaries.

## Persisted artifact compatibility

Each machine-readable artifact declares an integer `schema_version` and, where
analysis semantics matter, an `analysis_version`.

Readers must:

1. validate before use;
2. accept only explicitly supported versions;
3. preserve an unsupported artifact unchanged;
4. stop with a migration or restart instruction rather than guessing;
5. never overwrite an artifact merely because a newer workflow cannot parse it.
