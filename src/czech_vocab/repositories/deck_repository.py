import sqlite3
from contextlib import contextmanager
from pathlib import Path

from czech_vocab.repositories.records import DeckRecord, row_to_deck, serialize_datetime, utc_now
from czech_vocab.repositories.schema import DEFAULT_DECK_NAME


class DeckRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_decks(self) -> list[DeckRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM decks ORDER BY id").fetchall()
        return [row_to_deck(row) for row in rows]

    def get_deck_by_id(self, deck_id: int) -> DeckRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
        return row_to_deck(row) if row else None

    def get_deck_by_name(self, name: str) -> DeckRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM decks WHERE name = ?", (name,)).fetchone()
        return row_to_deck(row) if row else None

    def get_default_deck(self) -> DeckRecord:
        deck = self.get_deck_by_name(DEFAULT_DECK_NAME)
        assert deck is not None
        return deck

    def create_deck(
        self,
        *,
        name: str,
        desired_retention: float,
        daily_new_limit: int,
        connection: sqlite3.Connection | None = None,
    ) -> DeckRecord:
        timestamp = serialize_datetime(utc_now())
        with self._use_connection(connection) as active_connection:
            cursor = active_connection.execute(
                """
                INSERT INTO decks (
                    name,
                    desired_retention,
                    daily_new_limit,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (name, desired_retention, daily_new_limit, timestamp, timestamp),
            )
            row = active_connection.execute(
                "SELECT * FROM decks WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        assert row is not None
        return row_to_deck(row)

    def update_settings(
        self,
        *,
        deck_id: int,
        desired_retention: float,
        daily_new_limit: int,
        connection: sqlite3.Connection | None = None,
    ) -> DeckRecord:
        timestamp = serialize_datetime(utc_now())
        with self._use_connection(connection) as active_connection:
            active_connection.execute(
                """
                UPDATE decks
                SET desired_retention = ?, daily_new_limit = ?, updated_at = ?
                WHERE id = ?
                """,
                (desired_retention, daily_new_limit, timestamp, deck_id),
            )
            row = active_connection.execute(
                "SELECT * FROM decks WHERE id = ?",
                (deck_id,),
            ).fetchone()
        assert row is not None
        return row_to_deck(row)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _use_connection(self, connection: sqlite3.Connection | None):
        if connection is not None:
            yield connection
            return
        with self._connect() as active_connection:
            yield active_connection
