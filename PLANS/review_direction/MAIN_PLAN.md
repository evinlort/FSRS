# Reverse Review Direction

## Summary
Add Russian-to-Czech review as an explicit second FSRS direction while preserving the current Czech-to-Russian behavior.

## Locked decisions
- Review direction is chosen from the home page start-review form.
- Supported direction values are `cz_to_ru` and `ru_to_cz`.
- Each direction has independent FSRS state and review history.
- Existing review progress becomes `cz_to_ru`.
- `ru_to_cz` starts as a new direction for all existing cards.
- Stats and card catalog stay forward-only for this feature.

## Ordered checklist
- [ ] [01 Directional Review State Schema](./01_directional_review_state_schema.md)
- [ ] [02 Directional Study Flow](./02_directional_study_flow.md)
- [ ] [03 Dashboard Stats Map Regression](./03_dashboard_stats_map_regression.md)

## Done when
- Users can review decks in either direction.
- Each direction schedules independently.
- Existing Czech-to-Russian review history is preserved.
- Dashboard review entry points and counts work with the chosen direction.
- Stats and card catalog still behave correctly for forward review.
- `docs/PROJECT_MAP.md` reflects the final behavior.
