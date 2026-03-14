import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from czech_vocab.repositories.records import (
    CardCreate,
    CardRecord,
    ReviewLogRecord,
    dump_json,
    matches_query,
    parse_datetime,
    row_to_card,
    serialize_datetime,
    utc_now,
)


class CardRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def get_card_by_id(self, card_id: int) -> CardRecord | None:
        query = "SELECT * FROM cards WHERE id = ?"
        return self._fetch_one(query, (card_id,))

    def get_card_by_identity_key(self, identity_key: str) -> CardRecord | None:
        query = "SELECT * FROM cards WHERE identity_key = ?"
        return self._fetch_one(query, (identity_key,))

    def create_card(self, card: CardCreate) -> CardRecord:
        timestamp = utc_now()
        payload = (
            card.identity_key,
            card.lemma,
            card.translation,
            card.notes,
            dump_json(card.metadata),
            dump_json(card.fsrs_state),
            serialize_datetime(card.due_at),
            serialize_datetime(card.last_review_at),
            serialize_datetime(timestamp),
            serialize_datetime(timestamp),
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO cards (
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
        created = self.get_card_by_id(cursor.lastrowid)
        assert created is not None
        return created

    def update_imported_content(
        self,
        *,
        card_id: int,
        lemma: str,
        translation: str,
        notes: str,
        metadata: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE cards
                SET lemma = ?, translation = ?, notes = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    lemma,
                    translation,
                    notes,
                    dump_json(metadata),
                    serialize_datetime(utc_now()),
                    card_id,
                ),
            )

    def update_schedule_state(
        self,
        *,
        card_id: int,
        fsrs_state: dict[str, Any],
        due_at: datetime | None,
        last_review_at: datetime | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE cards
                SET fsrs_state_json = ?, due_at = ?, last_review_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    dump_json(fsrs_state),
                    serialize_datetime(due_at),
                    serialize_datetime(last_review_at),
                    serialize_datetime(utc_now()),
                    card_id,
                ),
            )

    def insert_review_log(
        self,
        *,
        card_id: int,
        rating: str,
        reviewed_at: datetime,
        review_duration_seconds: int | None,
    ) -> ReviewLogRecord:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO review_logs (card_id, rating, reviewed_at, review_duration_seconds)
                VALUES (?, ?, ?, ?)
                """,
                (
                    card_id,
                    rating,
                    serialize_datetime(reviewed_at),
                    review_duration_seconds,
                ),
            )
        return ReviewLogRecord(
            card_id,
            rating,
            reviewed_at.astimezone(UTC),
            review_duration_seconds,
        )

    def list_review_logs(self, card_id: int) -> list[ReviewLogRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT card_id, rating, reviewed_at, review_duration_seconds
                FROM review_logs
                WHERE card_id = ?
                ORDER BY reviewed_at, id
                """,
                (card_id,),
            ).fetchall()
        return [
            ReviewLogRecord(
                card_id=row["card_id"],
                rating=row["rating"],
                reviewed_at=parse_datetime(row["reviewed_at"]),
                review_duration_seconds=row["review_duration_seconds"],
            )
            for row in rows
        ]

    def query_due_cards(self, now: datetime) -> list[CardRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM cards
                WHERE due_at IS NOT NULL AND due_at <= ?
                ORDER BY due_at, id
                """,
                (serialize_datetime(now),),
            ).fetchall()
        return [row_to_card(row) for row in rows]

    def search_cards(self, query: str, *, limit: int = 50, offset: int = 0) -> list[CardRecord]:
        needle = query.casefold()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cards ORDER BY lemma, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        matches = [row_to_card(row) for row in rows if matches_query(row, needle)]
        return matches

    def _fetch_one(self, query: str, params: tuple[Any, ...]) -> CardRecord | None:
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return row_to_card(row) if row else None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
