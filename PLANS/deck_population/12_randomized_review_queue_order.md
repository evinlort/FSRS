# 12 Randomized Review Queue Order

## Title
Randomize review card order within the deck queue

## Problem this step solves
The review queue always shows cards in the same deterministic order, so repeated visits to the same deck start with the same cards.

## Why it is needed
The requested behavior is to vary deck card order between review sessions without breaking the existing due-first scheduling rules.

## Scope
- Keep queue selection deck-scoped.
- Keep learned due cards ahead of new cards.
- Randomize order within the due-card group and within the new-card group.
- Keep the change inside the review queue service and its tests.

## Dependencies
- `02_existing_flows_on_deck_links.md`
- `../ui/03_review_queue_rules.md`

## Implementation notes
- Keep repository queries deterministic and sorted; do not move randomness into SQL.
- Inject the randomization function into `StudyService` so tests can control the order.
- Shuffle the due list before taking the next due card, and shuffle the new list before taking the next new card.
- Do not add session state, schema changes, or UI controls in this step.

## Acceptance criteria
- Learned due cards still appear before untouched cards.
- Repeated queue reads are no longer locked to repository order.
- Deterministic tests can prove the service uses randomized selection for both due and new groups.
- Existing review page behavior continues to work without template changes.

## Verification approach
- Add service tests for shuffled due-card selection and shuffled new-card selection.
- Run targeted review service and UI tests, then `ruff check`.

## Risks / assumptions
- Randomness happens on each queue read; the app does not preserve a shuffled session order.
- Fully mixing due and new cards is out of scope.
