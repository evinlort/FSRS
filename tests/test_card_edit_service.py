from datetime import UTC, datetime
from pathlib import Path

import pytest

from czech_vocab.domain import FsrsScheduler
from czech_vocab.importers.csv_parser import normalize_header
from czech_vocab.repositories import (
    CardCreate,
    CardRepository,
    build_identity_key,
    initialize_database,
)
from czech_vocab.services import CardEditService, DeckSettingsService


def test_update_card_changes_all_visible_fields_and_normalizes_metadata_keys(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "edit.sqlite3"
    service = build_service(database_path)
    card = create_card(database_path, "kniha", "книга", "old note")
    second_deck = DeckSettingsService(database_path).create_deck("Путешествия")

    updated = service.update_card(
        card_id=card.id,
        deck_id=second_deck.id,
        lemma="kniha nova",
        translation="новая книга",
        notes="fresh note",
        metadata_rows=[
            (" CEFR Level ", "A2"),
            ("topic-name", "travel"),
            ("", "ignored"),
            ("empty", ""),
        ],
    )

    assert updated.deck_id == second_deck.id
    assert updated.lemma == "kniha nova"
    assert updated.translation == "новая книга"
    assert updated.notes == "fresh note"
    assert updated.metadata == {
        normalize_header(" CEFR Level "): "A2",
        normalize_header("topic-name"): "travel",
    }


def test_update_card_rejects_blank_required_fields(tmp_path: Path) -> None:
    database_path = tmp_path / "edit.sqlite3"
    service = build_service(database_path)
    card = create_card(database_path, "pes", "собака", "animal")

    with pytest.raises(ValueError, match="Заполните чешское слово и перевод."):
        service.update_card(
            card_id=card.id,
            deck_id=card.deck_id,
            lemma="",
            translation="собака",
            notes="animal",
            metadata_rows=[],
        )


def test_update_card_rejects_duplicate_identity_in_target_deck(tmp_path: Path) -> None:
    database_path = tmp_path / "edit.sqlite3"
    service = build_service(database_path)
    first = create_card(database_path, "pes", "собака", "first")
    second = create_card(database_path, "kocka", "кошка", "second")

    with pytest.raises(
        ValueError,
        match="В этой колоде уже есть карточка с таким словом и переводом.",
    ):
        service.update_card(
            card_id=second.id,
            deck_id=first.deck_id,
            lemma="pes",
            translation="собака",
            notes="duplicate",
            metadata_rows=[],
        )


def build_service(database_path: Path) -> CardEditService:
    initialize_database(database_path)
    return CardEditService(database_path)


def create_card(database_path: Path, lemma: str, translation: str, notes: str):
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    due_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = repository.create_card(
        CardCreate(
            identity_key=build_identity_key(lemma, translation),
            lemma=lemma,
            translation=translation,
            notes=notes,
            metadata={"topic": "edit"},
            fsrs_state=scheduler.create_default_state(card_id=0, now=due_at),
            due_at=due_at,
            last_review_at=None,
        )
    )
    return repository.get_card_by_id(created.id)
