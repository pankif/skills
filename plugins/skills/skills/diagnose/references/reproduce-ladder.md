# Strict reproduction gate and observation ladder

Read this reference for `strict` mode or when a quick investigation discovers a genuinely intermittent
failure. It is not the default workflow for ordinary deterministic defects, and it must not force unsafe
reproduction during an incident.

## Reproduction classes

Pin one exact signature and run the same named handle repeatedly:

- `deterministic`: the signature appears on every run under the stated conditions;
- `statistical`: the signature appears `k/N` times; record the rate, sample size, and a confidence interval;
- `unreproduced`: the signature did not appear within the declared budget.

For a statistical handle, every downstream A/B probe compares two samples. A single green run cannot kill
a flaky hypothesis. Record the sample plan before running the probe; do not change it after seeing results
without marking the change as exploratory.

## When reproduction is unavailable

Descend only as far as the available, safe capability surface allows:

1. **Amplify an existing knob.** Increase iterations, use the real load/concurrency, replay the captured
   input, or run in the failing environment if doing so is safe and authorized.
2. **Vary one nondeterminism source.** Compare writer count, prior-test ordering, seed, wall clock,
   persistent state, process timing, iteration order, or toolchain. Do not assume a control exists.
3. **Use a relevant instrument.** A sanitizer report can turn a statistical symptom into a deterministic
   handle only when the instrument can observe that class. A clean result from a blind instrument is
   non-exonerating.
4. **Arm the next observation.** If the safe budget ends, return `NOT-REPRODUCED` with the observed rate,
   narrowed space, instrumentation or capture needed at the suspected seam, and the evidence that would
   discriminate each surviving branch.

Do not add production instrumentation, change retention, restart services, or mutate external state without
authorization. In `incident` mode, a structured request for the next evidence is a valid result; an armed
trap is optional and must be safe.

## Statistical comparison

For control-off and control-on samples, report raw counts and the chosen decision rule. Use a method
appropriate to the sample size (for example, Fisher's exact test for small counts or an interval comparison
for larger samples). Do not claim causal closure from a rate change alone: strict confirmation still needs
an isolated mechanism control, hazard-removal evidence, and the return leg.

## Honest floor

An unreproduced symptom cannot yield `CAUSE-CONFIRMED`. Legal outcomes are a narrowed explanation, a safe
next experiment, an observation trap, or `BLOCKED` when a specific indispensable capability is unavailable.
