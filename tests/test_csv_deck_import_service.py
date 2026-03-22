from datetime import UTC, datetime
from pathlib import Path

import pytest

from czech_vocab.repositories import CardCreate, CardRepository, DeckRepository, build_identity_key
from czech_vocab.services import CsvDeckImportService


def test_preview_and_confirm_create_deck_from_new_rows(tmp_path: Path) -> None:
    database_path = tmp_path / 'csv-deck-import.sqlite3'
    service = build_service(database_path)
    imported_at = datetime(2026, 3, 22, 10, 0, tzinfo=UTC)

    preview = service.create_preview_from_text(
        deck_name='CSV deck',
        csv_text='lemma_cs,translation_ru,notes\nkniha,книга,common noun\nvlak,поезд,transport\n',
        imported_at=imported_at,
    )

    assert preview.accepted_count == 2
    assert preview.created_count == 2
    assert preview.updated_count == 0
    assert preview.duplicate_count == 0
    assert preview.token is not None

    result = service.confirm_preview(preview.token)

    assert result.deck_name == 'CSV deck'
    assert result.assigned_count == 2
    assert result.created_count == 2
    assert result.updated_count == 0

    deck = DeckRepository(database_path).get_deck_by_name('CSV deck')
    assert deck is not None
    repository = CardRepository(database_path)
    kniha = repository.get_card_by_lemma_key('kniha')
    vlak = repository.get_card_by_lemma_key('vlak')
    assert kniha is not None and kniha.deck_id == deck.id and kniha.due_at is not None
    assert vlak is not None and vlak.deck_id == deck.id and vlak.due_at is not None


def test_confirm_preview_updates_existing_card_moves_deck_and_preserves_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / 'csv-deck-import.sqlite3'
    service = build_service(database_path)
    repository = CardRepository(database_path)
    deck_repository = DeckRepository(database_path)
    source_deck = deck_repository.create_deck(
        name='Старая колода',
        desired_retention=0.9,
        daily_new_limit=20,
    )
    due_at = datetime(2026, 3, 30, 12, 0, tzinfo=UTC)
    existing = repository.create_card(
        CardCreate(
            identity_key=build_identity_key('kniha', 'книга'),
            lemma='kniha',
            translation='книга',
            notes='old note',
            metadata={'level': 'A1', 'topic': 'reading'},
            fsrs_state={'state': 'review', 'stability': 5.2},
            due_at=due_at,
            last_review_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            deck_id=source_deck.id,
        )
    )
    repository.insert_review_log(
        card_id=existing.id,
        rating='Good',
        reviewed_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
        review_duration_seconds=14,
    )

    preview = service.create_preview_from_text(
        deck_name='Новая колода',
        csv_text='lemma_cs,translation_ru,notes,source\nkniha,издание,new note,csv\n',
        imported_at=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
    )

    assert preview.accepted_count == 1
    assert preview.created_count == 0
    assert preview.updated_count == 1
    assert preview.token is not None

    result = service.confirm_preview(preview.token)

    assert result.assigned_count == 1
    assert result.created_count == 0
    assert result.updated_count == 1
    updated = repository.get_card_by_id(existing.id)
    target_deck = deck_repository.get_deck_by_name('Новая колода')
    assert updated is not None
    assert target_deck is not None
    assert updated.deck_id == target_deck.id
    assert updated.translation == 'издание'
    assert updated.notes == 'new note'
    assert updated.metadata == {'level': 'A1', 'topic': 'reading', 'source': 'csv'}
    assert updated.identity_key == build_identity_key('kniha', 'издание')
    assert updated.fsrs_state == {'state': 'review', 'stability': 5.2}
    assert updated.due_at == due_at
    assert len(repository.list_review_logs(existing.id)) == 1


def test_preview_without_accepted_rows_has_no_confirm_token(tmp_path: Path) -> None:
    database_path = tmp_path / 'csv-deck-import.sqlite3'
    service = build_service(database_path)

    preview = service.create_preview_from_text(
        deck_name='Пустая колода',
        csv_text='lemma_cs,translation_ru\n,книга\n',
        imported_at=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
    )

    assert preview.token is None
    assert preview.accepted_count == 0
    assert preview.rejected_count == 1
    assert preview.rejected_messages == ['Line 2: Missing required value: czech']


def test_duplicate_deck_name_is_rejected_during_preview(tmp_path: Path) -> None:
    database_path = tmp_path / 'csv-deck-import.sqlite3'
    service = build_service(database_path)
    DeckRepository(database_path).create_deck(
        name='CSV deck',
        desired_retention=0.9,
        daily_new_limit=20,
    )

    with pytest.raises(ValueError, match='already exists'):
        service.create_preview_from_text(
            deck_name='CSV deck',
            csv_text='lemma_cs,translation_ru\nkniha,книга\n',
            imported_at=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        )


def build_service(database_path: Path) -> CsvDeckImportService:
    from czech_vocab.repositories import initialize_database

    initialize_database(database_path)
    return CsvDeckImportService(database_path)
