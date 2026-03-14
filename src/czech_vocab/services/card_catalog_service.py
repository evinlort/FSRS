from dataclasses import dataclass
from math import ceil
from pathlib import Path

from czech_vocab.repositories import CardRepository
from czech_vocab.repositories.records import CardRecord, row_to_card

PAGE_SIZE = 50


@dataclass(frozen=True)
class CatalogCard:
    card_id: int
    lemma: str
    translation: str
    notes: str
    metadata: dict[str, str]
    due_text: str
    state_text: str


@dataclass(frozen=True)
class CatalogPage:
    cards: list[CatalogCard]
    query: str
    page: int
    total_pages: int
    has_previous: bool
    has_next: bool


class CardCatalogService:
    def __init__(self, database_path: Path) -> None:
        self._repository = CardRepository(database_path)

    def get_page(self, *, query: str = "", page: int = 1) -> CatalogPage:
        normalized_page = max(page, 1)
        all_cards = self._ordered_cards()
        filtered_cards = _filter_cards(all_cards, query)
        total_pages = max(1, ceil(len(filtered_cards) / PAGE_SIZE))
        current_page = min(normalized_page, total_pages)
        start = (current_page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page_cards = [self._to_catalog_card(card) for card in filtered_cards[start:end]]
        return CatalogPage(
            cards=page_cards,
            query=query,
            page=current_page,
            total_pages=total_pages,
            has_previous=current_page > 1,
            has_next=current_page < total_pages,
        )

    def _ordered_cards(self) -> list[CardRecord]:
        with self._repository.connect() as connection:
            rows = connection.execute("SELECT * FROM cards ORDER BY lemma, id").fetchall()
        return [row_to_card(row) for row in rows]

    def _to_catalog_card(self, card: CardRecord) -> CatalogCard:
        state = card.fsrs_state.get("state")
        state_text = _format_state(state)
        due_text = card.due_at.isoformat() if card.due_at else "Not scheduled"
        return CatalogCard(
            card_id=card.id,
            lemma=card.lemma,
            translation=card.translation,
            notes=card.notes,
            metadata={key: value for key, value in card.metadata.items() if value},
            due_text=due_text,
            state_text=state_text,
        )


def _filter_cards(cards: list[CardRecord], query: str) -> list[CardRecord]:
    needle = query.casefold().strip()
    if not needle:
        return cards
    filtered = []
    for card in cards:
        haystacks = (card.lemma, card.translation, card.notes)
        if any(needle in value.casefold() for value in haystacks):
            filtered.append(card)
    return filtered


def _format_state(value) -> str:
    mapping = {
        1: "learning",
        2: "review",
        3: "relearning",
        "1": "learning",
        "2": "review",
        "3": "relearning",
    }
    return mapping.get(value, "unknown")
