# Analysis - fixture

Source: spec.md
Spec SHA-256: ec08dbd491889690596c6f5219200dc5bce8c087e3b576467eb08c890eaef7a3
Analysis version: simulate-analysis/v2
Queue schema: 2
Analyzed: 2026-07-17
Mode: standard
Focus: none
Declared transition IDs: T01
Declared invariant IDs: I01

## State-transition matrix

| ID | Initiator | Preconditions | From state | Action/interface | Writes and external effects | To state | Invariants | Spec status |
|---|---|---|---|---|---|---|---|---|
| T01 | service | order pending | pending | pay | status write | paid | I01 | explicit |
