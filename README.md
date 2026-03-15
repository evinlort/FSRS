# Czech Vocabulary FSRS

## Project overview

This repository contains a small Flask web app for learning Czech vocabulary from CSV files with FSRS-based review scheduling. It is a server-rendered, single-user MVP with SQLite persistence, multi-deck support, deck-scoped review, CSV import preview, card editing, simple 30-day stats, and review/settings pages in Russian.

## MVP scope

The implemented MVP covers:

- importing Czech vocabulary from CSV by header names
- storing a global card base, deck links, settings, and review history in SQLite
- reviewing one selected deck at a time with `Again`, `Hard`, `Good`, and `Easy`
- scheduling the next review with FSRS
- creating decks from the global available pool
- adding cards to existing decks from the same global pool
- browsing, filtering, searching, and editing imported cards
- showing simple dashboard and 30-day stats views

## Implemented features

- Dashboard at `/` with deck-aware start-review action, due counts, deck summaries, recent activity, and navigation to import, stats, and cards
- Multi-deck support throughout the UI
- CSV import at `/import` with preview-before-confirm, automatic header mapping, duplicate skipping, and import into the global unassigned card base
- Header-based CSV parsing with aliases for Czech, Russian, and notes columns
- Safe handling of extra CSV columns as stored metadata
- Deck creation at `/decks/new` with `random`, `manual`, and `mixed` population modes
- Add-to-deck flow at `/decks/<id>/add` with the same `random`, `manual`, and `mixed` modes
- Manual deck population through a dedicated selection page with Czech/Russian search and checkbox selection
- Global default deck target count in `/settings`, used as the default requested count in create/add deck flows
- Deck-scoped review at `/review?deck=<id>` with reveal-on-demand answers and hidden extra details
- Review shortcuts in the browser: `Space` to reveal, `1`/`2`/`3`/`4` for `Again`/`Hard`/`Good`/`Easy`, `/` to focus cards search
- Undo for the last review answer
- Card catalog at `/cards` with deck filter, status filter, Czech/Russian search scope, pagination, and card editing
- Card edit page at `/cards/<card_id>/edit` for lemma, translation, notes, deck, and metadata
- Stats page at `/stats` with a 30-day deck-filtered summary
- Settings page at `/settings` for global defaults, including default deck target count, and per-deck `desired_retention` / daily new-card limits
- Automatic SQLite schema creation on app startup
- Mobile-first shared shell with collapsible navigation, skip link, focus styles, and responsive layout rules

## Not implemented / current limitations

- No FSRS optimizer or parameter fitting
- No user accounts, authentication, or multi-user support
- No delete flows for cards or decks
- No manual CSV column-mapping UI
- No metadata search beyond lemma, translation, and notes
- No background jobs, sync, API, or deployment setup
- No migration tool; schema is created directly from SQL on startup
- No dark mode or full i18n framework
- Stats are intentionally simple; there are no charts or advanced analytics
- Duplicate prevention is intentionally strict: the global base treats normalized Czech lemma as unique, even if Russian translation differs

## Tech stack

- Python `3.14`
- Flask `3.1`
- Jinja templates
- SQLite via the Python standard library
- `fsrs` `6.3.x`
- pytest
- Ruff
- `uv` with [`uv.lock`](/home/egrebnev/Dev/ai/FSRS/uv.lock) is present in the repo, but `uv` commands could not be validated in this environment

## Project structure

```text
src/czech_vocab/
  domain/         FSRS adapter
  importers/      CSV parsing
  repositories/   SQLite schema and persistence
  services/       dashboard, import, deck population, study, stats, settings, catalog, edit logic
  web/            Flask app factory, routes, templates, static assets
tests/            pytest coverage for behavior and UI routes
docs/             MVP scope notes
PLANS/            implementation plans and completed step checklist
```

## Requirements

- Bash-compatible shell on Linux
- Python `3.14.x`
- SQLite support in the Python stdlib build
- A working Flask and pytest environment
- No required `.env` file or application config file was found

Verified repository facts:

- [`pyproject.toml`](/home/egrebnev/Dev/ai/FSRS/pyproject.toml) requires `==3.14.*`
- the app factory is `czech_vocab.web.app:create_app`
- the default SQLite file is created at [`src/instance/czech_vocab.sqlite3`](/home/egrebnev/Dev/ai/FSRS/src/instance/czech_vocab.sqlite3)

## Quick start on Linux (Ubuntu 24.04+)

Verified local run path in this workspace:

```bash
.venv/bin/flask --app czech_vocab.web.app:create_app run
```

Verified local test command:

```bash
.venv/bin/pytest
```

Verified local lint command:

