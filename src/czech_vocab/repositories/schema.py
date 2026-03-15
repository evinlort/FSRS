import sqlite3
from pathlib import Path

from czech_vocab.repositories.records import serialize_datetime, utc_now
from czech_vocab.repositories.schema_migrations import (
    ensure_app_settings_schema,
    ensure_cards_schema,
    ensure_review_logs_schema,
)

DEFAULT_DESIRED_RETENTION = 0.90
DEFAULT_DAILY_NEW_LIMIT = 20
DEFAULT_TARGET_DECK_CARD_COUNT = 20
DEFAULT_DECK_NAME = "Основная"

BASE_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    desired_retention REAL NOT NULL,
    daily_new_limit INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    default_desired_retention REAL NOT NULL,
    default_daily_new_limit INTEGER NOT NULL,
    default_target_deck_card_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    rating TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    review_duration_seconds INTEGER,
    undone_at TEXT,
    FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_logs_card_id ON review_logs (card_id, reviewed_at);

CREATE TABLE IF NOT EXISTS import_previews (
    token TEXT PRIMARY KEY,
    deck_name TEXT NOT NULL,
    rows_json TEXT NOT NULL,
    rejected_messages_json TEXT NOT NULL,
    duplicate_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

CARDS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma_key TEXT NOT NULL UNIQUE,
    identity_key TEXT NOT NULL,
    lemma TEXT NOT NULL,
    translation TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL,
    fsrs_state_json TEXT NOT NULL,
    due_at TEXT,
    last_review_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cards_due_at ON cards (due_at, id);
"""

LINK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS deck_cards (
    card_id INTEGER NOT NULL UNIQUE,
    deck_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE,
    FOREIGN KEY (deck_id) REFERENCES decks (id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards (deck_id, card_id);

CREATE TABLE IF NOT EXISTS deck_population_drafts (
    token TEXT PRIMARY KEY,
    flow_type TEXT NOT NULL,
    deck_id INTEGER,
    deck_name TEXT,
    requested_count INTEGER NOT NULL,
    mode TEXT NOT NULL,
    save_default_count INTEGER NOT NULL DEFAULT 0,
    selected_card_ids_json TEXT NOT NULL,
    search_in TEXT NOT NULL,
    query_text TEXT NOT NULL,
    page INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (deck_id) REFERENCES decks (id) ON DELETE CASCADE
);
"""


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript(BASE_SCHEMA_SQL)
        ensure_app_settings_schema(connection)
        _seed_defaults(connection)
        ensure_review_logs_schema(connection)
        ensure_cards_schema(
            connection,
            cards_schema_sql=CARDS_SCHEMA_SQL,
            link_schema_sql=LINK_SCHEMA_SQL,
            default_deck_name=DEFAULT_DECK_NAME,
        )
        connection.executescript(LINK_SCHEMA_SQL)
        connection.execute("PRAGMA foreign_keys = ON")


def _seed_defaults(connection: sqlite3.Connection) -> None:
    timestamp = serialize_datetime(utc_now())
    connection.execute(
        """
        INSERT OR IGNORE INTO app_settings (
            id,
            default_desired_retention,
            default_daily_new_limit,
            default_target_deck_card_count,
            created_at,
            updated_at
        ) VALUES (1, ?, ?, ?, ?, ?)
        """,
        (
            DEFAULT_DESIRED_RETENTION,
            DEFAULT_DAILY_NEW_LIMIT,
            DEFAULT_TARGET_DECK_CARD_COUNT,
            timestamp,
            timestamp,
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO decks (
            name,
            desired_retention,
            daily_new_limit,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            DEFAULT_DECK_NAME,
            DEFAULT_DESIRED_RETENTION,
            DEFAULT_DAILY_NEW_LIMIT,
            timestamp,
            timestamp,
        ),
    )
