import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from czech_vocab.repositories.records import row_to_card, serialize_datetime, utc_now

CARD_SELECT = """
SELECT cards.*, deck_cards.deck_id AS deck_id
FROM deck_cards
JOIN cards ON cards.id = deck_cards.card_id
"""


class DeckCardRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def assign_card_to_deck(
        self,
        *,
        card_id: int,
        deck_id: int,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        timestamp = serialize_datetime(utc_now())
        with self._use_connection(connection) as active_connection:
            active_connection.execute(
                """
                INSERT INTO deck_cards (card_id, deck_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    deck_id = excluded.deck_id,
                    created_at = excluded.created_at
                """,
                (card_id, deck_id, timestamp),
            )

    def count_cards_in_deck(self, deck_id: int) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM deck_cards WHERE deck_id = ?",
                (deck_id,),
            ).fetchone()
        return row[0]

    def count_new_cards_reviewed_on_day(
        self,
        *,
        deck_id: int,
        day_start: datetime,
        day_end: datetime,
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT cards.id
                    FROM deck_cards
                    JOIN cards ON cards.id = deck_cards.card_id
                    JOIN review_logs ON review_logs.card_id = cards.id
                    WHERE deck_cards.deck_id = ?
                      AND review_logs.undone_at IS NULL
                    GROUP BY cards.id
                    HAVING MIN(review_logs.reviewed_at) >= ?
                       AND MIN(review_logs.reviewed_at) < ?
                )
                """,
                (
                    deck_id,
                    serialize_datetime(day_start),
                    serialize_datetime(day_end),
                ),
            ).fetchone()
        return row[0]

    def query_due_learned_cards(self, *, deck_id: int, now: datetime) -> list:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {CARD_SELECT}
                WHERE deck_cards.deck_id = ?
                  AND cards.due_at IS NOT NULL
                  AND cards.due_at <= ?
                  AND EXISTS (
                      SELECT 1
                      FROM review_logs
                      WHERE review_logs.card_id = cards.id
                        AND review_logs.undone_at IS NULL
                  )
                ORDER BY cards.due_at, cards.id
                """,
                (deck_id, serialize_datetime(now)),
            ).fetchall()
        return [row_to_card(row) for row in rows]

    def query_new_cards(self, *, deck_id: int) -> list:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {CARD_SELECT}
                WHERE deck_cards.deck_id = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM review_logs
                      WHERE review_logs.card_id = cards.id
                        AND review_logs.undone_at IS NULL
                  )
                ORDER BY cards.id
                """,
                (deck_id,),
            ).fetchall()
        return [row_to_card(row) for row in rows]

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
