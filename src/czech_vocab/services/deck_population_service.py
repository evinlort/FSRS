from dataclasses import dataclass
from pathlib import Path
from random import sample
from typing import Callable

from czech_vocab.repositories import (
    CardRecord,
    CardRepository,
    DeckPopulationDraftRecord,
    DeckPopulationDraftRepository,
)
from czech_vocab.services.deck_settings_service import DeckSettingsService

ALLOWED_MODES = {"random", "manual", "mixed"}
ALLOWED_SEARCH_SCOPES = {"czech", "russian"}


@dataclass(frozen=True)
class AvailablePoolCard:
    card_id: int
    lemma: str
    translation: str
    notes: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class DeckPopulationSelection:
    cards: list[AvailablePoolCard]
    manual_cards: list[AvailablePoolCard]
    random_cards: list[AvailablePoolCard]
    requested_count: int
    random_fill_count: int
    manual_shortfall: bool
    insufficient_pool: bool


class DeckPopulationService:
    def __init__(
        self,
        database_path: Path,
        *,
        sampler: Callable[[list[CardRecord], int], list[CardRecord]] | None = None,
    ) -> None:
        self._repository = CardRepository(database_path)
        self._draft_repository = DeckPopulationDraftRepository(database_path)
        self._deck_settings = DeckSettingsService(database_path)
        self._sampler = sampler or _sample_cards

    def get_default_target_count(self) -> int:
        return self._deck_settings.get_app_settings().default_target_deck_card_count

    def search_available_cards(self, *, search_in: str, query: str) -> list[AvailablePoolCard]:
        scope = _validate_search_scope(search_in)
        needle = query.strip().casefold()
        return [
            _to_available_card(card)
            for card in self._repository.list_available_cards()
            if _matches_search(card, search_in=scope, needle=needle)
        ]

    def build_selection(
        self,
        *,
        requested_count: int,
        manual_card_ids: list[int],
        mode: str,
    ) -> DeckPopulationSelection:
        count = _validate_requested_count(requested_count)
        normalized_mode = _validate_mode(mode)
        if len(set(manual_card_ids)) != len(manual_card_ids):
            raise ValueError("Manual selection cannot contain duplicate cards.")
        if len(manual_card_ids) > count:
            raise ValueError("Manual selection cannot exceed the requested count.")

        available_cards = self._repository.list_available_cards()
        available_by_id = {card.id: card for card in available_cards}
        manual_cards = []
        for card_id in manual_card_ids:
            card = available_by_id.get(card_id)
            if card is None:
                raise ValueError("Selected cards must still be available.")
            manual_cards.append(card)

        random_cards: list[CardRecord] = []
        if normalized_mode in {"random", "mixed"}:
            remaining_count = max(count - len(manual_cards), 0)
            random_pool = [card for card in available_cards if card.id not in set(manual_card_ids)]
            random_cards = _dedupe_cards(
                self._sampler(random_pool, min(remaining_count, len(random_pool)))
            )

        final_cards = manual_cards + random_cards
        return DeckPopulationSelection(
            cards=[_to_available_card(card) for card in final_cards],
            manual_cards=[_to_available_card(card) for card in manual_cards],
            random_cards=[_to_available_card(card) for card in random_cards],
            requested_count=count,
            random_fill_count=len(random_cards),
            manual_shortfall=normalized_mode != "random" and len(manual_cards) < count,
            insufficient_pool=len(final_cards) < count,
        )

    def create_draft(
        self,
        *,
        flow_type: str,
        deck_id: int | None,
        deck_name: str | None,
        requested_count: int,
        mode: str,
        save_default_count: bool,
        selected_card_ids: list[int],
        search_in: str,
        query: str,
        page: int,
    ) -> DeckPopulationDraftRecord:
        return self._draft_repository.create_draft(
            flow_type=flow_type,
            deck_id=deck_id,
            deck_name=deck_name,
            requested_count=_validate_requested_count(requested_count),
            mode=_validate_mode(mode),
            save_default_count=save_default_count,
            selected_card_ids=selected_card_ids,
            search_in=_validate_search_scope(search_in),
            query_text=query.strip(),
            page=max(page, 1),
        )

    def get_draft(self, token: str) -> DeckPopulationDraftRecord | None:
        return self._draft_repository.get_draft(token)

    def update_draft(
        self,
        *,
        token: str,
        selected_card_ids: list[int],
        search_in: str,
        query: str,
        page: int,
    ) -> DeckPopulationDraftRecord:
        return self._draft_repository.update_draft(
            token=token,
            selected_card_ids=selected_card_ids,
            search_in=_validate_search_scope(search_in),
            query_text=query.strip(),
            page=max(page, 1),
        )

    def delete_draft(self, token: str) -> None:
        self._draft_repository.delete_draft(token)


def _matches_search(card: CardRecord, *, search_in: str, needle: str) -> bool:
    if not needle:
        return True
    if search_in == "czech":
        return needle in card.lemma.casefold()
    return needle in card.translation.casefold()


def _to_available_card(card: CardRecord) -> AvailablePoolCard:
    return AvailablePoolCard(
        card_id=card.id,
        lemma=card.lemma,
        translation=card.translation,
        notes=card.notes,
        metadata=card.metadata,
    )


def _validate_mode(mode: str) -> str:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported population mode: {mode}")
    return mode


def _validate_requested_count(requested_count: int) -> int:
    if requested_count < 1:
        raise ValueError("Requested count must be at least 1.")
    return requested_count


def _validate_search_scope(search_in: str) -> str:
    if search_in not in ALLOWED_SEARCH_SCOPES:
        raise ValueError(f"Unsupported search scope: {search_in}")
    return search_in


def _sample_cards(cards: list[CardRecord], count: int) -> list[CardRecord]:
    if count <= 0:
        return []
    return sample(cards, count)


def _dedupe_cards(cards: list[CardRecord]) -> list[CardRecord]:
    seen_ids: set[int] = set()
    deduped: list[CardRecord] = []
    for card in cards:
        if card.id in seen_ids:
            continue
        seen_ids.add(card.id)
        deduped.append(card)
    return deduped
