import sqlite3
from pathlib import Path

from czech_vocab.repositories.records import serialize_datetime, utc_now

DEFAULT_DESIRED_RETENTION = 0.90
DEFAULT_DAILY_NEW_LIMIT = 20
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

CREATE INDEX IF NOT EXISTS idx_cards_due_at ON cards (due_at, id);
"""


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript(BASE_SCHEMA_SQL)
        _seed_defaults(connection)
        _ensure_review_logs_schema(connection)
        if _cards_need_migration(connection):
            _migrate_cards(connection)
        else:
            connection.executescript(CARDS_SCHEMA_SQL)
        connection.execute("PRAGMA foreign_keys = ON")


def _seed_defaults(connection: sqlite3.Connection) -> None:
    timestamp = serialize_datetime(utc_now())
    connection.execute(
        """
        INSERT OR IGNORE INTO app_settings (
            id,
            default_desired_retention,
            default_daily_new_limit,
            created_at,
            updated_at
        ) VALUES (1, ?, ?, ?, ?)
        """,
        (DEFAULT_DESIRED_RETENTION, DEFAULT_DAILY_NEW_LIMIT, timestamp, timestamp),
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


def _cards_need_migration(connection: sqlite3.Connection) -> bool:
    if not _table_exists(connection, "cards"):
        return False
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(cards)").fetchall()}
    return "deck_id" not in columns


def _ensure_review_logs_schema(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "review_logs"):
        return
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(review_logs)")}
    if "undone_at" not in columns:
        connection.execute("ALTER TABLE review_logs ADD COLUMN undone_at TEXT")


def _migrate_cards(connection: sqlite3.Connection) -> None:
    default_deck_id = connection.execute(
        "SELECT id FROM decks WHERE name = ?",
        (DEFAULT_DECK_NAME,),
    ).fetchone()["id"]
    connection.executescript(
        """
        DROP TABLE IF EXISTS cards_new;
        CREATE TABLE cards_new (
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
        """,
    )
    connection.execute(
        """
        INSERT INTO cards_new (
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
        )
        SELECT
            id,
            ?,
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
        FROM cards
        """,
        (default_deck_id,),
    )
    connection.executescript(
        """
        DROP TABLE cards;
        ALTER TABLE cards_new RENAME TO cards;
        CREATE INDEX IF NOT EXISTS idx_cards_due_at ON cards (due_at, id);
        """,
    )


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None
