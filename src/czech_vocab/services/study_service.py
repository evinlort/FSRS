from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import sample
from typing import Callable

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardRecord, CardRepository
from czech_vocab.repositories.records import UndoReviewSnapshot
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
    undo_snapshot: UndoReviewSnapshot


@dataclass(frozen=True)
class QueueState:
    card: StudyCard | None
    empty_reason: str | None


class StudyService:
    def __init__(
        self,
        database_path: Path,
        *,
        scheduler: FsrsScheduler | None = None,
        shuffler: Callable[[list[CardRecord]], list[CardRecord]] | None = None,
    ) -> None:
        self._repository = CardRepository(database_path)
        self._deck_settings_service = DeckSettingsService(database_path)
        self._scheduler = scheduler or FsrsScheduler()
        self._shuffler = shuffler or _shuffle_cards

    def get_next_due_card(self, *, now: datetime, deck_id: int | None = None) -> StudyCard | None:
        return self.get_queue_state(now=now, deck_id=deck_id).card

    def get_queue_state(self, *, now: datetime, deck_id: int | None = None) -> QueueState:
        active_deck_id = deck_id or self._deck_settings_service.get_default_deck().id
        if self._repository.count_cards_in_deck(active_deck_id) == 0:
            return QueueState(card=None, empty_reason="no_cards")
        due_cards = self._shuffler(
            self._repository.query_due_learned_cards(deck_id=active_deck_id, now=now)
        )
        if due_cards:
            return QueueState(card=_to_study_card(due_cards[0]), empty_reason=None)
        new_cards = self._repository.query_new_cards(deck_id=active_deck_id)
        if not new_cards:
            return QueueState(card=None, empty_reason="no_due_cards")
        if self._new_limit_reached(deck_id=active_deck_id, now=now):
            return QueueState(card=None, empty_reason="new_limit_reached")
        new_cards = self._shuffler(new_cards)
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
            previous_state = UndoReviewSnapshot(
                card_id=card.id,
                deck_id=card.deck_id,
                review_log_id=0,
                fsrs_state=card.fsrs_state,
                due_at=card.due_at,
                last_review_at=card.last_review_at,
            )
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
            review_log = self._repository.insert_review_log(
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
            undo_snapshot=UndoReviewSnapshot(
                card_id=previous_state.card_id,
                deck_id=previous_state.deck_id,
                review_log_id=review_log.id,
                fsrs_state=previous_state.fsrs_state,
                due_at=previous_state.due_at,
                last_review_at=previous_state.last_review_at,
            ),
        )

    def undo_review(self, *, snapshot: UndoReviewSnapshot, undone_at: datetime) -> None:
        with self._repository.connect() as connection:
            card = self._repository.get_card_by_id(snapshot.card_id, connection=connection)
            if card is None:
                raise LookupError(f"Card not found: {snapshot.card_id}")
            latest_log = self._repository.get_latest_active_review_log(
                card_id=snapshot.card_id,
                connection=connection,
            )
            if latest_log is None or latest_log.id != snapshot.review_log_id:
                raise ValueError("Undo is no longer available")
            self._repository.update_schedule_state(
                card_id=snapshot.card_id,
                fsrs_state=snapshot.fsrs_state,
                due_at=snapshot.due_at,
                last_review_at=snapshot.last_review_at,
                connection=connection,
            )
            self._repository.mark_review_log_undone(
                review_log_id=snapshot.review_log_id,
                undone_at=undone_at,
                connection=connection,
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


def _shuffle_cards(cards: list[CardRecord]) -> list[CardRecord]:
    if len(cards) < 2:
        return list(cards)
    return sample(cards, k=len(cards))
