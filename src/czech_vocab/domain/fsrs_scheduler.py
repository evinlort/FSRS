from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fsrs import Card, Rating, Scheduler

RATING_MAP = {
    "Again": Rating.Again,
    "Hard": Rating.Hard,
    "Good": Rating.Good,
    "Easy": Rating.Easy,
}


@dataclass(frozen=True)
class ReviewLogData:
    card_id: int
    rating: str
    reviewed_at: datetime
    review_duration_seconds: int | None


@dataclass(frozen=True)
class ReviewOutcome:
    card_state: dict[str, Any]
    due_at: datetime
    last_review_at: datetime
    review_log: ReviewLogData


class FsrsScheduler:
    def __init__(self, *, desired_retention: float = 0.90, enable_fuzzing: bool = True) -> None:
        self.desired_retention = desired_retention
        self._scheduler = Scheduler(
            desired_retention=desired_retention,
            enable_fuzzing=enable_fuzzing,
        )

    def create_default_state(self, *, card_id: int, now: datetime | None = None) -> dict[str, Any]:
        due_at = now.astimezone(UTC) if now else None
        return self.serialize_card(Card(card_id=card_id, due=due_at))

    def serialize_card(self, card: Card) -> dict[str, Any]:
        return card.to_dict()

    def deserialize_card(self, card_state: dict[str, Any]) -> Card:
        return Card.from_dict(card_state)

    def apply_rating(
        self,
        *,
        card_state: dict[str, Any],
        rating: str,
        review_at: datetime,
        review_duration_seconds: int | None = None,
    ) -> ReviewOutcome:
        fsrs_rating = self._parse_rating(rating)
        updated_card, review_log = self._scheduler.review_card(
            self.deserialize_card(card_state),
            fsrs_rating,
            review_datetime=review_at.astimezone(UTC),
            review_duration=review_duration_seconds,
        )
        assert updated_card.due is not None
        assert updated_card.last_review is not None
        return ReviewOutcome(
            card_state=self.serialize_card(updated_card),
            due_at=updated_card.due.astimezone(UTC),
            last_review_at=updated_card.last_review.astimezone(UTC),
            review_log=ReviewLogData(
                card_id=review_log.card_id,
                rating=review_log.rating.name,
                reviewed_at=review_log.review_datetime.astimezone(UTC),
                review_duration_seconds=review_log.review_duration,
            ),
        )

    def _parse_rating(self, rating: str) -> Rating:
        try:
            return RATING_MAP[rating]
        except KeyError as exc:
            raise ValueError(f"Unsupported rating: {rating}") from exc
