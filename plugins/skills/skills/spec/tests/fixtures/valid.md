---
title: 'Shared quiet hours'
domain: notifications
last_updated: 2026-07-17
---

# Shared quiet hours

## Purpose
Define a shared quiet-hours experience.

## Glossary
Quiet hours - a period with paused notifications.

## Actors
Workspace member and workspace owner.

## User-facing behavior
Members can see when quiet hours apply.

## Flows
An owner sets a period and members see it.

## States and transitions
Inactive becomes active at the configured start.

## Invariants
- The current state is visible.

## Edge cases
- A member changes time zone.

## Success criteria
- Members can identify the next active period.

## Out of scope
- Personal schedules.

## Open questions
(none)

---

## Technical appendix
> Derived from repository evidence; this section is implementation guidance, not the product contract.

### Evidence and conflicts
Unknown.

### Stack & placement
Unknown.

### Data model and contracts
Unknown.

### Migration & rollback
Unknown - no repository policy found.

### Integration points
Unknown.

### Risks & follow-ups
Repository evidence is required.
