from datetime import UTC, datetime
from pathlib import Path

import pytest

from czech_vocab.repositories import (
    CardCreate,
    CardRepository,
    DeckRepository,
    build_identity_key,
    initialize_database,
)
from czech_vocab.services import DeckCreateService


def test_start_create_flow_requires_available_cards_and_unique_deck_name(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-create.sqlite3"
    service = build_service(database_path)

    with pytest.raises(ValueError, match="available"):
        service.start_create_flow(
            deck_name="Глаголы",
            requested_count=3,
            mode="manual",
            save_default_count=False,
        )

    create_global_card(database_path, "kniha", "книга")
    token = service.start_create_flow(
        deck_name="Глаголы",
        requested_count=3,
        mode="manual",
        save_default_count=True,
    )

    assert service.get_draft_page(token).deck_name == "Глаголы"

    DeckRepository(database_path).create_deck(
        name="Глаголы",
        desired_retention=0.9,
        daily_new_limit=20,
    )
    with pytest.raises(ValueError, match="already exists"):
        service.confirm_create_flow(
            token=token,
            selected_card_ids=[1],
            search_in="czech",
            query="",
        )


def test_draft_page_supports_search_preserves_selection_and_warns_on_shortfall(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "deck-create.sqlite3"
    create_global_card(database_path, "kniha", "книга")
    create_global_card(database_path, "dum", "дом")
    create_global_card(database_path, "lod", "лодка")
    service = build_service(database_path)

    token = service.start_create_flow(
        deck_name="Глаголы",
        requested_count=3,
        mode="manual",
        save_default_count=False,
    )
    initial = service.get_draft_page(token)
    selected_id = initial.cards[0].card_id

    updated = service.update_draft_page(
        token=token,
        selected_card_ids=[selected_id],
        search_in="russian",
        query="лод",
    )

    assert updated.selected_count == 1
    assert updated.warning_message is not None
    assert updated.search_in == "russian"
    assert updated.query == "лод"
    assert [card.translation for card in updated.cards] == ["лодка"]
    assert updated.hidden_selected_ids == [selected_id]


def test_confirm_create_flow_supports_manual_and_mixed_modes(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-create.sqlite3"
    first = create_global_card(database_path, "kniha", "книга")
    second = create_global_card(database_path, "dum", "дом")
    third = create_global_card(database_path, "lod", "лодка")
    service = build_service(database_path)

    manual_token = service.start_create_flow(
        deck_name="Ручная",
        requested_count=3,
        mode="manual",
        save_default_count=False,
    )
    manual_result = service.confirm_create_flow(
        token=manual_token,
        selected_card_ids=[first.id, second.id],
        search_in="czech",
        query="",
    )
    assert manual_result.deck_name == "Ручная"
    assert manual_result.assigned_count == 2
    assert manual_result.insufficient_pool is True

    mixed_token = service.start_create_flow(
        deck_name="Смешанная",
        requested_count=2,
        mode="mixed",
        save_default_count=False,
    )
    mixed_result = service.confirm_create_flow(
        token=mixed_token,
        selected_card_ids=[third.id],
        search_in="czech",
        query="",
    )
    assert mixed_result.deck_name == "Смешанная"
    assert mixed_result.assigned_count == 1
    assert mixed_result.insufficient_pool is True


def test_confirm_create_flow_rejects_empty_manual_and_too_many_selected(tmp_path: Path) -> None:
    database_path = tmp_path / "deck-create.sqlite3"
    first = create_global_card(database_path, "kniha", "книга")
    second = create_global_card(database_path, "dum", "дом")
    service = build_service(database_path)

    manual_token = service.start_create_flow(
        deck_name="Ручная",
        requested_count=2,
        mode="manual",
        save_default_count=False,
    )
    with pytest.raises(ValueError, match="empty"):
        service.confirm_create_flow(
            token=manual_token,
            selected_card_ids=[],
            search_in="czech",
            query="",
        )

    mixed_token = service.start_create_flow(
        deck_name="Смешанная",
        requested_count=1,
        mode="mixed",
        save_default_count=False,
    )
    with pytest.raises(ValueError, match="exceed"):
        service.confirm_create_flow(
            token=mixed_token,
            selected_card_ids=[first.id, second.id],
            search_in="czech",
            query="",
        )


def build_service(database_path: Path) -> DeckCreateService:
    initialize_database(database_path)
    return DeckCreateService(database_path)


def create_global_card(database_path: Path, lemma: str, translation: str):
    initialize_database(database_path)
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
