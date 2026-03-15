# Project Map

## 1. Purpose of this map

- This file is the fast orientation layer for future agent work.
- It summarizes the verified runtime, data, and flow relationships so later tasks can start from the right source files instead of rediscovering the repo.
- Unless noted otherwise, statements below are verified from code and tests.

## 2. Project snapshot

- The app is a single-user Flask + Jinja vocabulary trainer for Czech words with FSRS scheduling and SQLite persistence.
- Current MVP scope:
  - CSV import by header names, with preview-before-confirm
  - multi-deck card storage
  - deck-scoped review with FSRS scheduler grades `Again`, `Hard`, `Good`, `Easy`
  - undo for the last review answer
  - cards list/search/filter/edit
  - 30-day stats page
  - settings for global defaults and per-deck review limits
- Major implemented areas:
  - server-rendered UI shell and pages
  - SQLite schema bootstrap and seed defaults
  - FSRS adapter around the `fsrs` package
  - deck-aware review queue rules
  - import preview persistence
  - runtime deck membership now resolved through `deck_cards` joins rather than `cards.deck_id`
- Major missing or partial areas:
  - global-base schema refactor has started: `cards` are now schema-level global rows with `deck_cards` links, but most repositories/services still assume the older deck-owned access pattern and are scheduled to be migrated next
  - no optimizer or FSRS parameter fitting
  - no auth or multi-user support
  - no delete flows for cards/decks
  - no API or background jobs
  - no migration framework; schema changes are handled inside bootstrap
  - no manual CSV header-mapping UI

## 3. Repository structure

- [`src/czech_vocab/web`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web)
  - Flask app factory, all routes, Jinja templates, CSS, and small JS enhancements.
- [`src/czech_vocab/services`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services)
  - application-layer orchestration for dashboard, import, review, cards, stats, and settings.
- [`src/czech_vocab/repositories`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/repositories)
  - SQLite schema bootstrap, schema migrations, and repositories for cards, decks, settings, and import previews.
- [`src/czech_vocab/domain`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/domain)
  - FSRS scheduler adapter.
- [`src/czech_vocab/importers`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/importers)
  - CSV parsing and header normalization.
- [`tests`](/home/egrebnev/Dev/ai/FSRS/tests)
  - pytest coverage for repositories, services, route behavior, and main UI flows.
- [`docs/FSRS_SCOPE.md`](/home/egrebnev/Dev/ai/FSRS/docs/FSRS_SCOPE.md)
  - MVP scope contract.
- [`README.md`](/home/egrebnev/Dev/ai/FSRS/README.md)
  - developer-facing setup and usage docs.
- [`pyproject.toml`](/home/egrebnev/Dev/ai/FSRS/pyproject.toml)
  - Python/dependency/tool configuration.

## 4. Runtime architecture

- App entrypoint:
  - verified Flask factory: [`create_app()`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/app.py)
  - verified CLI target: `czech_vocab.web.app:create_app`
- App startup path:
  1. `create_app()` builds the Flask app.
  2. It creates the instance directory.
  3. It configures `DATABASE_PATH` and `SECRET_KEY`.
  4. It runs [`initialize_database()`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/repositories/schema.py).
  5. It registers a Jinja filter for review empty-state messaging.
  6. It registers the single blueprint `main_bp`.
- Configuration sources:
  - defaults live in [`web/app.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/app.py)
  - test overrides are passed through `test_config`
  - no `.env` or separate config module was found
- Request handling begins in:
  - [`src/czech_vocab/web/routes.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/routes.py)
- Static/template runtime:
  - base layout: [`base.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/base.html)
  - global CSS: [`styles.css`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/styles.css)
  - progressive enhancement JS: [`app.js`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/app.js)

## 5. Route map

- `/`
  - methods: `GET`
  - handler: `home()` in [`routes.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/routes.py)
  - template: [`home.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/home.html)
  - service: [`DashboardService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/dashboard_service.py)
  - DB access: `cards`, `decks`, `review_logs`
  - inputs: none

- `/favicon.ico`
  - methods: `GET`
  - handler: `favicon()`
  - behavior: redirects to static `favicon.svg`

- `/import`
  - methods: `GET`
  - handler: `import_page()`
  - template: [`import.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/import.html)
  - service used indirectly via `_render_import_page()`: [`DeckSettingsService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/deck_settings_service.py)
  - DB access: `decks`

