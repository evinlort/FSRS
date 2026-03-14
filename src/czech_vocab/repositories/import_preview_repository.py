import secrets
import sqlite3
from pathlib import Path

from czech_vocab.repositories.records import (
    ImportPreviewRecord,
    dump_json,
    row_to_import_preview,
    serialize_datetime,
    utc_now,
)


class ImportPreviewRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def create_preview(
        self,
        *,
        deck_name: str,
        rows: list[dict[str, object]],
        rejected_messages: list[str],
        duplicate_count: int,
        imported_at,
    ) -> ImportPreviewRecord:
        token = secrets.token_urlsafe(18)
        created_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO import_previews (
                    token,
                    deck_name,
                    rows_json,
                    rejected_messages_json,
                    duplicate_count,
                    imported_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    deck_name,
                    dump_json(rows),
                    dump_json(rejected_messages),
                    duplicate_count,
                    serialize_datetime(imported_at),
                    serialize_datetime(created_at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM import_previews WHERE token = ?",
                (token,),
            ).fetchone()
        assert row is not None
        return row_to_import_preview(row)

    def get_preview(self, token: str) -> ImportPreviewRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM import_previews WHERE token = ?",
                (token,),
            ).fetchone()
        return row_to_import_preview(row) if row else None

    def delete_preview(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM import_previews WHERE token = ?", (token,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
