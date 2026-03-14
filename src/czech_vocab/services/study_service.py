from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardRecord, CardRepository
from czech_vocab.services.deck_settings_service import DeckSettingsService


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


@dataclass(frozen=True)
class QueueState:
    card: StudyCard | None
    empty_reason: str | None


class StudyService:
    def __init__(self, database_path: Path, *, scheduler: FsrsScheduler | None = None) -> None:
        self._repository = CardRepository(database_path)
        self._deck_settings_service = DeckSettingsService(database_path)
        self._scheduler = scheduler or FsrsScheduler()

    def get_next_due_card(self, *, now: datetime, deck_id: int | None = None) -> StudyCard | None:
        return self.get_queue_state(now=now, deck_id=deck_id).card

    def get_queue_state(self, *, now: datetime, deck_id: int | None = None) -> QueueState:
        active_deck_id = deck_id or self._deck_settings_service.get_default_deck().id
        if self._repository.count_cards_in_deck(active_deck_id) == 0:
            return QueueState(card=None, empty_reason="no_cards")
        due_cards = self._repository.query_due_learned_cards(deck_id=active_deck_id, now=now)
        if due_cards:
            return QueueState(card=_to_study_card(due_cards[0]), empty_reason=None)
        new_cards = self._repository.query_new_cards(deck_id=active_deck_id)
        if not new_cards:
            return QueueState(card=None, empty_reason="no_due_cards")
        if self._new_limit_reached(deck_id=active_deck_id, now=now):
            return QueueState(card=None, empty_reason="new_limit_reached")
        return QueueState(card=_to_study_card(new_cards[0]), empty_reason=None)

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

    def _new_limit_reached(self, *, deck_id: int, now: datetime) -> bool:
        deck = self._deck_settings_service.get_default_deck()
        if deck_id != deck.id:
            selected = next(
                item for item in self._deck_settings_service.list_decks() if item.id == deck_id
            )
            deck = selected
        day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        reviewed_new_cards = self._repository.count_new_cards_reviewed_on_day(
            deck_id=deck_id,
            day_start=day_start,
            day_end=day_end,
        )
        return reviewed_new_cards >= deck.daily_new_limit


def _to_study_card(card: CardRecord) -> StudyCard:
    return StudyCard(
        card_id=card.id,
        lemma=card.lemma,
        translation=card.translation,
        notes=card.notes,
        metadata=card.metadata,
        due_at=card.due_at,
    )
