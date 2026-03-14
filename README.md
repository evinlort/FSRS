# Czech Vocabulary FSRS

## Project overview

This repository contains a small Flask web app for learning Czech vocabulary from CSV files with FSRS-based review scheduling. It is a server-rendered MVP with SQLite persistence, browser-based CSV import, a due-card review flow, and a searchable card catalog.

## MVP scope

The implemented MVP covers:

- importing Czech vocabulary from CSV by header names
- persisting cards and review history in SQLite
- reviewing due cards with `Again`, `Hard`, `Good`, and `Easy`
- scheduling the next review with FSRS
- browsing and searching imported cards

## Implemented features

- Dashboard at `/` with live total-card and due-card counts
- CSV upload page at `/import`
- Header-based CSV parsing with aliases for Czech, Russian, and notes columns
- Safe handling of extra CSV columns as stored metadata
- Re-import upsert by normalized Czech lemma + Russian translation
- Review page at `/review` with four FSRS grades
- Persistent review log storage in `review_logs`
- Card catalog at `/cards` with case-insensitive search and pagination
- Automatic SQLite schema creation on app startup

## Not implemented / current limitations

- No FSRS optimizer or parameter fitting
- No user accounts, multi-user support, or authentication
- No answer-reveal step; the review page shows Czech, Russian, notes, and metadata together
- No analytics dashboard beyond total and due counts
- No background jobs, sync, or cloud deployment setup
- No migration tool; schema is created directly from SQL on startup
- Search only checks lemma, translation, and notes; extra metadata is displayed but not searchable
- Re-import identity is based on normalized lemma + translation, so changing either creates a new logical card

## Tech stack

- Python `3.14`
- Flask `3.1`
- Jinja templates
- SQLite via the Python standard library
- `fsrs` `6.3.x`
- pytest
- Ruff
- `uv` is the intended package manager, but its use could not be validated in this environment

## Project structure

```text
src/czech_vocab/
  domain/         FSRS adapter
  importers/      CSV parsing
  repositories/   SQLite schema and persistence
  services/       import, study, catalog, dashboard logic
  web/            Flask app factory, routes, templates
tests/            pytest coverage for the implemented behavior
docs/             MVP scope notes
```

## Requirements

- Bash-compatible shell on Linux
- Python `3.14.x`
- SQLite support in the Python stdlib build
- A working Flask and pytest environment
- No required `.env` file or application config file was found

Verified repository facts:

- `pyproject.toml` requires `==3.14.*`
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

The repository does not include:

- `uv.lock`
- `.env`
- `.env.example`
- Docker files
- deployment manifests

That means dependency resolution is driven directly from [`pyproject.toml`](/home/egrebnev/Dev/ai/FSRS/pyproject.toml).

## Execution command

Primary verified command:

```bash
.venv/bin/flask --app czech_vocab.web.app:create_app run
```

Verified variant with an explicit port:

```bash
.venv/bin/flask --app czech_vocab.web.app:create_app run --port 5012
```

Unverified `uv`-based equivalent:

```bash
uv run flask --app czech_vocab.web.app:create_app run
```

Unverified debug variant:

```bash
.venv/bin/flask --app czech_vocab.web.app:create_app run --debug
```

`--debug` could not be validated in this sandbox because Werkzeug's debugger tried to use `/dev/shm` and failed with `PermissionError`.

## Running the application

After starting the server, open `http://127.0.0.1:5000`.

Available routes verified from the Flask CLI:

- `/`
- `/import`
- `/review`
- `/review/<card_id>/grade`
- `/cards`

On first start, the app creates the SQLite database in [`src/instance`](/home/egrebnev/Dev/ai/FSRS/src/instance).

## Running tests

Verified command:

```bash
.venv/bin/pytest
```

This repository configures pytest through [`pyproject.toml`](/home/egrebnev/Dev/ai/FSRS/pyproject.toml), with `tests/` as the test root.

An additional development check is present and was previously used in this repo, but it was not re-run for this README update:

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

- missing required headers fail the whole import
- missing required values reject only the affected row
- unknown columns are stored as metadata
- metadata keys are normalized to lowercase with spaces and hyphens converted to `_`

Example:

```csv
lemma_cs,translation_ru,notes,level,topic
kniha,книга,common noun,A1,reading
vlak,поезд,transport,A1,travel
```

## FSRS scope in this project

The app implements only the scheduler portion of FSRS.

Verified behavior from code and tests:

- default `desired_retention` is `0.90`
- supported ratings are `Again`, `Hard`, `Good`, and `Easy`
- card state is serialized into SQLite
- review history is stored persistently in `review_logs`

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
- Search in the catalog is case-insensitive and matches lemma, translation, and notes.
- Catalog pagination is fixed at 50 cards per page.
- Tests use temporary SQLite databases and Flask test clients rather than a running server.

## Troubleshooting

- `uv` fails immediately with `snap-confine` permission errors:
  Use a non-snap `uv` install. The installed `uv` binary in this environment was not usable.
- `flask run --debug` fails in restricted environments:
  Run without `--debug`. Non-debug `flask run` was verified here.
- The database is not where you expected:
  Check [`src/instance/czech_vocab.sqlite3`](/home/egrebnev/Dev/ai/FSRS/src/instance/czech_vocab.sqlite3). That is the default path from the current app factory.
- Import rejects rows:
  Check header names and ensure the CSV is UTF-8 encoded and each imported row has both Czech and Russian values.

## Roadmap or next possible improvements

- Add a checked-in `uv.lock` and verify the `uv` workflow end to end
- Add a hidden-answer review flow instead of showing translation immediately
- Add migrations instead of startup-only schema creation
- Make the database path configurable through environment variables or config
- Add FSRS optimizer support once enough review history exists
- Add richer review analytics and card-level history views
