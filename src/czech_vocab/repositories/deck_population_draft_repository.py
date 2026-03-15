import secrets
import sqlite3
from pathlib import Path

from czech_vocab.repositories.records import (
    DeckPopulationDraftRecord,
    dump_json,
    row_to_deck_population_draft,
    serialize_datetime,
    utc_now,
)


class DeckPopulationDraftRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def create_draft(
        self,
        *,
        flow_type: str,
        deck_id: int | None,
        deck_name: str | None,
        requested_count: int,
        mode: str,
        save_default_count: bool,
        selected_card_ids: list[int],
        search_in: str,
        query_text: str,
        page: int,
    ) -> DeckPopulationDraftRecord:
        token = secrets.token_urlsafe(18)
        timestamp = serialize_datetime(utc_now())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO deck_population_drafts (
                    token,
                    flow_type,
                    deck_id,
                    deck_name,
                    requested_count,
                    mode,
                    save_default_count,
                    selected_card_ids_json,
                    search_in,
                    query_text,
                    page,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    flow_type,
                    deck_id,
                    deck_name,
                    requested_count,
                    mode,
                    int(save_default_count),
                    dump_json(selected_card_ids),
                    search_in,
                    query_text,
                    page,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM deck_population_drafts WHERE token = ?",
                (token,),
            ).fetchone()
        assert row is not None
        return row_to_deck_population_draft(row)

    def get_draft(self, token: str) -> DeckPopulationDraftRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM deck_population_drafts WHERE token = ?",
                (token,),
            ).fetchone()
        return row_to_deck_population_draft(row) if row else None

    def update_draft(
        self,
        *,
        token: str,
        selected_card_ids: list[int],
        search_in: str,
        query_text: str,
        page: int,
    ) -> DeckPopulationDraftRecord:
        timestamp = serialize_datetime(utc_now())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE deck_population_drafts
                SET
                    selected_card_ids_json = ?,
                    search_in = ?,
                    query_text = ?,
                    page = ?,
                    updated_at = ?
                WHERE token = ?
                """,
                (
                    dump_json(selected_card_ids),
                    search_in,
                    query_text,
                    page,
                    timestamp,
                    token,
                ),
            )
            row = connection.execute(
                "SELECT * FROM deck_population_drafts WHERE token = ?",
                (token,),
            ).fetchone()
        if row is None:
            raise LookupError(f"Draft not found: {token}")
        return row_to_deck_population_draft(row)

    def delete_draft(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM deck_population_drafts WHERE token = ?", (token,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
