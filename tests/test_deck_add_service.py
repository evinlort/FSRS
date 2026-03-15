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


def test_add_manual_and_mixed_cards_to_existing_deck(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-add.sqlite3"
    initialize_database(database_path)
    settings = DeckSettingsService(database_path)
    deck = settings.create_deck("Путешествия")
    other = settings.create_deck("Работа")
    service = DeckPopulationService(database_path, sampler=pick_last_cards)

    selected = create_card(database_path, "auto", "машина")
    random_fill = create_card(database_path, "dum", "дом")
    create_card(database_path, "lod", "лодка")
    blocked = create_card(database_path, "vlak", "поезд")
    service.add_random_cards_to_deck(
        deck_id=other.id,
        requested_count=1,
        save_default_count=False,
        manual_card_ids=[blocked.id],
        mode="manual",
    )

    manual_result = service.add_random_cards_to_deck(
        deck_id=deck.id,
        requested_count=3,
        save_default_count=False,
        manual_card_ids=[selected.id],
        mode="manual",
    )
    assert manual_result.assigned_count == 1
    assert manual_result.insufficient_pool is True

    mixed_result = service.add_random_cards_to_deck(
        deck_id=deck.id,
        requested_count=2,
        save_default_count=False,
        manual_card_ids=[random_fill.id],
        mode="mixed",
    )
    assert mixed_result.assigned_count == 2
    assert mixed_result.insufficient_pool is False

    with CardRepository(database_path).connect() as connection:
        linked_ids = {
            row[0]
            for row in connection.execute(
                "SELECT card_id FROM deck_cards WHERE deck_id = ?",
                (deck.id,),
            ).fetchall()
        }
    assert selected.id in linked_ids
    assert random_fill.id in linked_ids
    assert blocked.id not in linked_ids


def test_add_random_cards_to_existing_deck_rejects_invalid_manual_state(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-add.sqlite3"
    initialize_database(database_path)
    settings = DeckSettingsService(database_path)
    deck = settings.create_deck("Путешествия")
    other = settings.create_deck("Работа")
    service = DeckPopulationService(database_path)

    first = create_card(database_path, "auto", "машина")
    blocked = create_card(database_path, "vlak", "поезд")
    service.add_random_cards_to_deck(
        deck_id=other.id,
        requested_count=1,
        save_default_count=False,
        manual_card_ids=[blocked.id],
        mode="manual",
    )

    with pytest.raises(ValueError, match="available"):
        service.add_random_cards_to_deck(
            deck_id=deck.id,
            requested_count=1,
            save_default_count=False,
            manual_card_ids=[blocked.id],
            mode="manual",
        )

    with pytest.raises(ValueError, match="cannot exceed"):
        service.add_random_cards_to_deck(
            deck_id=deck.id,
            requested_count=1,
            save_default_count=False,
            manual_card_ids=[first.id, blocked.id],
            mode="mixed",
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
