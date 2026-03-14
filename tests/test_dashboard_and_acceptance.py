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
    upload_response = client.post(
        "/import",
        data={
            "csv_file": (
                BytesIO("lemma_cs,translation_ru,notes\nkniha,книга,book note\n".encode("utf-8")),
                "cards.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert upload_response.status_code == 200
    assert "Создано: 1" in upload_response.get_data(as_text=True)
    home_after_import = client.get("/").get_data(as_text=True)
    assert "Всего карточек: 1" in home_after_import
    assert "К повторению сегодня: 1" in home_after_import
    assert 'action="/review"' in home_after_import
    assert 'option value="1" selected' in home_after_import

    review_page = client.get("/review?deck=1")
    assert review_page.status_code == 200
    assert "kniha" in review_page.get_data(as_text=True)

    card = repository.get_card_by_identity_key(build_identity_key("kniha", "книга"))
    assert card is not None
    review_response = client.post(f"/review/{card.id}/grade", data={"rating": "Good"})

    assert review_response.status_code == 302
    logs = repository.list_review_logs(card.id)
    assert len(logs) == 1
    assert logs[0].rating == "Good"

    home_after_review = client.get("/").get_data(as_text=True)
    assert "К повторению сегодня: 0" in home_after_review
    catalog_page = client.get("/cards?q=kniha").get_data(as_text=True)
    assert "kniha" in catalog_page
    assert "книга" in catalog_page


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