- `/import/preview`
  - methods: `POST`
  - handler: `preview_import()`
  - template: `import.html`
  - service: [`ImportService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/import_service.py)
  - repositories: `DeckRepository`, `CardRepository`, `ImportPreviewRepository`
  - inputs: `csv_file`, `deck_id`, `new_deck_name`
  - DB access: `decks`, `cards`, `deck_cards`, `import_previews`

- `/import/confirm`
  - methods: `POST`
  - handler: `confirm_import()`
  - template: `import.html`
  - service: `ImportService`
  - inputs: `preview_token`
  - DB access: `import_previews`, `decks`, `cards`, `deck_cards`

- `/review`
  - methods: `GET`
  - handler: `review_page()`
  - template: [`review.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/review.html)
  - services: [`StudyService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/study_service.py), `DeckSettingsService`
  - inputs: query param `deck`
  - DB access: `decks`, `cards`, `deck_cards`, `review_logs`

- `/review/<card_id>/grade`
  - methods: `POST`
  - handler: `submit_review()`
  - service: `StudyService`
  - inputs: form `rating`, `deck`
  - DB access: `cards`, `deck_cards`, `review_logs`
  - side effect: writes session key `review_undo`

- `/review/undo`
  - methods: `POST`
  - handler: `undo_review()`
  - service: `StudyService`
  - inputs: form `deck`
  - DB access: `cards`, `review_logs`
  - side effect: reads/clears session key `review_undo`

- `/cards`
  - methods: `GET`
  - handler: `cards_page()`
  - template: [`cards.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/cards.html)
  - service: [`CardCatalogService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/card_catalog_service.py)
  - inputs: `deck`, `status`, `search_in`, `q`, `page`
  - DB access: `cards`, `deck_cards`, `decks`, `review_logs`

- `/cards/<card_id>/edit`
  - methods: `GET`, `POST`
  - handlers: `edit_card_page()`, `update_card_page()`
  - template: [`card_edit.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/card_edit.html)
  - service: [`CardEditService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/card_edit_service.py)
  - inputs: `deck_id`, `lemma`, `translation`, `notes`, `metadata_key_*`, `metadata_value_*`
  - DB access: `cards`, `deck_cards`, `decks`

- `/stats`
  - methods: `GET`
  - handler: `stats_page()`
  - template: [`stats.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/stats.html)
  - service: [`StatsService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/stats_service.py)
  - inputs: query param `deck`
  - DB access: `cards`, `deck_cards`, `decks`, `review_logs`, `app_settings`

- `/settings`
  - methods: `GET`, `POST`
  - handlers: `settings_page()`, `update_settings_page()`
  - template: [`settings.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/settings.html)
  - service: [`SettingsPageService`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/settings_page_service.py)
  - inputs: global defaults plus `deck_<id>_desired_retention` and `deck_<id>_daily_new_limit`
  - DB access: `app_settings`, `decks`

## 6. Database map

- `decks`
  - role: deck catalog and per-deck review defaults
  - important fields: `name`, `desired_retention`, `daily_new_limit`
  - written by: `DeckRepository`, `DeckSettingsService`, `SettingsPageService`
  - read by: dashboard, import, review, cards, stats, settings

- `app_settings`
  - role: global defaults for new decks, stats “all decks” retention display, and deck-population defaults
  - important fields: `default_desired_retention`, `default_daily_new_limit`, `default_target_deck_card_count`
  - written by: `AppSettingsRepository`, `DeckSettingsService`, `SettingsPageService`
  - read by: settings and deck creation flows

- `cards`
  - role: persistent global card content + scheduling state
  - important fields: `lemma_key`, `identity_key`, `lemma`, `translation`, `notes`, `metadata_json`, `fsrs_state_json`, `due_at`, `last_review_at`
  - uniqueness: `lemma_key`
  - written by: import, review scheduling updates, card edit
  - read by: review queue, dashboard, cards list, stats

- `deck_cards`
  - role: active assignment link between a global card and one deck
  - important fields: `card_id`, `deck_id`, `created_at`
  - relations: `card_id -> cards.id`, `deck_id -> decks.id`
  - uniqueness: `card_id` is unique so a card can belong to at most one active deck
  - written by: schema migration, card creation, import confirm, and card edit reassignment
  - read by: review queue, dashboard, cards list, stats, and duplicate lookup by deck

