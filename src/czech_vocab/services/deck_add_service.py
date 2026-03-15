from dataclasses import dataclass
from pathlib import Path

from czech_vocab.repositories import DeckRepository
from czech_vocab.services.deck_population_service import (
    AvailablePoolCard,
    DeckPopulationService,
)

MANUAL_MODE = "manual"
MIXED_MODE = "mixed"


@dataclass(frozen=True)
class DeckAddSelectionCard:
    card_id: int
    lemma: str
    translation: str
    selected: bool


@dataclass(frozen=True)
class DeckAddDraftPage:
    token: str
    deck_id: int
    deck_name: str
    requested_count: int
    mode: str
    save_default_count: bool
    search_in: str
    query: str
    selected_count: int
    cards: list[DeckAddSelectionCard]
    hidden_selected_ids: list[int]
    warning_message: str | None


class DeckAddService:
    def __init__(self, database_path: Path) -> None:
        self._population = DeckPopulationService(database_path)
        self._decks = DeckRepository(database_path)

    def start_add_flow(
        self,
        *,
        deck_id: int,
        requested_count: int,
        mode: str,
        save_default_count: bool,
    ) -> str:
        deck = self._decks.get_deck_by_id(deck_id)
        if deck is None:
            raise LookupError(f"Deck not found: {deck_id}")
        if self._population.count_available_cards() == 0:
            raise ValueError("No available cards.")
        draft = self._population.create_draft(
            flow_type="add",
            deck_id=deck.id,
            deck_name=deck.name,
            requested_count=requested_count,
            mode=mode,
            save_default_count=save_default_count,
            selected_card_ids=[],
            search_in="czech",
            query="",
            page=1,
        )
        return draft.token

    def get_draft_page(self, token: str) -> DeckAddDraftPage:
        draft = self._require_draft(token)
        return self._build_page(draft)

    def update_draft_page(
        self,
        *,
        token: str,
        selected_card_ids: list[int],
        search_in: str,
        query: str,
    ) -> DeckAddDraftPage:
        draft = self._require_draft(token)
        self._population.build_selection(
            requested_count=draft.requested_count,
            manual_card_ids=selected_card_ids,
            mode=draft.mode,
        )
        updated = self._population.update_draft(
            token=token,
            selected_card_ids=selected_card_ids,
            search_in=search_in,
            query=query,
            page=1,
        )
        return self._build_page(updated)

    def confirm_add_flow(
        self,
        *,
        token: str,
        selected_card_ids: list[int],
        search_in: str,
        query: str,
    ):
        page = self.update_draft_page(
            token=token,
            selected_card_ids=selected_card_ids,
            search_in=search_in,
            query=query,
        )
        if page.mode == MANUAL_MODE and page.selected_count == 0:
            raise ValueError("Manual add cannot be empty.")
        draft = self._require_draft(token)
        result = self._population.add_random_cards_to_deck(
            deck_id=draft.deck_id or 0,
            requested_count=draft.requested_count,
            save_default_count=draft.save_default_count,
            manual_card_ids=selected_card_ids,
            mode=draft.mode,
        )
        self._population.delete_draft(token)
        return result

    def _build_page(self, draft) -> DeckAddDraftPage:
        selected_ids = set(draft.selected_card_ids)
        visible = self._population.search_available_cards(
            search_in=draft.search_in,
            query=draft.query_text,
        )
        visible_ids = {card.card_id for card in visible}
        return DeckAddDraftPage(
            token=draft.token,
            deck_id=draft.deck_id or 0,
            deck_name=draft.deck_name or "",
            requested_count=draft.requested_count,
            mode=draft.mode,
            save_default_count=draft.save_default_count,
            search_in=draft.search_in,
            query=draft.query_text,
            selected_count=len(draft.selected_card_ids),
            cards=[_to_selection_card(card, selected_ids) for card in visible],
            hidden_selected_ids=[
                card_id for card_id in draft.selected_card_ids if card_id not in visible_ids
            ],
            warning_message=_warning_message(
                draft.mode,
                len(draft.selected_card_ids),
                draft.requested_count,
            ),
        )

    def _require_draft(self, token: str):
        draft = self._population.get_draft(token)
        if draft is None or draft.flow_type != "add":
            raise LookupError(f"Draft not found: {token}")
        return draft


def _to_selection_card(card: AvailablePoolCard, selected_ids: set[int]) -> DeckAddSelectionCard:
    return DeckAddSelectionCard(
        card_id=card.card_id,
        lemma=card.lemma,
        translation=card.translation,
        selected=card.card_id in selected_ids,
    )


def _warning_message(mode: str, selected_count: int, requested_count: int) -> str | None:
    if selected_count >= requested_count:
        return None
    if mode == MIXED_MODE:
        return "Остальные карточки будут выбраны случайно при добавлении в колоду."
    return "В колоду будет добавлено выбранное количество карточек."
