# 02 Directional Study Flow

## Goal
Make the review queue, grading flow, undo flow, and review template direction-aware.

## Why this step is needed
Once directional state exists, the study flow must choose the correct prompt, answer, schedule row, and review-log stream.

## Inputs / context
- `src/czech_vocab/services/study_service.py`
- `src/czech_vocab/web/routes.py`
- `src/czech_vocab/web/templates/home.html`
- `src/czech_vocab/web/templates/review.html`
- `tests/test_study_service.py`
- `tests/test_review_ui.py`
- `tests/test_dashboard_and_acceptance.py`

## Implementation notes
- Add shared direction parsing with `cz_to_ru` default.
- Pass direction through `/`, `/review`, grade, and undo flows.
- Use Czech as prompt for `cz_to_ru` and Russian as prompt for `ru_to_cz`.
- Keep queue rules unchanged except that they now work per direction.
- Scope undo to both deck and direction.

## Tests
- Study-service tests for per-direction queue isolation and grading.
- Review UI tests for reverse prompt/answer rendering and direction-preserving redirects.
- Dashboard route coverage for the new start-review selector.

## Done when
- A review session can run in either direction.
- Reverse reviews update only reverse schedule/history.
- Undo only applies within the same direction.

## Suggested commit message
feat: add reverse review study flow