- `deck_population_drafts`
  - role: server-side draft state for manual deck population flows
  - important fields: `token`, `flow_type`, `deck_id`, `deck_name`, `requested_count`, `mode`, `selected_card_ids_json`
  - written by: no runtime writer yet; introduced by schema as a dependency for planned manual selection flows

- `review_logs`
  - role: immutable review history with soft undo marker
  - important fields: `card_id`, `rating`, `reviewed_at`, `undone_at`
  - relation: `card_id -> cards.id`
  - written by: `StudyService.submit_review()`, `StudyService.undo_review()`
  - read by: review undo checks, dashboard recent activity, cards learned-state, stats

- `import_previews`
  - role: persisted preview state between upload and confirm
  - important fields: `token`, `deck_name`, `rows_json`, `rejected_messages_json`, `duplicate_count`, `imported_at`
  - written by: `ImportPreviewRepository.create_preview()`
  - consumed/deleted by: `ImportService.confirm_preview()`

- Schema ownership:
  - source of truth: [`schema.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/repositories/schema.py) and [`schema_migrations.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/repositories/schema_migrations.py)
  - there is no separate migration tool
  - bootstrap now includes additive migrations for `review_logs.undone_at` and `app_settings.default_target_deck_card_count`
  - bootstrap also includes an ad hoc rebuild from legacy deck-owned `cards` rows to global `cards` plus `deck_cards`, with fail-fast Czech-duplicate detection

## 7. Domain and service relations

- Domain objects
  - [`FsrsScheduler`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/domain/fsrs_scheduler.py) wraps `fsrs.Scheduler`
  - it owns rating parsing, default state creation, and review application