```bash
.venv/bin/python -m ruff check src tests
```

Practical fresh-clone path for Ubuntu, not verified here because the local `uv` binary is broken:

1. Install or provide Python `3.14`.
2. Install `uv`.
3. Sync dependencies.
4. Start the Flask dev server.

Suggested `uv` commands, unverified in this environment:

```bash
uv sync --dev
uv run flask --app czech_vocab.web.app:create_app run
uv run pytest
```

The local `uv` binary failed with a `snap-confine` permission error, so prefer a non-snap `uv` install if you hit the same issue on Ubuntu.

## Setup

No environment variables are required for the default local run. The app creates its instance directory and SQLite database automatically on startup.

The repository includes:

- [`uv.lock`](/home/egrebnev/Dev/ai/FSRS/uv.lock)

The repository does not include:

- `.env`
- `.env.example`
- Docker files
- deployment manifests

Dependency resolution is driven from [`pyproject.toml`](/home/egrebnev/Dev/ai/FSRS/pyproject.toml) and [`uv.lock`](/home/egrebnev/Dev/ai/FSRS/uv.lock).

## Execution command

Primary verified command:

```bash
.venv/bin/flask --app czech_vocab.web.app:create_app run
```

Verified variant with an explicit port:

```bash
.venv/bin/flask --app czech_vocab.web.app:create_app run --port 5122
```

Unverified `uv`-based equivalent:

```bash
uv run flask --app czech_vocab.web.app:create_app run
```

Unverified debug variant:

```bash
.venv/bin/flask --app czech_vocab.web.app:create_app run --debug
```

`--debug` was not revalidated during this update.

## Running the application

After starting the server, open `http://127.0.0.1:5000`.

Verified user-facing routes from the Flask CLI:

- `GET /`
- `GET /import`
- `POST /import/preview`
- `POST /import/confirm`
- `GET /decks/new`
- `POST /decks/new`
- `GET /decks/<deck_id>/add`
- `POST /decks/<deck_id>/add`
- `GET /deck-drafts/<token>/select`
- `POST /deck-drafts/<token>/select`
- `GET /review`
- `POST /review/<card_id>/grade`
- `POST /review/undo`
- `GET /cards`
- `GET /cards/<card_id>/edit`
- `POST /cards/<card_id>/edit`
- `GET /stats`
- `GET /settings`
- `POST /settings`

On first start, the app creates the SQLite database in [`src/instance`](/home/egrebnev/Dev/ai/FSRS/src/instance).

## Main UI pages and flows

- Dashboard: choose a deck, start review, inspect due counts, recent activity, deck summaries, and quick links.
- Import: upload CSV into the global base, review the preview, then confirm the import.
- Create deck: open `/decks/new`, choose a deck name, pick `random`, `manual`, or `mixed`, optionally override the requested count, and optionally save that count as the new global default.
- Add to deck: open `/decks/<id>/add` from the dashboard, use the same `random`, `manual`, or `mixed` modes, and return to the dashboard with success feedback.
- Manual selection: use `/deck-drafts/<token>/select` to search the available pool by Czech or Russian and pick cards with checkboxes.
- Review: study one deck at a time; due learned cards are served before new cards, and deck daily new-card limits are respected.
- Cards: browse one list view with deck/status filters and Czech/Russian search.
- Card edit: change deck, Czech word, Russian translation, notes, and metadata.
- Stats: see a 30-day summary for one deck or all decks.
- Settings: edit global defaults, including default deck target count, plus per-deck retention and daily new-card limits.

## Decks and card assignment rules

- `cards` is the global word base. Deck membership is stored separately through `deck_cards`.
- Decks link to existing cards; they do not copy card content.
- A card can belong to at most one active deck at a time because `deck_cards.card_id` is unique.
- “Available cards” in deck creation and add-to-deck flows means global cards that are not currently linked to any deck.
- Duplicate prevention in the global base uses normalized Czech lemma only (`lemma_key`), even if translations differ.
- Editing a card updates the shared global card row, so the change is visible wherever that card is linked.

## Deck creation and population flows

- Default requested count comes from the global setting `default_target_deck_card_count`, which starts at `20`.
- The create and add flows both let the user override that count per request.
- Both flows also expose a checkbox to save the entered count back to the global setting.
- `random` mode fills from the available pool only.
- `manual` mode lets the user pick up to the requested count on a dedicated selection page.
- `mixed` mode keeps the manually selected cards and fills the remaining slots randomly from the still-available pool.
- If fewer available cards exist than requested, the app creates or fills the deck with the available number.
- Manual selection with fewer than the requested count is allowed; the selection page shows a warning instead of blocking the flow.
- Successful create/add flows redirect back to the dashboard with a success flash.

