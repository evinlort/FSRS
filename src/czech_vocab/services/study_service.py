from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardRecord, CardRepository


@dataclass(frozen=True)
class StudyCard:
    card_id: int
    lemma: str
    translation: str
    notes: str
    metadata: dict[str, str]
    due_at: datetime | None


@dataclass(frozen=True)
class ReviewResult:
    card_id: int
    rating: str
    reviewed_at: datetime
    due_at: datetime


class StudyService:
    def __init__(self, database_path: Path, *, scheduler: FsrsScheduler | None = None) -> None:
        self._repository = CardRepository(database_path)
        self._scheduler = scheduler or FsrsScheduler()

    def get_next_due_card(self, *, now: datetime) -> StudyCard | None:
        due_cards = self._repository.query_due_cards(now)
        if not due_cards:
            return None
        return _to_study_card(due_cards[0])

    def submit_review(
        self,
        *,
        card_id: int,
        rating: str,
        review_at: datetime,
        review_duration_seconds: int | None = None,
    ) -> ReviewResult:
        with self._repository.connect() as connection:
            card = self._repository.get_card_by_id(card_id, connection=connection)
            if card is None:
                raise LookupError(f"Card not found: {card_id}")
            outcome = self._scheduler.apply_rating(
                card_state=card.fsrs_state,
                rating=rating,
                review_at=review_at,
                review_duration_seconds=review_duration_seconds,
            )
            self._repository.update_schedule_state(
                card_id=card_id,
                fsrs_state=outcome.card_state,
                due_at=outcome.due_at,
                last_review_at=outcome.last_review_at,
                connection=connection,
            )
            self._repository.insert_review_log(
                card_id=card_id,
                rating=outcome.review_log.rating,
                reviewed_at=outcome.review_log.reviewed_at,
                review_duration_seconds=outcome.review_log.review_duration_seconds,
                connection=connection,
            )
        return ReviewResult(
            card_id=card_id,
            rating=outcome.review_log.rating,
            reviewed_at=outcome.review_log.reviewed_at,
            due_at=outcome.due_at,
        )


def _to_study_card(card: CardRecord) -> StudyCard:
    return StudyCard(
        card_id=card.id,
        lemma=card.lemma,
        translation=card.translation,
        notes=card.notes,
        metadata=card.metadata,
        due_at=card.due_at,
    )
