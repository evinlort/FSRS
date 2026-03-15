import re
from datetime import UTC, datetime, timedelta
from io import BytesIO

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardCreate, CardRepository, build_identity_key
from czech_vocab.services import DeckSettingsService


def test_home_page_shows_dashboard_sections_in_priority_order(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck_service = DeckSettingsService(database_path)
    second_deck = deck_service.create_deck("Путешествия")
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    due_card = create_dashboard_card(
        database_path,
        lemma="kniha",
        translation="книга",
        due_at=now - timedelta(hours=1),
        learned=True,
    )
    create_dashboard_card(
        database_path,
        lemma="vlak",
        translation="поезд",
        due_at=now + timedelta(days=2),
        learned=False,
        deck_id=second_deck.id,
    )
    create_review_log(database_path, due_card.id, reviewed_at=now - timedelta(minutes=15))

    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert page.index("Начать повторение") < page.index("К повторению сегодня")
    assert page.index("К повторению сегодня") < page.index("Колоды")
    assert page.index("Колоды") < page.index("Недавняя активность")
    assert page.index("Недавняя активность") < page.index("Импорт словаря")
    assert page.index("Импорт словаря") < page.index("Статистика по обучению")
    assert 'action="/review"' in page
    assert 'name="deck"' in page
    assert 'option value="1" selected' in page
    assert "Основная" in page
    assert "Путешествия" in page
    assert "Всего карточек: 2" in page
    assert "К повторению сегодня: 1" in page
    assert "kniha" in page
    assert "Good" in page


def test_home_page_points_to_import_when_no_cards_exist(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Пока нет карточек" in page
    assert 'href="/import"' in page
    assert "Импортировать слова" in page


def test_acceptance_flow_covers_import_review_and_catalog(client, app) -> None:
    repository = CardRepository(app.config["DATABASE_PATH"])
    preview_response = client.post(
        "/import/preview",
        data={
            "csv_file": (
                BytesIO("lemma_cs,translation_ru,notes\nkniha,книга,book note\n".encode("utf-8")),
                "cards.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert preview_response.status_code == 200
    preview_page = preview_response.get_data(as_text=True)
    assert "Предпросмотр импорта" in preview_page
    token = _extract_preview_token(preview_page)
    upload_response = client.post("/import/confirm", data={"preview_token": token})

    assert upload_response.status_code == 200
    assert "Добавлено карточек: 1" in upload_response.get_data(as_text=True)
    home_after_import = client.get("/").get_data(as_text=True)
    assert "Пока нет карточек" in home_after_import
    assert 'href="/import"' in home_after_import

    review_page = client.get("/review?deck=1")
    assert review_page.status_code == 200
    assert "Колода пуста" in review_page.get_data(as_text=True)

    card = repository.get_card_by_identity_key(build_identity_key("kniha", "книга"))
    assert card is None
    catalog_page = client.get("/cards?q=kniha").get_data(as_text=True)
    assert "kniha" in catalog_page
    assert "книга" in catalog_page
    assert "Без колоды" in catalog_page


def test_deck_population_regression_covers_create_add_and_saved_defaults(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    for lemma, translation in [
        ("kniha", "книга"),
        ("dum", "дом"),
        ("lod", "лодка"),
        ("mesto", "город"),
        ("vlak", "поезд"),
    ]:
        create_unassigned_card(database_path, lemma=lemma, translation=translation)

    created = client.post(
        "/decks/new",
        data={
            "deck_name": "Первая",
            "requested_count": "2",
            "mode": "random",
            "save_default_count": "on",
        },
        follow_redirects=True,
    )

    assert created.status_code == 200
    created_page = created.get_data(as_text=True)
    assert "Колода «Первая» создана. Добавлено 2 карточек." in created_page

    first_deck = DeckSettingsService(database_path).list_decks()[-1]
    with CardRepository(database_path).connect() as connection:
        assigned_rows = connection.execute(
            """
            SELECT cards.lemma
            FROM deck_cards
            JOIN cards ON cards.id = deck_cards.card_id
            WHERE deck_cards.deck_id = ?
            ORDER BY cards.lemma
            """,
            (first_deck.id,),
        ).fetchall()
    assigned_lemmas = [row["lemma"] for row in assigned_rows]
    assert len(assigned_lemmas) == 2

    second_deck = DeckSettingsService(database_path).create_deck("Вторая")
    add_page = client.get(f"/decks/{second_deck.id}/add")
    assert add_page.status_code == 200
    assert 'value="2"' in add_page.get_data(as_text=True)

    manual_start = client.post(
        f"/decks/{second_deck.id}/add",
        data={
            "requested_count": "2",
            "mode": "manual",
        },
    )
    assert manual_start.status_code == 302
    manual_page = client.get(manual_start.headers["Location"]).get_data(as_text=True)
    for lemma in assigned_lemmas:
        assert lemma not in manual_page
    assert "В колоду будет добавлено выбранное количество карточек." in manual_page
    manual_id = _extract_card_ids(manual_page)[0]

    manual_done = client.post(
        manual_start.headers["Location"],
        data={
            "action": "confirm",
            "search_in": "czech",
            "q": "",
            "selected_card_ids": [str(manual_id)],
        },
        follow_redirects=True,
    )
    assert manual_done.status_code == 200
    assert "В колоду «Вторая» добавлено 1 карточек." in manual_done.get_data(as_text=True)

    mixed_start = client.post(
        f"/decks/{second_deck.id}/add",
        data={
            "requested_count": "2",
            "mode": "mixed",
        },
    )
    assert mixed_start.status_code == 302
    mixed_page = client.get(mixed_start.headers["Location"]).get_data(as_text=True)
    assert "Остальные карточки будут выбраны случайно при добавлении в колоду." in mixed_page
    mixed_id = _extract_card_ids(mixed_page)[0]

    mixed_done = client.post(
        mixed_start.headers["Location"],
        data={
            "action": "confirm",
            "search_in": "czech",
            "q": "",
            "selected_card_ids": [str(mixed_id)],
        },
        follow_redirects=True,
    )
    assert mixed_done.status_code == 200
    mixed_done_page = mixed_done.get_data(as_text=True)
    assert "В колоду «Вторая» добавлено 2 карточек." in mixed_done_page
    assert "Вторая" in mixed_done_page

    with CardRepository(database_path).connect() as connection:
        second_count = connection.execute(
            "SELECT COUNT(*) FROM deck_cards WHERE deck_id = ?",
            (second_deck.id,),
        ).fetchone()[0]
        unique_assignments = connection.execute(
            "SELECT COUNT(*) = COUNT(DISTINCT card_id) FROM deck_cards",
        ).fetchone()[0]
    assert second_count == 3
    assert unique_assignments == 1


def _extract_preview_token(page: str) -> str:
    marker = 'name="preview_token" value="'
    start = page.index(marker) + len(marker)
    end = page.index('"', start)
    return page[start:end]


def _extract_card_ids(page: str) -> list[int]:
    return [int(match) for match in re.findall(r'name="selected_card_ids" value="(\d+)"', page)]


def create_dashboard_card(
    database_path,
    *,
    lemma: str,
    translation: str,
    due_at: datetime,
    learned: bool,
    deck_id: int = 1,
):
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    identity_key = build_identity_key(lemma, translation)
    created = repository.create_card(
        CardCreate(
            identity_key=identity_key,
            lemma=lemma,
            translation=translation,
            notes="",
            metadata={},
            fsrs_state=scheduler.create_default_state(card_id=0, now=due_at),
            due_at=due_at,
            last_review_at=None,
            deck_id=deck_id,
        ),
    )
    state = scheduler.create_default_state(card_id=created.id, now=due_at)
    restored = scheduler.deserialize_card(state)
    repository.update_schedule_state(
        card_id=created.id,
        fsrs_state=state,
        due_at=restored.due,
        last_review_at=restored.last_review,
    )
    if learned:
        create_review_log(database_path, created.id, reviewed_at=due_at - timedelta(days=1))
        repository.update_schedule_state(
            card_id=created.id,
            fsrs_state=state,
            due_at=due_at,
            last_review_at=due_at - timedelta(days=1),
        )
    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    return updated


def create_unassigned_card(
    database_path,
    *,
    lemma: str,
    translation: str,
):
    repository = CardRepository(database_path)
    due_at = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    return repository.create_card(
        CardCreate(
            identity_key=build_identity_key(lemma, translation),
            lemma=lemma,
            translation=translation,
            notes="",
            metadata={},
            fsrs_state={},
            due_at=due_at,
            last_review_at=None,
            deck_id=None,
        )
    )


def create_review_log(
    database_path,
    card_id: int,
    *,
    reviewed_at: datetime,
    rating: str = "Good",
) -> None:
    repository = CardRepository(database_path)
    repository.insert_review_log(
        card_id=card_id,
        rating=rating,
        reviewed_at=reviewed_at,
        review_duration_seconds=15,
    )
