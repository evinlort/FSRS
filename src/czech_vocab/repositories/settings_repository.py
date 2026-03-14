import sqlite3
from contextlib import contextmanager
from pathlib import Path

from czech_vocab.repositories.records import (
    AppSettingsRecord,
    row_to_settings,
    serialize_datetime,
    utc_now,
)


class AppSettingsRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def get_settings(self) -> AppSettingsRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM app_settings WHERE id = 1").fetchone()
        assert row is not None
        return row_to_settings(row)

    def update_settings(
        self,
        *,
        default_desired_retention: float,
        default_daily_new_limit: int,
        connection: sqlite3.Connection | None = None,
    ) -> AppSettingsRecord:
        timestamp = serialize_datetime(utc_now())
        with self._use_connection(connection) as active_connection:
            active_connection.execute(
                """
                UPDATE app_settings
                SET default_desired_retention = ?, default_daily_new_limit = ?, updated_at = ?
                WHERE id = 1
                """,
                (default_desired_retention, default_daily_new_limit, timestamp),
            )
            row = active_connection.execute(
                "SELECT * FROM app_settings WHERE id = 1"
            ).fetchone()
        assert row is not None
        return row_to_settings(row)

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