## Running tests

Verified command:

```bash
.venv/bin/pytest
```

This repository configures pytest through [`pyproject.toml`](/home/egrebnev/Dev/ai/FSRS/pyproject.toml), with `tests/` as the test root.

Verified additional check:

```bash
.venv/bin/python -m ruff check src tests
```

## CSV import format

The importer reads CSV as UTF-8 with BOM support (`utf-8-sig`) and parses rows by header names, not by column position.

Required logical fields:

- Czech lemma or word
- Russian translation

Supported header aliases:

- Czech: `lemma_cs`, `czech`, `czech_word`, `word_cs`, `lemma`, `word`
- Russian: `translation_ru`, `russian`, `translation`, `ru_translation`
- Notes: `notes`, `note`, `comment`, `comments`

Behavior:

- import is preview-before-confirm
- imported cards go into the global unassigned base
- missing required headers block confirmation
- missing required values reject only the affected row
- duplicates are skipped globally by normalized Czech lemma
- unknown columns are stored as metadata
- metadata keys are normalized to lowercase with spaces and hyphens converted to `_`

Example:

```csv
lemma_cs,translation_ru,notes,level,topic
kniha,книга,common noun,A1,reading
vlak,поезд,transport,A1,travel
```

## Keyboard shortcuts

Verified custom browser shortcuts from [`app.js`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/static/app.js):

- `Space` reveals the answer on the review page
- `1` / `2` / `3` / `4` submit `Again` / `Hard` / `Good` / `Easy` after reveal
- `/` focuses the cards search input when a form field is not already focused

The settings page also documents `Enter` as the normal confirm action when the relevant button is focused, but there is no separate custom `Enter` handler in `app.js`.

## FSRS scope in this project

The app implements only the scheduler portion of FSRS.

Verified behavior from code and tests:

- default `desired_retention` is `0.90`
- supported ratings are `Again`, `Hard`, `Good`, and `Easy`
- card state is serialized into SQLite
- review history is stored persistently in `review_logs`
- review queue is deck-scoped and serves due learned cards before new cards
- per-deck daily new-card limits are enforced

Explicitly out of scope in the current MVP:

- optimizer fitting from review history
- advanced analytics
- multi-user support
- background jobs
- device synchronization

## Development notes

- The Flask app is created in [`src/czech_vocab/web/app.py`](/home/egrebnev/Dev/ai/FSRS/src/czech_vocab/web/app.py).
- Business logic lives in service and repository modules rather than a monolithic `app.py`.
- The default instance path resolves to [`src/instance`](/home/egrebnev/Dev/ai/FSRS/src/instance), not a top-level `instance/` directory.
- Deck population flows are server-rendered and draft-backed in SQLite rather than stored in browser session state.
- Review, import, card edit, and settings forms expose simple busy-submit states in the server-rendered UI.
- The shared shell is mobile-first: it has a viewport meta tag, a collapsible mobile nav, stacked controls on small screens, and wider multi-column layouts from `760px` upward.
- Tests use temporary SQLite databases and Flask test clients rather than a running server.

## Troubleshooting

- `uv` fails immediately with `snap-confine` permission errors:
  Use a non-snap `uv` install. The installed `uv` binary in this environment was not usable.
- The app starts but the browser shows missing icons:
  The app serves a built-in SVG favicon via `/favicon.ico` and `/static/favicon.svg` in the current repo state.
- The database is not where you expected:
  Check [`src/instance/czech_vocab.sqlite3`](/home/egrebnev/Dev/ai/FSRS/src/instance/czech_vocab.sqlite3). That is the default path from the current app factory.
- Import rejects rows:
  Check header names and ensure the CSV is UTF-8 encoded and each imported row has both Czech and Russian values.
- You cannot find imported words in review immediately:
  Imported words stay unassigned in the global base until you create a deck or add cards to an existing deck.
- Create/add deck pages show fewer cards than expected:
  Only cards not linked to any active deck are available for selection or random fill.
- Review says there is nothing due:
  Check the selected deck and its daily new-card limit in `/settings`.

## Roadmap or next possible improvements

- Verify the `uv` workflow end to end in this environment
- Add manual CSV mapping when source headers drift beyond the current alias list
- Add richer review analytics and card-level history views
- Add migrations instead of startup-only schema creation
- Make the database path configurable through environment variables or config
- Add FSRS optimizer support once enough review history exists
- Add delete/archive flows and stronger admin/data-maintenance tools if the MVP grows
- Revisit the Czech-only duplicate rule if the dataset needs legitimate same-lemma variants