- Repository ownership
  - `CardRepository`: global card rows + review logs
  - `DeckCardRepository`: deck membership writes and deck-scoped card queries
  - `DeckRepository`: decks
  - `AppSettingsRepository`: app settings
  - `ImportPreviewRepository`: import previews
  - [`records.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/repositories/records.py): dataclasses, JSON/datetime serialization, identity key building, Czech `lemma_key` normalization

- Service relations
  - `ImportService`
    - calls CSV parser
    - resolves deck via `DeckSettingsService`
    - checks duplicates via `CardRepository` deck lookups
    - stores previews via `ImportPreviewRepository`
    - initializes FSRS state via `FsrsScheduler`
  - `StudyService`
    - reads deck defaults via `DeckSettingsService`
    - selects queue via `CardRepository`
    - applies review via `FsrsScheduler`
    - writes `cards` and `review_logs`
  - `DashboardService`
    - reads aggregate card/deck/review data
    - currently uses direct SQL through `CardRepository.connect()` with `deck_cards` joins
  - `CardCatalogService`
    - builds filtered list view
    - currently uses direct SQL through `CardRepository.connect()` with `deck_cards` joins
  - `CardEditService`
    - validates editable fields
    - normalizes metadata keys using CSV header normalization
    - writes shared card content through `CardRepository` and reassigns deck membership through the repository layer
  - `StatsService`
    - builds 30-day metrics
    - mixes `CardRepository.connect()` SQL with `DeckRepository`/`AppSettingsRepository`, now through `deck_cards` joins
  - `DeckSettingsService`
    - thin wrapper around deck/app-settings repositories
    - creates new decks from app defaults
  - `SettingsPageService`
    - prepares settings form data
    - validates numeric inputs
    - writes app and deck settings in one SQLite transaction

- Review state transitions
  - queue selection: `StudyService.get_queue_state()`
  - schedule mutation: `StudyService.submit_review()`
  - undo mutation: `StudyService.undo_review()`

- Deck logic
  - default deck seeding and lookup: `schema.py`, `DeckRepository`
  - import deck resolution: `DeckSettingsService.resolve_import_deck()`
  - selected review deck: route-level `_resolve_deck()` in `routes.py`

- Settings logic
  - persistence: `settings_repository.py`, `deck_repository.py`
  - page assembly + validation: `settings_page_service.py`

## 8. End-to-end flows

- App startup
  1. Flask CLI loads `czech_vocab.web.app:create_app`
  2. `create_app()` configures app and DB path
  3. `initialize_database()` creates/seeds tables
  4. `main_bp` routes start handling requests
  - tables affected: `decks`, `app_settings`, optionally `cards` migration, `review_logs`
  - result: ready app with default deck/settings

- CSV import flow
  1. `GET /import` renders form and deck options
  2. `POST /import/preview` reads upload bytes
  3. `ImportService` parses CSV and computes duplicates/rejections
  4. preview persists in `import_previews`
  5. `POST /import/confirm` resolves/creates deck and inserts new cards
  6. each imported card gets default FSRS state
  7. preview token is deleted
  - modules: `routes.py` -> `ImportService` -> CSV parser / repositories / `FsrsScheduler`
  - tables affected: `import_previews`, `decks`, `cards`
  - result: new cards inserted, duplicates skipped

- Review flow
  1. `GET /review?deck=<id>` resolves deck
  2. `StudyService.get_queue_state()` returns due learned card first, otherwise new card, otherwise empty reason
  3. `review.html` renders Czech prompt only
  4. client JS reveals answer and enables grade buttons
  5. `POST /review/<id>/grade` calls `StudyService.submit_review()`
  6. scheduler updates card state and review log
  7. undo snapshot is stored in session
  - tables affected: `cards`, `review_logs`
  - result: next due date/state persisted

- Undo flow
  1. review success leaves `review_undo` in session
  2. `POST /review/undo` reconstructs `UndoReviewSnapshot`
  3. `StudyService.undo_review()` restores prior card state
  4. latest active review log gets `undone_at`
  - tables affected: `cards`, `review_logs`
  - result: last answer becomes ignored by queue/stats logic

- Cards list/search flow
  1. `GET /cards` collects filters from query params
  2. `CardCatalogService.get_page()` loads cards + learned-state flag
  3. service filters in Python and returns paginated view model
  4. template renders single list view
  - tables affected: read-only `cards`, `decks`, `review_logs`
  - result: filtered card catalog

- Card edit flow
  1. `GET /cards/<id>/edit` loads form
  2. `POST /cards/<id>/edit` validates required fields and deck+identity uniqueness
  3. metadata keys normalize through `normalize_header()`
  4. repository updates card content
  - tables affected: `cards`
  - result: updated card, redirect back to cards list

- Stats flow
  1. `GET /stats?deck=<id|all>` selects deck scope
  2. `StatsService` computes due/review counts, success/fail rates, retention text, average interval, and 10 recent daily summary rows
  - tables affected: read-only `cards`, `review_logs`, `decks`, `app_settings`
  - result: 30-day summary page

- Settings flow
  1. `GET /settings` loads current app + deck settings
  2. `POST /settings` validates string inputs
  3. `SettingsPageService` writes app settings and all deck settings in one DB transaction
  - tables affected: `app_settings`, `decks`
  - result: persisted review defaults

## 9. Template/UI map

- Base layout
  - source: [`base.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/base.html)
  - owns: page title blocks, primary nav, flash stack, skip link

- Major page templates
  - dashboard: `home.html`
  - import: `import.html`
  - review: `review.html`
  - cards list: `cards.html`
  - card edit: `card_edit.html`
  - stats: `stats.html`
  - settings: `settings.html`

- Reusable partials/components
  - no separate Jinja partial files were found
  - reuse is done through base template blocks and shared CSS classes
  - [`placeholder.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/placeholder.html) exists but no current route references it

- Static modules
  - CSS: [`styles.css`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/styles.css)
  - JS: [`app.js`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/app.js)
  - favicon: [`favicon.svg`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/favicon.svg)

- Server-rendered vs JS-enhanced
  - server-rendered: all pages, all data views, all forms
  - JS-enhanced only:
    - mobile nav toggle
    - review answer reveal
    - review keyboard grades
    - `/` shortcut for cards search
    - busy-state submit protection/labels

## 10. Test map

- App/bootstrap and shell
  - [`test_package.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_package.py)
  - [`test_web_shell.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_web_shell.py)

- Import/parser
  - [`test_csv_parser.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_csv_parser.py)
  - [`test_import_service.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_import_service.py)
  - [`test_import_flow.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_import_flow.py)

