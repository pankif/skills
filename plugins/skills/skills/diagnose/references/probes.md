# Capability discovery and discriminating probes

A probe is a controlled experiment over one search axis. Discover how to realize it in the current
repository; never assume a stack, runner flag, environment, or production access exists.

## Capability map

Record only verified capabilities:

- exact build, test, run, replay, and observation commands;
- available axes: commit, input, config, persistent state, ordering/timing, environment, and toolchain;
- real controls for each axis, including permissions and safety limits;
- instrument blindness: what each checker cannot observe;
- missing capabilities and what would provide them.

Use the map proportionally:

- `quick`: inspect only capabilities needed for the leading and rival explanation;
- `strict`: persist a capability record in `CASE.jsonl` before probes;
- `incident`: prefer existing telemetry and safe replay; never treat unavailable production control as
  permission to mutate the system.

If a preferred realizer is missing, try another safe axis. Return `BLOCKED` only if the missing capability
is indispensable to any meaningful next inference.

## Probe selection

Choose the cheapest experiment that best separates live hypotheses. Symptom shape provides a prior, not a
verdict. Keep evidence from other axes alive until an observation actually contradicts it.

| Symptom | Useful starting axis | Example discriminating probe |
|---|---|---|
| deterministic failing test | recent semantic change or data path | bisect a known-good range; assert the value at the pipeline midpoint |
| crash/panic | captured input and state read by the faulting frame | replay and minimize the input; compare state immediately before the frame |
| wrong output | data flow | binary-search the first correct-to-wrong transition |
| performance regression | commit, load, or accumulation rate | threshold bisect for step changes; profile and measure rate for gradual changes |
| flaky or suite-only failure | ordering, persistent state, timing | amplify safely; compare alone vs after candidate predecessor; vary one source |
| build failure | toolchain, dependency, generated artifact | compare environment/toolchain; regenerate and diff; bisect semantic changes |
| environment-dependent defect | config/environment delta | capture both environments; toggle one verified delta at a time |
| production incident | triggering request/state/time window | correlate existing telemetry; replay captured input only in a controlled target |

## Probe integrity

1. Write the prediction and disconfirming outcome before running the command.
2. Change one axis. Broad logging, reordering, restarts, and environment changes are confounded controls.
3. Quote raw output and command provenance.
4. A negative result kills a hypothesis only when the instrument can see that mechanism.
5. For statistical symptoms, compare samples rather than individual runs.
6. A bisection point is localization, not automatically a cause. Reject non-semantic first-bad commits
   until a semantic delta is demonstrated.
7. If a probe kills nothing, switch axes or report the limit; do not repeat it for the appearance of rigor.

For save/replay, replica divergence, or sequence-dependent faults, capture one operation log, run it through
both paths, and bisect the first diverging operation. Treat the sequence invariant as the candidate
mechanism rather than blaming the last observed function.
