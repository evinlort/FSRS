# 03 Dashboard Stats Map Regression

## Goal
Finish downstream direction handling, keep forward-only screens working, and update the project map.

## Why this step is needed
The new directional storage changes dashboard queries immediately and requires forward-only consumers to switch away from `cards` schedule columns.

## Inputs / context
- `src/czech_vocab/services/dashboard_service.py`
- `src/czech_vocab/services/stats_service.py`
- `src/czech_vocab/services/card_catalog_service.py`
- `docs/PROJECT_MAP.md`
- related dashboard, stats, and catalog tests

## Implementation notes
- Make dashboard counts and recent reviews direction-aware.
- Keep stats and card catalog on `cz_to_ru` only in this feature.
- Remove remaining application reads of review schedule from `cards`.
- Update `docs/PROJECT_MAP.md` from verified code.

## Tests
- Dashboard tests for direction-aware counts and recent reviews.
- Stats and card catalog regression tests against forward-direction state.
- Relevant broader pytest run plus `ruff check`.

## Done when
- Dashboard matches the chosen review direction.
- Stats and card catalog still work for forward review.
- The project map documents the new schema and flows.

## Suggested commit message
feat: finish directional review integration