- FSRS and review behavior
  - [`test_fsrs_scheduler.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_fsrs_scheduler.py)
  - [`test_study_service.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_study_service.py)
  - [`test_review_ui.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_review_ui.py)

- Persistence and decks/settings
  - [`test_card_repository.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_card_repository.py)
  - [`test_deck_settings_service.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_deck_settings_service.py)
  - [`test_settings_service.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_settings_service.py)
  - [`test_settings_page.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_settings_page.py)

- Catalog/edit/stats/dashboard
  - [`test_card_catalog.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_card_catalog.py)
  - [`test_card_edit_service.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_card_edit_service.py)
  - [`test_card_edit_page.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_card_edit_page.py)
  - [`test_stats_service.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_stats_service.py)
  - [`test_stats_page.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_stats_page.py)
  - [`test_dashboard_and_acceptance.py`](/home/egrebnev/Dev/ai/FSRS/tests/test_dashboard_and_acceptance.py)

- Obvious test gaps
  - no separate tests for the global JS module itself; keyboard/busy behavior is mostly covered through route/UI expectations and prior MCP/browser checks, not unit tests
  - no explicit tests for production config or deployment behavior

## 11. Source-of-truth index

- Routes: [`src/czech_vocab/web/routes.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/routes.py)
- App/bootstrap: [`src/czech_vocab/web/app.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/app.py)
- DB/schema: [`src/czech_vocab/repositories/schema.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/repositories/schema.py)
- FSRS logic: [`src/czech_vocab/domain/fsrs_scheduler.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/domain/fsrs_scheduler.py)
- Imports: [`src/czech_vocab/services/import_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/import_service.py), [`src/czech_vocab/importers/csv_parser.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/importers/csv_parser.py)
- Review behavior: [`src/czech_vocab/services/study_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/study_service.py), [`src/czech_vocab/web/templates/review.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/review.html), [`src/czech_vocab/web/static/app.js`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/app.js)
- Cards editing: [`src/czech_vocab/services/card_edit_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/card_edit_service.py), [`src/czech_vocab/web/templates/card_edit.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/card_edit.html)
- Settings: [`src/czech_vocab/services/settings_page_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/settings_page_service.py)
- Stats: [`src/czech_vocab/services/stats_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/stats_service.py)
- Templates/layout: [`src/czech_vocab/web/templates/base.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/base.html)
- Tests: [`tests`](/home/egrebnev/Dev/ai/FSRS/tests)

## 12. Known risks / architectural pressure points

- Direct SQL in services
  - dashboard, cards catalog, and stats assemble SQL in service modules via `CardRepository.connect()`. Read logic is not consistently encapsulated in repositories.

- Schema evolution path
  - there is no migration tool. Future schema changes must be handled carefully inside `initialize_database()`.

- Deck selection logic is split
  - routes resolve current deck for review pages, while queue rules live in `StudyService`. Changes to default/selected deck behavior can drift if updated in only one place.

- Import preview persistence is DB-backed
  - preview confirmation depends on `import_previews` tokens and stored serialized rows; schema changes there can break import confirmation.

- Undo relies on session + latest active log
  - the undo contract depends on session state matching the latest non-undone `review_logs` row for that card.

- Filtering strategy in cards catalog
  - catalog filtering is partly done in Python after loading rows; performance assumptions are acceptable now but could become pressure points with large datasets.

## 13. Fast navigation checklist for future agents

- If the task is about routes or form payloads, inspect [`routes.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/routes.py) first.
- If the task is about DB writes or table shape, inspect [`schema.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/repositories/schema.py) and the relevant repository module first.
- If the task is about scheduling or grades, inspect [`fsrs_scheduler.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/domain/fsrs_scheduler.py) and [`study_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/study_service.py) first.
- If the task is about CSV import behavior, inspect [`csv_parser.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/importers/csv_parser.py) and [`import_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/import_service.py) first.
- If the task is about review UI behavior, inspect [`review.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/review.html) and [`app.js`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/app.js) first.
- If the task is about cards list/search, inspect [`card_catalog_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/card_catalog_service.py) first.
- If the task is about card editing, inspect [`card_edit_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/card_edit_service.py) and [`card_edit.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/card_edit.html) first.
- If the task is about settings or deck defaults, inspect [`settings_page_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/settings_page_service.py) and [`deck_settings_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/deck_settings_service.py) first.
- If the task is about stats, inspect [`stats_service.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/services/stats_service.py) first.
- If the task is about layout or styling, inspect [`base.html`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/templates/base.html) and [`styles.css`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/styles.css) first.
- If the task is about test expectations, inspect the matching `tests/test_*.py` file before changing code.
