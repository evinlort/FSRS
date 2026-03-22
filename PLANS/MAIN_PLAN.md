# Deck Creation And Population From Global Base

## Summary
Plan the refactor from deck-owned cards to a united global word base plus deck links, then add deck creation and deck population flows on top of that model.

## Locked decisions
- CSV import becomes global-base import, not direct deck import.
- Duplicate conflicts are enforced by normalized Czech only.
- Available pool means cards with no active deck link.
- A new deck cannot be created empty.
- Default target count comes from global settings and starts at `20`.
- Successful create/add flows return to the dashboard with a success flash.

## Ordered checklist
- [x] [01 Global Base Schema And Migration](./deck_population/01_global_base_schema_and_migration.md)
- [x] [02 Existing Flows On Deck Links](./deck_population/02_existing_flows_on_deck_links.md)
- [x] [03 Import To Global Base](./deck_population/03_import_to_global_base.md)
- [x] [04 Target Count Settings](./deck_population/04_target_count_settings.md)
- [x] [05 Available Pool And Population Service](./deck_population/05_available_pool_and_population_service.md)
- [x] [06 Create Deck With Random Fill](./deck_population/06_create_deck_with_random_fill.md)
- [x] [07 Create Deck With Manual And Mixed Selection](./deck_population/07_create_deck_with_manual_and_mixed_selection.md)
- [x] [08 Add Random Cards To Existing Deck](./deck_population/08_add_random_cards_to_existing_deck.md)
- [x] [09 Add Manual And Mixed Cards To Existing Deck](./deck_population/09_add_manual_and_mixed_cards_to_existing_deck.md)
- [x] [10 Project Map And Regression Coverage](./deck_population/10_project_map_and_regression_coverage.md)
- [x] [11 Create Deck From CSV](./deck_population/11_create_deck_from_csv.md)
- [ ] [12 Randomized Review Queue Order](./deck_population/12_randomized_review_queue_order.md)

## Done when
- The database stores one global card row per Czech lemma and deck membership through links.
- Existing review, cards, stats, settings, and dashboard behavior still works on the new model.
- CSV import fills the global base.
- Users can create decks and add cards to existing decks with random, manual, and mixed modes.
- Relevant pytest coverage exists for schema, services, routes, and edge cases.
- `docs/PROJECT_MAP.md` is updated after implementation.
