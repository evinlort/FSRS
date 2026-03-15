from datetime import UTC, datetime
from pathlib import Path

import pytest

from czech_vocab.repositories import (
    CardCreate,
    CardRepository,
    build_identity_key,
    initialize_database,
)
from czech_vocab.services import DeckPopulationService, DeckSettingsService


def test_add_random_cards_to_existing_deck_assigns_available_subset_and_updates_defaults(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "deck-add.sqlite3"
    initialize_database(database_path)
    settings = DeckSettingsService(database_path)
    deck = settings.create_deck("Путешествия")
    service = DeckPopulationService(database_path, sampler=pick_last_cards)

    create_card(database_path, "auto", "машина")
    create_card(database_path, "dum", "дом")

    result = service.add_random_cards_to_deck(
        deck_id=deck.id,
        requested_count=3,
        save_default_count=True,
    )

    assert result.deck_id == deck.id
    assert result.deck_name == "Путешествия"
    assert result.assigned_count == 2
    assert result.insufficient_pool is True
    assert settings.get_app_settings().default_target_deck_card_count == 3


def test_add_random_cards_to_existing_deck_blocks_missing_deck_and_empty_pool(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "deck-add.sqlite3"
    initialize_database(database_path)
    deck = DeckSettingsService(database_path).create_deck("Путешествия")
    service = DeckPopulationService(database_path)

    with pytest.raises(LookupError, match="Deck not found"):
        service.add_random_cards_to_deck(
            deck_id=999,
            requested_count=1,
            save_default_count=False,
        )

    with pytest.raises(ValueError, match="available"):
        service.add_random_cards_to_deck(
            deck_id=deck.id,
            requested_count=1,
            save_default_count=False,
        )


def create_card(database_path: Path, lemma: str, translation: str):
    repository = CardRepository(database_path)
    now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    return repository.create_card(
        CardCreate(
            identity_key=build_identity_key(lemma, translation),
            lemma=lemma,
            translation=translation,
            notes="",
            metadata={},
            fsrs_state={},
            due_at=now,
            last_review_at=None,
            deck_id=None,
        )
    )


def pick_last_cards(cards, count: int):
    return cards[-count:]
