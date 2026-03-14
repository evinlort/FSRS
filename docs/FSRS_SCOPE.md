# FSRS_SCOPE.md

## Product goal
Build an MVP web app for learning Czech vocabulary from CSV using FSRS-style scheduling.

## MVP functional scope
The MVP must allow the user to:
- import vocabulary from CSV
- store cards persistently
- review cards with four grades: Again, Hard, Good, Easy
- calculate the next review using FSRS scheduler logic
- persist review history
- show due cards for study
- browse/search imported cards

## FSRS scope for MVP
Implement only the scheduler part of FSRS.

Use:
- default FSRS parameters
- desired retention = 0.90 by default
- persistent per-card review history

Do not implement in MVP:
- optimizer fitting from user history
- parameter training UI
- advanced statistics dashboards
- multi-user support
- synchronization across devices

## Card state expectations
Each card should have persistent scheduling-related state sufficient to support FSRS scheduling.
Review history must be stored so the project can support optimizer work later.

## CSV expectations
CSV header structure may evolve over time.
Parse by headers, not position.

Required logical meaning:
- Czech word or lemma
- Russian translation

Optional:
- notes
- any additional metadata columns

Unknown columns must not break import.

## Non-functional constraints
- maintainable architecture
- small focused modules
- testable code
- minimal dependencies
- SQLite persistence for MVP
