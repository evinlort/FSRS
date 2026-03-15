import sqlite3
from pathlib import Path

import pytest

from czech_vocab.repositories import initialize_database


def test_initialize_database_creates_global_base_tables_and_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "global-base.sqlite3"

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        card_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(cards)").fetchall()
        }
        setting_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(app_settings)").fetchall()
        }
        settings_row = connection.execute(
            """
            SELECT
                default_desired_retention,
                default_daily_new_limit,
                default_target_deck_card_count
            FROM app_settings
            WHERE id = 1
            """
        ).fetchone()

    assert {"cards", "deck_cards", "deck_population_drafts"} <= tables
    assert "deck_id" not in card_columns
    assert "lemma_key" in card_columns
    assert "default_target_deck_card_count" in setting_columns
    assert settings_row == (0.9, 20, 20)


def test_initialize_database_migrates_deck_owned_cards_to_linked_global_cards(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migrate.sqlite3"
    _build_old_style_database(database_path)

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        card_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(cards)").fetchall()
        }
        cards = connection.execute(
            "SELECT id, lemma, translation, lemma_key FROM cards ORDER BY id"
        ).fetchall()
        links = connection.execute(
            "SELECT deck_id, card_id FROM deck_cards ORDER BY deck_id, card_id"
        ).fetchall()
        review_logs = connection.execute(
            "SELECT card_id, rating FROM review_logs ORDER BY id"
        ).fetchall()
        target_count = connection.execute(
            "SELECT default_target_deck_card_count FROM app_settings WHERE id = 1"
        ).fetchone()

    assert "deck_id" not in card_columns
    assert cards == [
        (1, "kniha", "книга", "kniha"),
        (2, "vlak", "поезд", "vlak"),
    ]
    assert links == [(1, 1), (2, 2)]
    assert review_logs == [(1, "Good"), (2, "Again")]
    assert target_count == (20,)


def test_initialize_database_rejects_conflicting_czech_duplicates_during_migration(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "conflict.sqlite3"
    _build_old_style_database(
        database_path,
        cards=[
            (1, 1, "identity-1", "hrad", "замок"),
            (2, 2, "identity-2", "  HRAD  ", "крепость"),
        ],
    )

    with pytest.raises(ValueError, match=r"hrad"):
        initialize_database(database_path)


def _build_old_style_database(
    database_path: Path,
    *,
    cards: list[tuple[int, int, str, str, str]] | None = None,
) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                desired_retention REAL NOT NULL,
                daily_new_limit INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE app_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                default_desired_retention REAL NOT NULL,
                default_daily_new_limit INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                identity_key TEXT NOT NULL,
                lemma TEXT NOT NULL,
                translation TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL,
                fsrs_state_json TEXT NOT NULL,
                due_at TEXT,
                last_review_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (deck_id) REFERENCES decks (id) ON DELETE RESTRICT,
                UNIQUE (deck_id, identity_key)
            );

            CREATE TABLE review_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                rating TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                review_duration_seconds INTEGER,
                FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO decks (
                id,
                name,
                desired_retention,
                daily_new_limit,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "Основная",
                    0.9,
                    20,
                    "2026-03-15T08:00:00+00:00",
                    "2026-03-15T08:00:00+00:00",
                ),
                (
                    2,
                    "Путешествия",
                    0.88,
                    12,
                    "2026-03-15T08:00:00+00:00",
                    "2026-03-15T08:00:00+00:00",
                ),
            ],
        )
        connection.execute(
            """
            INSERT INTO app_settings (
                id,
                default_desired_retention,
                default_daily_new_limit,
                created_at,
                updated_at
            ) VALUES (1, 0.9, 20, '2026-03-15T08:00:00+00:00', '2026-03-15T08:00:00+00:00')
            """
        )
        rows = cards or [
            (1, 1, "identity-1", "kniha", "книга"),
            (2, 2, "identity-2", "vlak", "поезд"),
        ]
        connection.executemany(
            """
            INSERT INTO cards (
                id,
                deck_id,
                identity_key,
                lemma,
                translation,
                notes,
                metadata_json,
                fsrs_state_json,
                due_at,
                last_review_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, '', '{}', '{}', NULL, NULL, ?, ?)
            """,
            [
                (
                    card_id,
                    deck_id,
                    identity_key,
                    lemma,
                    translation,
                    "2026-03-15T08:00:00+00:00",
                    "2026-03-15T08:00:00+00:00",
                )
                for card_id, deck_id, identity_key, lemma, translation in rows
            ],
        )
        connection.executemany(
            """
            INSERT INTO review_logs (
                card_id,
                rating,
                reviewed_at,
                review_duration_seconds
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (1, "Good", "2026-03-15T09:00:00+00:00", 12),
                (2, "Again", "2026-03-15T09:01:00+00:00", 15),
            ],
        )
