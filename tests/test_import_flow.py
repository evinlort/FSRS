import sqlite3
from io import BytesIO

from czech_vocab.repositories import build_identity_key


def test_get_import_page_renders_upload_form_for_global_base(client) -> None:
    response = client.get("/import")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'action="/import/preview"' in page
    assert 'enctype="multipart/form-data"' in page
    assert 'type="file"' in page
    assert 'name="csv_file"' in page
    assert "Глобальная база" in page
    assert 'name="deck_id"' not in page
    assert 'name="new_deck_name"' not in page
    assert "data-busy-form" in page
    assert 'data-busy-label="Готовим предпросмотр..."' in page


def test_preview_valid_csv_without_committing_and_confirm_import(client, app) -> None:
    preview_response = preview_csv(
        client,
        "lemma_cs,translation_ru,notes\nkniha,книга,common noun\nvlak,поезд,transport\n",
    )

    assert preview_response.status_code == 200
    preview_page = preview_response.get_data(as_text=True)
    assert "Предпросмотр импорта" in preview_page
    assert "Глобальная база" in preview_page
    assert "Готово к импорту: 2" in preview_page
    assert "Дубликаты будут пропущены: 0" in preview_page
    assert "Отклонено строк: 0" in preview_page
    assert 'action="/import/confirm"' in preview_page
    assert count_cards(app.config["DATABASE_PATH"]) == 0

    confirm_response = client.post(
        "/import/confirm",
        data={"preview_token": extract_preview_token(preview_page)},
        follow_redirects=True,
    )

    assert confirm_response.status_code == 200
    page = confirm_response.get_data(as_text=True)
    assert "Импорт завершён" in page
    assert "Добавлено карточек: 2" in page
    assert "Пропущено дубликатов: 0" in page
    assert count_cards(app.config["DATABASE_PATH"]) == 2
    stored_card = fetch_card(app.config["DATABASE_PATH"], "kniha", "книга")
    assert stored_card is not None
    assert stored_card["due_at"] is not None
    assert stored_card["fsrs_state_json"] != "{}"
    assert stored_card["deck_id"] is None
    assert count_deck_links(app.config["DATABASE_PATH"]) == 0


def test_imported_cards_remain_unassigned_and_not_reviewable(client, app) -> None:
    preview_response = preview_csv(
        client,
        "lemma_cs,translation_ru,notes\nlod,лодка,travel\n",
    )

    preview_page = preview_response.get_data(as_text=True)
    assert "Глобальная база" in preview_page

    confirm_response = client.post(
        "/import/confirm",
        data={"preview_token": extract_preview_token(preview_page)},
        follow_redirects=True,
    )

    assert confirm_response.status_code == 200
    stored_card = fetch_card(app.config["DATABASE_PATH"], "lod", "лодка")
    assert stored_card is not None
    assert stored_card["deck_id"] is None
    review_page = client.get("/review?deck=1").get_data(as_text=True)
    assert "Колода пуста" in review_page


def test_duplicate_preview_and_confirm_skip_existing_lemma_globally_without_updating(
    client,
    app,
) -> None:
    first_preview = preview_csv(client, "lemma_cs,translation_ru,notes\nkniha,книга,old note\n")
    client.post(
        "/import/confirm",
        data={"preview_token": extract_preview_token(first_preview.get_data(as_text=True))},
    )
    original = fetch_card(app.config["DATABASE_PATH"], "kniha", "книга")

    preview_response = preview_csv(
        client,
        "lemma_cs,translation_ru,notes\nkniha,издание,new note\n",
    )

    preview_page = preview_response.get_data(as_text=True)
    assert "Дубликаты будут пропущены: 1" in preview_page
    assert "Найдены дубликаты" in preview_page
    assert count_cards(app.config["DATABASE_PATH"]) == 1

    confirm_response = client.post(
        "/import/confirm",
        data={"preview_token": extract_preview_token(preview_page)},
        follow_redirects=True,
    )

    assert confirm_response.status_code == 200
    page = confirm_response.get_data(as_text=True)
    assert "Добавлено карточек: 0" in page
    assert "Пропущено дубликатов: 1" in page
    assert "Новые карточки не добавлены" in page
    assert count_cards(app.config["DATABASE_PATH"]) == 1
    updated = fetch_card(app.config["DATABASE_PATH"], "kniha", "книга")
    assert updated is not None
    assert updated["notes"] == "old note"
    assert updated["due_at"] == original["due_at"]
    assert updated["fsrs_state_json"] == original["fsrs_state_json"]


def test_row_errors_are_reported_in_preview_and_valid_rows_import_on_confirm(client, app) -> None:
    preview_response = preview_csv(
        client,
        "lemma_cs,translation_ru,notes\nkniha,книга,valid\n,поезд,missing lemma\n",
    )

    preview_page = preview_response.get_data(as_text=True)
    assert "Готово к импорту: 1" in preview_page
    assert "Отклонено строк: 1" in preview_page
    assert "Line 3: Missing required value: czech" in preview_page
    assert count_cards(app.config["DATABASE_PATH"]) == 0

    confirm_response = client.post(
        "/import/confirm",
        data={"preview_token": extract_preview_token(preview_page)},
        follow_redirects=True,
    )

    assert confirm_response.status_code == 200
    assert "Добавлено карточек: 1" in confirm_response.get_data(as_text=True)
    assert count_cards(app.config["DATABASE_PATH"]) == 1


def test_missing_required_headers_block_confirmation_without_partial_writes(client, app) -> None:
    response = preview_csv(client, "notes\nmissing headers\n")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Не удалось распознать обязательные заголовки CSV." in page
    assert "Missing required headers: czech, russian" in page
    assert "Выбрать другой файл" in page
    assert 'action="/import/confirm"' not in page
    assert count_cards(app.config["DATABASE_PATH"]) == 0


def preview_csv(client, csv_text: str):
    return client.post(
        "/import/preview",
        data={
            "csv_file": (BytesIO(csv_text.encode("utf-8")), "words.csv"),
        },
        content_type="multipart/form-data",
    )


def extract_preview_token(page: str) -> str:
    marker = 'name="preview_token" value="'
    start = page.index(marker) + len(marker)
    end = page.index('"', start)
    return page[start:end]


def count_cards(database_path) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM cards").fetchone()
    return row[0]


def count_deck_links(database_path) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM deck_cards").fetchone()
    return row[0]


def fetch_card(database_path, lemma: str, translation: str):
    identity_key = build_identity_key(lemma, translation)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            """
            SELECT
                cards.notes,
                cards.due_at,
                cards.fsrs_state_json,
                deck_cards.deck_id AS deck_id
            FROM cards
            LEFT JOIN deck_cards ON deck_cards.card_id = cards.id
            WHERE cards.identity_key = ?
            """,
            (identity_key,),
        ).fetchone()
