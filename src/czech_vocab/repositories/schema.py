import sqlite3
from pathlib import Path

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_key TEXT NOT NULL UNIQUE,
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

CREATE TABLE IF NOT EXISTS review_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    rating TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    review_duration_seconds INTEGER,
    FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_logs_card_id ON review_logs (card_id, reviewed_at);
"""


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA_SQL)
