import sqlite3
from io import BytesIO

from czech_vocab.repositories import build_identity_key


def test_get_import_page_renders_upload_form(client) -> None:
    response = client.get("/import")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "<form" in page
    assert 'type="file"' in page
    assert 'name="csv_file"' in page


def test_valid_csv_upload_creates_cards_and_shows_summary(client, app) -> None:
    response = post_csv(
        client,
        "lemma_cs,translation_ru,notes\nkniha,книга,common noun\nvlak,поезд,transport\n",
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Created: 2" in page
    assert "Updated: 0" in page
    assert "Rejected: 0" in page
    assert count_cards(app.config["DATABASE_PATH"]) == 2
    stored_card = fetch_card(app.config["DATABASE_PATH"], "kniha", "книга")
    assert stored_card is not None
    assert stored_card["due_at"] is not None
    assert stored_card["fsrs_state_json"] != "{}"


def test_reimport_updates_existing_card_without_duplicate_or_schedule_reset(client, app) -> None:
    post_csv(client, "lemma_cs,translation_ru,notes\nkniha,книга,old note\n")
    original = fetch_card(app.config["DATABASE_PATH"], "kniha", "книга")

    response = post_csv(client, "lemma_cs,translation_ru,notes\nkniha,книга,new note\n")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Created: 0" in page
    assert "Updated: 1" in page
    assert count_cards(app.config["DATABASE_PATH"]) == 1
    updated = fetch_card(app.config["DATABASE_PATH"], "kniha", "книга")
    assert updated is not None
    assert updated["notes"] == "new note"
    assert updated["due_at"] == original["due_at"]
    assert updated["fsrs_state_json"] == original["fsrs_state_json"]


def test_row_errors_are_reported_while_valid_rows_import(client, app) -> None:
    response = post_csv(
        client,
        "lemma_cs,translation_ru,notes\nkniha,книга,valid\n,поезд,missing lemma\n",
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Created: 1" in page
    assert "Rejected: 1" in page
    assert "Line 3: Missing required value: czech" in page
    assert count_cards(app.config["DATABASE_PATH"]) == 1


def test_missing_required_headers_fails_without_partial_writes(client, app) -> None:
    response = post_csv(client, "notes\nmissing headers\n")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Missing required headers: czech, russian" in page
    assert count_cards(app.config["DATABASE_PATH"]) == 0


def post_csv(client, csv_text: str):
    return client.post(
        "/import",
        data={"csv_file": (BytesIO(csv_text.encode("utf-8")), "words.csv")},
        content_type="multipart/form-data",
    )


def count_cards(database_path) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM cards").fetchone()
    return row[0]


def fetch_card(database_path, lemma: str, translation: str):
    identity_key = build_identity_key(lemma, translation)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT notes, due_at, fsrs_state_json FROM cards WHERE identity_key = ?",
            (identity_key,),
        ).fetchone()
