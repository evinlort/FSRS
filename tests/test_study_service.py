from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import (
    CardCreate,
    build_identity_key,
    initialize_database,
)
from czech_vocab.services.study_service import StudyService


def test_get_next_due_card_returns_none_when_nothing_is_due(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")

    result = service.get_next_due_card(now=datetime(2026, 3, 14, 12, 0, tzinfo=UTC))

    assert result is None


def test_get_next_due_card_returns_most_overdue_first(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    older_due = create_card(service, "auto", "машина", due_at=now - timedelta(days=2))
    create_card(service, "vlak", "поезд", due_at=now + timedelta(hours=1))
    newer_due = create_card(service, "dum", "дом", due_at=now - timedelta(hours=1))

    result = service.get_next_due_card(now=now)

    assert result is not None
    assert result.card_id == older_due.id
    assert result.lemma == "auto"
    assert result.due_at == older_due.due_at
    assert result.card_id != newer_due.id


def test_submit_review_updates_schedule_and_adds_one_review_log(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_card(service, "kniha", "книга", due_at=review_at)

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


def test_invalid_rating_does_not_mutate_database(tmp_path: Path) -> None:
    service = build_service(tmp_path / "study.sqlite3")
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_card(service, "pes", "собака", due_at=review_at)
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


def create_card(service: StudyService, lemma: str, translation: str, *, due_at: datetime):
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
    updated = service._repository.get_card_by_id(created.id)
    assert updated is not None
    return updated
