from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardCreate, build_identity_key, initialize_database
from czech_vocab.services import DeckSettingsService
from czech_vocab.services.study_service import StudyService


def test_get_next_due_card_returns_none_when_deck_has_no_cards(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")

    result = service.get_next_due_card(now=datetime(2026, 3, 14, 12, 0, tzinfo=UTC))
    queue = service.get_queue_state(now=datetime(2026, 3, 14, 12, 0, tzinfo=UTC))

    assert result is None
    assert queue.empty_reason == "no_cards"


def test_queue_serves_due_learned_cards_before_new_cards(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    learned_due = create_card(
        service,
        "auto",
        "машина",
        due_at=now - timedelta(days=2),
        learned=True,
    )
    create_card(service, "vlak", "поезд", due_at=now, learned=False)

    queue = service.get_queue_state(now=now)

    assert queue.card is not None
    assert queue.card.card_id == learned_due.id
    assert queue.empty_reason is None


def test_queue_is_isolated_to_selected_deck(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    settings = DeckSettingsService(tmp_path / "study.sqlite3")
    second_deck = settings.create_deck("Путешествия")
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_card(service, "kniha", "книга", due_at=now - timedelta(hours=1), learned=True)
    selected = create_card(
        service,
        "lod",
        "лодка",
        due_at=now - timedelta(days=1),
        learned=True,
        deck_id=second_deck.id,
    )

    queue = service.get_queue_state(now=now, deck_id=second_deck.id)

    assert queue.card is not None
    assert queue.card.card_id == selected.id
    assert queue.card.lemma == "lod"


def test_queue_reports_no_due_cards_when_only_future_learned_cards_exist(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_card(service, "dum", "дом", due_at=now + timedelta(days=2), learned=True)

    queue = service.get_queue_state(now=now)

    assert queue.card is None
    assert queue.empty_reason == "no_due_cards"


def test_queue_reports_new_limit_reached_when_new_cards_remain(tmp_path: Path) -> None:
    database_path = tmp_path / "study.sqlite3"
    service = build_service(database_path)
    settings = DeckSettingsService(database_path)
    default_deck = settings.get_default_deck()
    settings.update_deck_settings(
        deck_id=default_deck.id,
        desired_retention=default_deck.desired_retention,
        daily_new_limit=1,
    )
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    first_new = create_card(service, "pes", "собака", due_at=now, learned=False)
    create_card(service, "strom", "дерево", due_at=now, learned=False)
    service.submit_review(card_id=first_new.id, rating="Good", review_at=now)

    queue = service.get_queue_state(now=now + timedelta(minutes=5))

    assert queue.card is None
    assert queue.empty_reason == "new_limit_reached"


def test_submit_review_updates_schedule_and_adds_one_review_log(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_card(service, "kniha", "книга", due_at=review_at, learned=False)

    result = service.submit_review(
        card_id=created.id,
        rating="Good",
        review_at=review_at,
        review_duration_seconds=13,
    )

    stored = service._repository.get_card_by_id(created.id)
    logs = service._repository.list_review_logs(created.id)
    assert stored is not None
    assert result.card_id == created.id
    assert result.rating == "Good"
    assert result.reviewed_at == review_at
    assert stored.last_review_at == review_at
    assert stored.due_at is not None
    assert stored.due_at >= review_at
    assert len(logs) == 1
    assert logs[0].rating == "Good"
    assert logs[0].review_duration_seconds == 13


def test_undo_review_restores_previous_schedule_and_marks_log_undone(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_card(service, "kniha", "книга", due_at=review_at, learned=False)

    result = service.submit_review(
        card_id=created.id,
        rating="Good",
        review_at=review_at,
        review_duration_seconds=13,
    )

    service.undo_review(snapshot=result.undo_snapshot, undone_at=review_at + timedelta(minutes=1))

    restored = service._repository.get_card_by_id(created.id)
    logs = service._repository.list_review_logs(created.id)
    assert restored is not None
    assert restored.due_at == created.due_at
    assert restored.last_review_at == created.last_review_at
    assert restored.fsrs_state == created.fsrs_state
    assert len(logs) == 1
    assert logs[0].undone_at == review_at + timedelta(minutes=1)
    queue = service.get_queue_state(now=review_at + timedelta(minutes=2))
    assert queue.card is not None
    assert queue.card.card_id == created.id


def test_undo_review_rejects_second_attempt(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_card(service, "pes", "собака", due_at=review_at, learned=False)
    result = service.submit_review(card_id=created.id, rating="Good", review_at=review_at)

    service.undo_review(snapshot=result.undo_snapshot, undone_at=review_at + timedelta(minutes=1))

    with pytest.raises(ValueError, match="Undo is no longer available"):
        service.undo_review(
            snapshot=result.undo_snapshot,
            undone_at=review_at + timedelta(minutes=2),
        )


def test_invalid_rating_does_not_mutate_database(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_card(service, "pes", "собака", due_at=review_at, learned=False)
    before = service._repository.get_card_by_id(created.id)

    with pytest.raises(ValueError, match="Unsupported rating: Maybe"):
        service.submit_review(
            card_id=created.id,
            rating="Maybe",
            review_at=review_at,
        )

    after = service._repository.get_card_by_id(created.id)
    assert after == before
    assert service._repository.list_review_logs(created.id) == []


def build_service(database_path: Path) -> StudyService:
    initialize_database(database_path)
    return StudyService(database_path, scheduler=FsrsScheduler(enable_fuzzing=False))


def create_card(
    service: StudyService,
    lemma: str,
    translation: str,
    *,
    due_at: datetime,
    learned: bool,
    deck_id: int = 1,
):
    identity_key = build_identity_key(lemma, translation)
    created = service._repository.create_card(
        CardCreate(
            identity_key=identity_key,
            lemma=lemma,
            translation=translation,
            notes="",
            metadata={},
            fsrs_state=service._scheduler.create_default_state(card_id=0, now=due_at),
            due_at=due_at,
            last_review_at=None,
            deck_id=deck_id,
        ),
    )
    state = service._scheduler.create_default_state(card_id=created.id, now=due_at)
    restored = service._scheduler.deserialize_card(state)
    service._repository.update_schedule_state(
        card_id=created.id,
        fsrs_state=state,
        due_at=restored.due,
        last_review_at=restored.last_review,
    )
    if learned:
        service._repository.insert_review_log(
            card_id=created.id,
            rating="Good",
            reviewed_at=due_at - timedelta(days=1),
            review_duration_seconds=12,
        )
        service._repository.update_schedule_state(
            card_id=created.id,
            fsrs_state=state,
            due_at=due_at,
            last_review_at=due_at - timedelta(days=1),
        )
    updated = service._repository.get_card_by_id(created.id)
    assert updated is not None
    return updated
