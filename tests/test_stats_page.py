from datetime import UTC, datetime, timedelta

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardCreate, CardRepository, build_identity_key
from czech_vocab.services import DeckSettingsService


def test_stats_page_shows_metrics_and_deck_filter(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    travel = DeckSettingsService(database_path).create_deck("Путешествия")
    card = create_stats_card(
        database_path,
        lemma="auto",
        translation="машина",
        due_at=now - timedelta(hours=1),
        learned=True,
        deck_id=travel.id,
        last_review_at=now - timedelta(days=3),
    )
    repository = CardRepository(database_path)
    repository.insert_review_log(
        card_id=card.id,
        rating="Good",
        reviewed_at=now - timedelta(hours=2),
        review_duration_seconds=12,
    )

    response = client.get(f"/stats?deck={travel.id}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Статистика за 30 дней" in page
    assert 'name="deck"' in page
    assert "Путешествия" in page
    assert "К повторению сегодня" in page
    assert "Успешных ответов" in page
    assert "Средний интервал" in page


def test_stats_page_shows_empty_state_without_review_history(client) -> None:
    response = client.get("/stats?deck=all")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Пока недостаточно истории повторений за последние 30 дней." in page
    assert 'href="/review"' in page


def create_stats_card(
    database_path,
    *,
    lemma: str,
    translation: str,
    due_at: datetime,
    learned: bool,
    deck_id: int = 1,
    last_review_at: datetime | None = None,
):
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    created = repository.create_card(
        CardCreate(
            identity_key=build_identity_key(lemma, translation),
            lemma=lemma,
            translation=translation,
            notes="",
            metadata={},
            fsrs_state=scheduler.create_default_state(card_id=0, now=due_at),
            due_at=due_at,
            last_review_at=None,
            deck_id=deck_id,
        )
    )
    state = scheduler.create_default_state(card_id=created.id, now=due_at)
    restored = scheduler.deserialize_card(state)
    repository.update_schedule_state(
        card_id=created.id,
        fsrs_state=state,
        due_at=restored.due,
        last_review_at=restored.last_review,
    )
    if learned and last_review_at is not None:
        repository.insert_review_log(
            card_id=created.id,
            rating="Good",
            reviewed_at=last_review_at,
            review_duration_seconds=12,
        )
        repository.update_schedule_state(
            card_id=created.id,
            fsrs_state=state,
            due_at=due_at,
            last_review_at=last_review_at,
        )
    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    return updated
