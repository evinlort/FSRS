# 01 Directional Review State Schema

## Goal
Split review scheduling data into per-direction state so Czech-to-Russian and Russian-to-Czech can progress independently.

## Why this step is needed
The current schema stores exactly one FSRS state and one review-log stream per card, so reverse review cannot be added safely without separating directional progress first.

## Inputs / context
- `src/czech_vocab/repositories/schema.py`
- `src/czech_vocab/repositories/schema_migrations.py`
- `src/czech_vocab/repositories/card_repository.py`
- `src/czech_vocab/repositories/records.py`
- `tests/test_global_base_schema.py`
- `tests/test_card_repository.py`

## Implementation notes
- Add `card_review_states` keyed by `(card_id, direction)`.
- Add `direction` to `review_logs` and backfill existing rows to `cz_to_ru`.
- Preserve current forward schedule by migrating `cards.fsrs_state_json`, `cards.due_at`, and `cards.last_review_at` into `card_review_states`.
- Keep card content storage unchanged.
- Add repository support for reading and writing directional review state and review logs.
- Keep forward direction as the default for existing callers.

## Tests
- Fresh database bootstrap creates the new table and review-log direction column.
- Legacy database migration preserves forward state and backfills `review_logs.direction`.
- Repository tests cover forward default behavior plus reverse-direction state/log access.

## Done when
- Schema bootstrap supports fresh and migrated databases.
- Forward review data is preserved under `cz_to_ru`.
- Repository code can store and retrieve a second direction without overwriting forward state.

## Suggested commit message
feat: add directional review state schema
