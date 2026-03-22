import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from czech_vocab.repositories.deck_card_repository import DeckCardRepository
from czech_vocab.repositories.records import (
    CardCreate,
    CardRecord,
    ReviewLogRecord,
    build_identity_key,
    build_lemma_key,
    dump_json,
    matches_query,
    parse_datetime,
    row_to_card,
    serialize_datetime,
    utc_now,
)

CARD_SELECT = """
SELECT cards.*, deck_cards.deck_id AS deck_id
FROM cards
LEFT JOIN deck_cards ON deck_cards.card_id = cards.id
"""


class CardRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._deck_card_repository = DeckCardRepository(database_path)

    def get_card_by_id(
        self,
        card_id: int,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CardRecord | None:
        query = f"{CARD_SELECT} WHERE cards.id = ?"
        return self._fetch_one(query, (card_id,), connection=connection)

    def get_card_by_identity_key(
        self,
        identity_key: str,
        *,
        deck_id: int = 1,
        connection: sqlite3.Connection | None = None,
    ) -> CardRecord | None:
        query = f"{CARD_SELECT} WHERE deck_cards.deck_id = ? AND cards.identity_key = ?"
        return self._fetch_one(query, (deck_id, identity_key), connection=connection)

    def get_card_by_lemma_key(
        self,
        lemma_key: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CardRecord | None:
        query = f"{CARD_SELECT} WHERE cards.lemma_key = ?"
        return self._fetch_one(query, (lemma_key,), connection=connection)

    def list_available_cards(self) -> list[CardRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {CARD_SELECT}
                WHERE deck_cards.card_id IS NULL
                ORDER BY cards.lemma, cards.id
                """
            ).fetchall()
        return [row_to_card(row) for row in rows]

    def create_card(
        self,
        card: CardCreate,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CardRecord:
        timestamp = serialize_datetime(utc_now())
        payload = (
            build_lemma_key(card.lemma),
            card.identity_key,
            card.lemma,
            card.translation,
            card.notes,
            dump_json(card.metadata),
            dump_json(card.fsrs_state),
            serialize_datetime(card.due_at),
            serialize_datetime(card.last_review_at),
            timestamp,
            timestamp,
        )
        with self._use_connection(connection) as active_connection:
            cursor = active_connection.execute(
                """
                INSERT INTO cards (
                    lemma_key,
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            if card.deck_id is not None:
                self._deck_card_repository.assign_card_to_deck(
                    card_id=cursor.lastrowid,
                    deck_id=card.deck_id,
                    connection=active_connection,
                )
            created = self.get_card_by_id(cursor.lastrowid, connection=active_connection)
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
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self._update_card_fields(
            card_id=card_id,
            identity_key=build_identity_key(lemma, translation),
            lemma=lemma,
            translation=translation,
            notes=notes,
            metadata=metadata,
            connection=connection,
        )

    def update_card_content(
        self,
        *,
        card_id: int,
        deck_id: int,
        identity_key: str,
        lemma: str,
        translation: str,
        notes: str,
        metadata: dict[str, Any],
        connection: sqlite3.Connection | None = None,
    ) -> None:
        with self._use_connection(connection) as active_connection:
            self._update_card_fields(
                card_id=card_id,
                identity_key=identity_key,
                lemma=lemma,
                translation=translation,
                notes=notes,
                metadata=metadata,
                connection=active_connection,
            )
            self._deck_card_repository.assign_card_to_deck(
                card_id=card_id,
                deck_id=deck_id,
                connection=active_connection,
            )

    def update_schedule_state(
        self,
        *,
        card_id: int,
        fsrs_state: dict[str, Any],
        due_at: datetime | None,
        last_review_at: datetime | None,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        with self._use_connection(connection) as active_connection:
            active_connection.execute(
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
        connection: sqlite3.Connection | None = None,
    ) -> ReviewLogRecord:
        with self._use_connection(connection) as active_connection:
            cursor = active_connection.execute(
                """
                INSERT INTO review_logs (
                    card_id,
                    rating,
                    reviewed_at,
                    review_duration_seconds,
                    undone_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    card_id,
                    rating,
                    serialize_datetime(reviewed_at),
                    review_duration_seconds,
                    None,
                ),
            )
        return ReviewLogRecord(
            id=cursor.lastrowid,
            card_id=card_id,
            rating=rating,
            reviewed_at=reviewed_at.astimezone(UTC),
            review_duration_seconds=review_duration_seconds,
            undone_at=None,
        )

    def list_review_logs(self, card_id: int) -> list[ReviewLogRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, card_id, rating, reviewed_at, review_duration_seconds, undone_at
                FROM review_logs
                WHERE card_id = ?
                ORDER BY reviewed_at, id
                """,
                (card_id,),
            ).fetchall()
        return [_row_to_review_log(row) for row in rows]

    def get_latest_active_review_log(
        self,
        *,
        card_id: int,
        connection: sqlite3.Connection | None = None,
    ) -> ReviewLogRecord | None:
        with self._use_connection(connection) as active_connection:
            row = active_connection.execute(
                """
                SELECT id, card_id, rating, reviewed_at, review_duration_seconds, undone_at
                FROM review_logs
                WHERE card_id = ? AND undone_at IS NULL
                ORDER BY reviewed_at DESC, id DESC
                LIMIT 1
                """,
                (card_id,),
            ).fetchone()
        return _row_to_review_log(row) if row else None

    def mark_review_log_undone(
        self,
        *,
        review_log_id: int,
        undone_at: datetime,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        with self._use_connection(connection) as active_connection:
            active_connection.execute(
                """
                UPDATE review_logs
                SET undone_at = ?
                WHERE id = ? AND undone_at IS NULL
                """,
                (serialize_datetime(undone_at), review_log_id),
            )

    def count_cards_in_deck(self, deck_id: int) -> int:
        return self._deck_card_repository.count_cards_in_deck(deck_id)

    def count_new_cards_reviewed_on_day(
        self,
        *,
        deck_id: int,
        day_start: datetime,
        day_end: datetime,
    ) -> int:
        return self._deck_card_repository.count_new_cards_reviewed_on_day(
            deck_id=deck_id,
            day_start=day_start,
            day_end=day_end,
        )

    def query_due_learned_cards(self, *, deck_id: int, now: datetime) -> list[CardRecord]:
        return self._deck_card_repository.query_due_learned_cards(deck_id=deck_id, now=now)

    def query_new_cards(self, *, deck_id: int) -> list[CardRecord]:
        return self._deck_card_repository.query_new_cards(deck_id=deck_id)

    def query_due_cards(self, now: datetime) -> list[CardRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {CARD_SELECT}
                WHERE cards.due_at IS NOT NULL AND cards.due_at <= ?
                ORDER BY cards.due_at, cards.id
                """,
                (serialize_datetime(now),),
            ).fetchall()
        return [row_to_card(row) for row in rows]

    def search_cards(self, query: str, *, limit: int = 50, offset: int = 0) -> list[CardRecord]:
        needle = query.casefold()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {CARD_SELECT}
                ORDER BY cards.lemma, cards.id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        matches = [row_to_card(row) for row in rows if matches_query(row, needle)]
        return matches

    def connect(self) -> sqlite3.Connection:
        return self._connect()

    def _update_card_fields(
        self,
        *,
        card_id: int,
        identity_key: str | None,
        lemma: str,
        translation: str,
        notes: str,
        metadata: dict[str, Any],
        connection: sqlite3.Connection | None = None,
    ) -> None:
        identity_sql = ", identity_key = ?" if identity_key is not None else ""
        lemma_sql = build_lemma_key(lemma)
        params: list[Any] = [
            lemma_sql,
            lemma,
            translation,
            notes,
            dump_json(metadata),
            serialize_datetime(utc_now()),
        ]
        if identity_key is not None:
            params.append(identity_key)
        params.append(card_id)
        with self._use_connection(connection) as active_connection:
            active_connection.execute(
                f"""
                UPDATE cards
                SET
                    lemma_key = ?,
                    lemma = ?,
                    translation = ?,
                    notes = ?,
                    metadata_json = ?,
                    updated_at = ?{identity_sql}
                WHERE id = ?
                """,
                tuple(params),
            )

    def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> CardRecord | None:
        with self._use_connection(connection) as active_connection:
            row = active_connection.execute(query, params).fetchone()
        return row_to_card(row) if row else None

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


def _row_to_review_log(row: sqlite3.Row) -> ReviewLogRecord:
    return ReviewLogRecord(
        id=row["id"],
        card_id=row["card_id"],
        rating=row["rating"],
        reviewed_at=parse_datetime(row["reviewed_at"]),
        review_duration_seconds=row["review_duration_seconds"],
        undone_at=parse_datetime(row["undone_at"]),
    )
