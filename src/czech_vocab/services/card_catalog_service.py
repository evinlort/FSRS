import json
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from pathlib import Path

from czech_vocab.repositories import CardRepository
from czech_vocab.services.deck_settings_service import DeckSettingsService

PAGE_SIZE = 50
ALLOWED_STATUSES = {"all", "due", "new", "learned"}
ALLOWED_SEARCH_SCOPES = {"all", "czech", "russian"}


@dataclass(frozen=True)
class CatalogDeckOption:
    value: str
    label: str


@dataclass(frozen=True)
class CatalogCard:
    card_id: int
    deck_name: str
    lemma: str
    translation: str
    notes: str
    metadata: dict[str, str]
    due_text: str
    state_text: str
    edit_path: str


@dataclass(frozen=True)
class CatalogPage:
    cards: list[CatalogCard]
    deck_options: list[CatalogDeckOption]
    selected_deck: str
    selected_status: str
    search_scope: str
    query: str
    page: int
    total_pages: int
    has_previous: bool
    has_next: bool
    is_empty_catalog: bool
    has_filters_applied: bool


class CardCatalogService:
    def __init__(self, database_path: Path) -> None:
        self._repository = CardRepository(database_path)
        self._deck_settings_service = DeckSettingsService(database_path)

    def get_page(
        self,
        *,
        now: datetime,
        deck: str = "all",
        status: str = "all",
        search_in: str = "all",
        query: str = "",
        page: int = 1,
    ) -> CatalogPage:
        selected_deck = deck if self._is_known_deck(deck) else "all"
        selected_status = status if status in ALLOWED_STATUSES else "all"
        search_scope = search_in if search_in in ALLOWED_SEARCH_SCOPES else "all"
        normalized_query = query.strip()
        all_cards = self._load_cards()
        filtered = [
            card
            for card in all_cards
            if _matches_filters(
                card,
                now=now,
                deck=selected_deck,
                status=selected_status,
                search_scope=search_scope,
                query=normalized_query,
            )
        ]
        total_pages = max(1, ceil(len(filtered) / PAGE_SIZE))
        current_page = min(max(page, 1), total_pages)
        start = (current_page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        return CatalogPage(
            cards=[self._to_catalog_card(card, now=now) for card in filtered[start:end]],
            deck_options=_deck_options(self._deck_settings_service.list_decks()),
            selected_deck=selected_deck,
            selected_status=selected_status,
            search_scope=search_scope,
            query=normalized_query,
            page=current_page,
            total_pages=total_pages,
            has_previous=current_page > 1,
            has_next=current_page < total_pages,
            is_empty_catalog=not all_cards,
            has_filters_applied=bool(
                normalized_query or selected_deck != "all" or selected_status != "all"
            ),
        )

    def _is_known_deck(self, raw_deck: str) -> bool:
        if raw_deck == "all":
            return True
        if not raw_deck.isdigit():
            return False
        return any(str(deck.id) == raw_deck for deck in self._deck_settings_service.list_decks())

    def _load_cards(self) -> list[dict]:
        with self._repository.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    cards.*,
                    decks.name AS deck_name,
                    EXISTS (
                        SELECT 1
                        FROM review_logs
                        WHERE review_logs.card_id = cards.id
                          AND review_logs.undone_at IS NULL
                    ) AS is_learned
                FROM cards
                JOIN decks ON decks.id = cards.deck_id
                ORDER BY cards.lemma, cards.id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _to_catalog_card(self, row: dict, *, now: datetime) -> CatalogCard:
        due_at = _parse_due_at(row["due_at"])
        metadata = {key: value for key, value in json.loads(row["metadata_json"]).items() if value}
        return CatalogCard(
            card_id=row["id"],
            deck_name=row["deck_name"],
            lemma=row["lemma"],
            translation=row["translation"],
            notes=row["notes"],
            metadata=metadata,
            due_text=_format_due_text(due_at, now=now, is_learned=bool(row["is_learned"])),
            state_text="learned" if row["is_learned"] else "new",
            edit_path=f"/cards/{row['id']}/edit",
        )


def _deck_options(decks) -> list[CatalogDeckOption]:
    options = [CatalogDeckOption(value="all", label="Все колоды")]
    options.extend(CatalogDeckOption(value=str(deck.id), label=deck.name) for deck in decks)
    return options


def _matches_filters(
    row: dict,
    *,
    now: datetime,
    deck: str,
    status: str,
    search_scope: str,
    query: str,
) -> bool:
    if deck != "all" and str(row["deck_id"]) != deck:
        return False
    if not _matches_status(row, now=now, status=status):
        return False
    return _matches_search(row, scope=search_scope, query=query)


def _matches_status(row: dict, *, now: datetime, status: str) -> bool:
    is_learned = bool(row["is_learned"])
    due_at = _parse_due_at(row["due_at"])
    is_due = is_learned and due_at is not None and due_at <= now.astimezone(UTC)
    if status == "due":
        return is_due
    if status == "new":
        return not is_learned
    if status == "learned":
        return is_learned
    return True


def _matches_search(row: dict, *, scope: str, query: str) -> bool:
    needle = query.casefold()
    if not needle:
        return True
    if scope == "czech":
        return needle in row["lemma"].casefold()
    if scope == "russian":
        return needle in row["translation"].casefold()
    haystacks = (row["lemma"], row["translation"], row["notes"])
    return any(needle in value.casefold() for value in haystacks)


def _parse_due_at(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _format_due_text(due_at: datetime | None, *, now: datetime, is_learned: bool) -> str:
    if not due_at:
        return "Без расписания"
    if not is_learned:
        return "Новая карточка"
    if due_at <= now.astimezone(UTC):
        return "К повторению сейчас"
    return due_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
