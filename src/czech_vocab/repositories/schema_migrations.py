import sqlite3

from czech_vocab.repositories.records import build_lemma_key, serialize_datetime, utc_now


def ensure_app_settings_schema(connection: sqlite3.Connection) -> None:
    if not table_exists(connection, "app_settings"):
        return
    columns = table_columns(connection, "app_settings")
    if "default_target_deck_card_count" not in columns:
        connection.execute(
            """
            ALTER TABLE app_settings
            ADD COLUMN default_target_deck_card_count INTEGER NOT NULL DEFAULT 20
            """
        )


def ensure_review_logs_schema(
    connection: sqlite3.Connection,
    *,
    default_direction: str,
) -> None:
    if not table_exists(connection, "review_logs"):
        return
    columns = table_columns(connection, "review_logs")
    if "direction" not in columns:
        connection.execute("ALTER TABLE review_logs ADD COLUMN direction TEXT")
    connection.execute(
        """
        UPDATE review_logs
        SET direction = ?
        WHERE direction IS NULL OR direction = ''
        """,
        (default_direction,),
    )
    if "undone_at" not in columns:
        connection.execute("ALTER TABLE review_logs ADD COLUMN undone_at TEXT")
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_review_logs_card_direction
        ON review_logs (card_id, direction, reviewed_at)
        """
    )


def ensure_card_review_states_schema(
    connection: sqlite3.Connection,
    *,
    default_direction: str,
) -> None:
    if not table_exists(connection, "cards") or not table_exists(connection, "card_review_states"):
        return
    connection.execute(
        """
        INSERT INTO card_review_states (
            card_id,
            direction,
            fsrs_state_json,
            due_at,
            last_review_at,
            created_at,
            updated_at
        )
        SELECT
            cards.id,
            ?,
            cards.fsrs_state_json,
            cards.due_at,
            cards.last_review_at,
            cards.created_at,
            cards.updated_at
        FROM cards
        WHERE NOT EXISTS (
            SELECT 1
            FROM card_review_states
            WHERE card_review_states.card_id = cards.id
              AND card_review_states.direction = ?
        )
        """,
        (default_direction, default_direction),
    )


def ensure_cards_schema(
    connection: sqlite3.Connection,
    *,
    cards_schema_sql: str,
    link_schema_sql: str,
    default_deck_name: str,
) -> None:
    if not table_exists(connection, "cards"):
        connection.executescript(cards_schema_sql)
        return
    columns = table_columns(connection, "cards")
    if "deck_id" in columns or "lemma_key" not in columns:
        migrate_cards_to_global_base(
            connection,
            columns=columns,
            link_schema_sql=link_schema_sql,
            default_deck_name=default_deck_name,
        )
        return
    connection.executescript(cards_schema_sql)


def migrate_cards_to_global_base(
    connection: sqlite3.Connection,
    *,
    columns: set[str],
    link_schema_sql: str,
    default_deck_name: str,
) -> None:
    legacy_rows = connection.execute("SELECT * FROM cards ORDER BY id").fetchall()
    review_logs = review_log_rows(connection)
    conflicts = conflicting_lemma_keys(legacy_rows)
    if conflicts:
        joined = ", ".join(conflicts)
        raise ValueError(
            "Conflicting Czech duplicates during migration. "
            f"Resolve duplicate lemmas before startup: {joined}"
        )
    legacy_links = legacy_deck_links(
        connection,
        legacy_rows,
        columns=columns,
        default_deck_name=default_deck_name,
    )
    connection.executescript(
        """
        DROP TABLE IF EXISTS cards_new;
        CREATE TABLE cards_new (
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
        """
    )
    copy_legacy_cards(connection, legacy_rows)
    connection.executescript(
        """
        DROP TABLE cards;
        ALTER TABLE cards_new RENAME TO cards;
        CREATE INDEX IF NOT EXISTS idx_cards_due_at ON cards (due_at, id);
        DROP TABLE IF EXISTS deck_cards;
        """
    )
    connection.executescript(link_schema_sql)
    connection.executemany(
        "INSERT INTO deck_cards (card_id, deck_id, created_at) VALUES (?, ?, ?)",
        legacy_links,
    )
    restore_review_logs(connection, review_logs)


def copy_legacy_cards(connection: sqlite3.Connection, legacy_rows) -> None:
    payload = [
        (
            row["id"],
            build_lemma_key(row["lemma"]),
            row["identity_key"],
            row["lemma"],
            row["translation"],
            row["notes"],
            row["metadata_json"],
            row["fsrs_state_json"],
            row["due_at"],
            row["last_review_at"],
            row["created_at"],
            row["updated_at"],
        )
        for row in legacy_rows
    ]
    connection.executemany(
        """
        INSERT INTO cards_new (
            id,
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )


def legacy_deck_links(
    connection: sqlite3.Connection,
    legacy_rows,
    *,
    columns: set[str],
    default_deck_name: str,
) -> list[tuple]:
    default_deck_id = connection.execute(
        "SELECT id FROM decks WHERE name = ?",
        (default_deck_name,),
    ).fetchone()["id"]
    timestamp = serialize_datetime(utc_now())
    if "deck_id" not in columns:
        return [(row["id"], default_deck_id, timestamp) for row in legacy_rows]
    return [(row["id"], row["deck_id"], timestamp) for row in legacy_rows]


def conflicting_lemma_keys(legacy_rows) -> list[str]:
    seen: set[str] = set()
    conflicts: set[str] = set()
    for row in legacy_rows:
        lemma_key = build_lemma_key(row["lemma"])
        if lemma_key in seen:
            conflicts.add(lemma_key)
            continue
        seen.add(lemma_key)
    return sorted(conflicts)


def review_log_rows(connection: sqlite3.Connection) -> list[tuple]:
    if not table_exists(connection, "review_logs"):
        return []
    columns = table_columns(connection, "review_logs")
    direction_sql = "direction," if "direction" in columns else "? AS direction,"
    return connection.execute(
        f"""
        SELECT
            id,
            card_id,
            {direction_sql}
            rating,
            reviewed_at,
            review_duration_seconds,
            undone_at
        FROM review_logs
        ORDER BY id
        """,
        () if "direction" in columns else ("cz_to_ru",),
    ).fetchall()


def restore_review_logs(connection: sqlite3.Connection, review_logs) -> None:
    if not review_logs:
        return
    connection.execute("DELETE FROM review_logs")
    connection.executemany(
        """
        INSERT INTO review_logs (
            id,
            card_id,
            direction,
            rating,
            reviewed_at,
            review_duration_seconds,
            undone_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        review_logs,
    )


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def table_columns(connection: sqlite3.Connection, name: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({name})").fetchall()}
