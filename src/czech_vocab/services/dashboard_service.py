from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from czech_vocab.repositories import CardRepository, DeckRepository
from czech_vocab.repositories.records import serialize_datetime


@dataclass(frozen=True)
class DashboardDeckSummary:
    deck_id: int
    name: str
    total_cards: int
    due_cards: int


@dataclass(frozen=True)
class DashboardRecentReview:
    deck_name: str
    lemma: str
    rating: str
    reviewed_at_text: str


@dataclass(frozen=True)
class DashboardData:
    total_cards: int
    due_cards: int
    selected_deck_id: int | None
    deck_summaries: list[DashboardDeckSummary]
    recent_reviews: list[DashboardRecentReview]


class DashboardService:
    def __init__(self, database_path: Path) -> None:
        self._repository = CardRepository(database_path)
        self._deck_repository = DeckRepository(database_path)

    def get_dashboard_data(self, *, now: datetime) -> DashboardData:
        deck_summaries = self._load_deck_summaries(now)
        return DashboardData(
            total_cards=sum(item.total_cards for item in deck_summaries),
            due_cards=sum(item.due_cards for item in deck_summaries),
            selected_deck_id=_pick_selected_deck(deck_summaries),
            deck_summaries=deck_summaries,
            recent_reviews=self._load_recent_reviews(),
        )

    def _load_deck_summaries(self, now: datetime) -> list[DashboardDeckSummary]:
        decks = self._deck_repository.list_decks()
        with self._repository.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    decks.id AS deck_id,
                    decks.name AS deck_name,
                    COUNT(cards.id) AS total_cards,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN cards.due_at IS NOT NULL AND cards.due_at <= ? THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS due_cards
                FROM decks
                LEFT JOIN deck_cards ON deck_cards.deck_id = decks.id
                LEFT JOIN cards ON cards.id = deck_cards.card_id
                GROUP BY decks.id, decks.name
                ORDER BY decks.id
                """,
                (serialize_datetime(now),),
            ).fetchall()
        totals = {row["deck_id"]: row for row in rows}
        return [
            DashboardDeckSummary(
                deck_id=deck.id,
                name=deck.name,
                total_cards=totals[deck.id]["total_cards"],
                due_cards=totals[deck.id]["due_cards"],
            )
            for deck in decks
        ]

    def _load_recent_reviews(self) -> list[DashboardRecentReview]:
        with self._repository.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    decks.name AS deck_name,
                    cards.lemma,
                    review_logs.rating,
                    review_logs.reviewed_at
                FROM review_logs
                JOIN cards ON cards.id = review_logs.card_id
                JOIN deck_cards ON deck_cards.card_id = cards.id
                JOIN decks ON decks.id = deck_cards.deck_id
                WHERE review_logs.undone_at IS NULL
                ORDER BY review_logs.reviewed_at DESC, review_logs.id DESC
                LIMIT 5
                """
            ).fetchall()
        return [
            DashboardRecentReview(
                deck_name=row["deck_name"],
                lemma=row["lemma"],
                rating=row["rating"],
                reviewed_at_text=row["reviewed_at"],
            )
            for row in rows
        ]


def _pick_selected_deck(deck_summaries: list[DashboardDeckSummary]) -> int | None:
    for deck in deck_summaries:
        if deck.due_cards > 0:
            return deck.deck_id
    for deck in deck_summaries:
        if deck.total_cards > 0:
            return deck.deck_id
    return None
