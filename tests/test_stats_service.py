from datetime import UTC, datetime, timedelta
from pathlib import Path

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import (
    REVERSE_REVIEW_DIRECTION,
    CardCreate,
    CardRepository,
    build_identity_key,
    initialize_database,
)
from czech_vocab.services import DeckSettingsService, StatsService


def test_stats_service_calculates_metrics_for_selected_deck(tmp_path: Path) -> None:
    database_path = tmp_path / "stats.sqlite3"
    initialize_database(database_path)
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    travel = DeckSettingsService(database_path).create_deck("Путешествия")
    due_card = create_stats_card(
        database_path,
        lemma="auto",
        translation="машина",
        due_at=now - timedelta(hours=2),
        learned=True,
        deck_id=travel.id,
        last_review_at=now - timedelta(days=4),
    )
    create_stats_card(
        database_path,
        lemma="lod",
        translation="лодка",
        due_at=now + timedelta(days=2),
        learned=False,
        deck_id=travel.id,
    )
    add_review(database_path, due_card.id, "Good", now - timedelta(hours=1))
    add_review(database_path, due_card.id, "Again", now - timedelta(days=2))

    stats = StatsService(database_path).get_stats(now=now, deck=str(travel.id))

    assert stats.selected_deck == str(travel.id)
    assert stats.due_today == 1
    assert stats.reviewed_today == 1
    assert stats.success_rate == "50%"
    assert stats.fail_rate == "50%"
    assert stats.desired_retention_text == "0.90"
    assert stats.average_interval_text == "3.9 дн."
    assert stats.summary_rows[0].date_text == "2026-03-14"


def test_stats_service_uses_app_default_retention_for_all_decks_and_ignores_undone_logs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "stats.sqlite3"
    initialize_database(database_path)
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    card = create_stats_card(
        database_path,
        lemma="kniha",
        translation="книга",
        due_at=now + timedelta(days=3),
        learned=True,
        last_review_at=now - timedelta(days=5),
    )
    add_review(database_path, card.id, "Easy", now - timedelta(days=1), undone=True)

    stats = StatsService(database_path).get_stats(now=now, deck="all")

    assert stats.selected_deck == "all"
    assert stats.reviewed_today == 0
    assert stats.success_rate == "Нет данных"
    assert stats.fail_rate == "Нет данных"
    assert stats.desired_retention_text == "0.90"
    assert stats.summary_rows == []


def test_stats_service_ignores_reverse_direction_activity(tmp_path: Path) -> None:
    database_path = tmp_path / "stats.sqlite3"
    initialize_database(database_path)
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    card = create_stats_card(
        database_path,
        lemma="most",
        translation="мост",
        due_at=now + timedelta(days=3),
        learned=False,
    )
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    reverse_state = scheduler.create_default_state(card_id=card.id, now=now - timedelta(days=1))
    repository.update_schedule_state(
        card_id=card.id,
        direction=REVERSE_REVIEW_DIRECTION,
        fsrs_state=reverse_state,
        due_at=now - timedelta(hours=1),
        last_review_at=now - timedelta(days=1),
    )
    repository.insert_review_log(
        card_id=card.id,
        direction=REVERSE_REVIEW_DIRECTION,
        rating="Good",
        reviewed_at=now - timedelta(hours=2),
        review_duration_seconds=12,
    )

    stats = StatsService(database_path).get_stats(now=now, deck="all")

    assert stats.due_today == 0
    assert stats.reviewed_today == 0
    assert stats.success_rate == "Нет данных"
    assert stats.summary_rows == []


def create_stats_card(
    database_path: Path,
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
        last_review_at=last_review_at or restored.last_review,
    )
    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    return updated


def add_review(
    database_path: Path,
    card_id: int,
    rating: str,
    reviewed_at: datetime,
    *,
    undone: bool = False,
) -> None:
    repository = CardRepository(database_path)
    log = repository.insert_review_log(
        card_id=card_id,
        rating=rating,
        reviewed_at=reviewed_at,
        review_duration_seconds=12,
    )
    if undone:
        repository.mark_review_log_undone(
            review_log_id=log.id,
            undone_at=reviewed_at + timedelta(minutes=1),
        )
