from datetime import UTC, datetime
from pathlib import Path

import pytest

from czech_vocab.repositories import CardCreate, CardRepository, initialize_database
from czech_vocab.repositories.records import build_identity_key
from czech_vocab.services import DeckPopulationService, DeckSettingsService


def test_available_pool_only_returns_unassigned_cards_and_supports_search(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-population.sqlite3"
    initialize_database(database_path)
    service = DeckPopulationService(database_path)
    deck_service = DeckSettingsService(database_path)
    extra_deck = deck_service.create_deck("Путешествия")

    kniha = create_card(database_path, "kniha", "книга", deck_id=None)
    lod = create_card(database_path, "lod", "лодка", deck_id=None)
    create_card(database_path, "vlak", "поезд", deck_id=extra_deck.id)

    czech_results = service.search_available_cards(search_in="czech", query="lod")
    russian_results = service.search_available_cards(search_in="russian", query="кни")

    assert service.get_default_target_count() == 20
    assert [card.card_id for card in czech_results] == [lod.id]
    assert [card.card_id for card in russian_results] == [kniha.id]


def test_mixed_selection_keeps_manual_cards_and_fills_the_rest_randomly(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-population.sqlite3"
    initialize_database(database_path)
    service = DeckPopulationService(database_path, sampler=pick_last_cards)

    auto = create_card(database_path, "auto", "машина", deck_id=None)
    dum = create_card(database_path, "dum", "дом", deck_id=None)
    kniha = create_card(database_path, "kniha", "книга", deck_id=None)
    les = create_card(database_path, "les", "лес", deck_id=None)

    selection = service.build_selection(
        requested_count=3,
        manual_card_ids=[kniha.id],
        mode="mixed",
    )

    assert [card.card_id for card in selection.manual_cards] == [kniha.id]
    assert [card.card_id for card in selection.random_cards] == [dum.id, les.id]
    assert [card.card_id for card in selection.cards] == [kniha.id, dum.id, les.id]
    assert selection.manual_shortfall is True
    assert selection.insufficient_pool is False
    assert auto.id not in [card.card_id for card in selection.random_cards]


def test_random_selection_uses_available_subset_when_pool_is_too_small(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-population.sqlite3"
    initialize_database(database_path)
    service = DeckPopulationService(database_path, sampler=pick_last_cards)

    first = create_card(database_path, "prvni", "первый", deck_id=None)
    second = create_card(database_path, "druhy", "второй", deck_id=None)

    selection = service.build_selection(
        requested_count=4,
        manual_card_ids=[],
        mode="random",
    )

    assert [card.card_id for card in selection.cards] == [second.id, first.id]
    assert selection.random_fill_count == 2
    assert selection.insufficient_pool is True
    assert selection.manual_shortfall is False


def test_selection_rejects_too_many_manual_cards_duplicates_and_unavailable_ids(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "deck-population.sqlite3"
    initialize_database(database_path)
    service = DeckPopulationService(database_path)
    deck_service = DeckSettingsService(database_path)
    extra_deck = deck_service.create_deck("Путешествия")

    available = create_card(database_path, "kniha", "книга", deck_id=None)
    second = create_card(database_path, "les", "лес", deck_id=None)
    assigned = create_card(database_path, "vlak", "поезд", deck_id=extra_deck.id)

    with pytest.raises(ValueError, match="cannot exceed"):
        service.build_selection(
            requested_count=1,
            manual_card_ids=[available.id, second.id],
            mode="manual",
        )

    with pytest.raises(ValueError, match="duplicate"):
        service.build_selection(
            requested_count=2,
            manual_card_ids=[available.id, available.id],
            mode="manual",
        )

    with pytest.raises(ValueError, match="available"):
        service.build_selection(
            requested_count=1,
            manual_card_ids=[assigned.id],
            mode="manual",
        )


def test_draft_lifecycle_persists_selection_state_server_side(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-population.sqlite3"
    initialize_database(database_path)
    service = DeckPopulationService(database_path)

    created = service.create_draft(
        flow_type="create",
        deck_id=None,
        deck_name="Глаголы",
        requested_count=5,
        mode="mixed",
        save_default_count=True,
        selected_card_ids=[1, 2],
        search_in="czech",
        query="kni",
        page=2,
    )

    assert created.deck_name == "Глаголы"
    assert created.selected_card_ids == [1, 2]
    assert created.save_default_count is True

    updated = service.update_draft(
        token=created.token,
        selected_card_ids=[2, 3],
        search_in="russian",
        query="кни",
        page=4,
    )

    fetched = service.get_draft(updated.token)
    assert fetched is not None
    assert fetched.selected_card_ids == [2, 3]
    assert fetched.search_in == "russian"
    assert fetched.query_text == "кни"
    assert fetched.page == 4

    service.delete_draft(updated.token)
    assert service.get_draft(updated.token) is None


def create_card(database_path: Path, lemma: str, translation: str, *, deck_id: int | None):
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
            deck_id=deck_id,
        )
    )


def pick_last_cards(cards, count: int):
    return cards[-count:]
