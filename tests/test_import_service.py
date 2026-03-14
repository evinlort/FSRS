from datetime import UTC, datetime
from pathlib import Path

from czech_vocab.services.import_service import ImportService


def test_preview_lifecycle_persists_rows_and_confirm_skips_duplicates(tmp_path: Path) -> None:
    database_path = tmp_path / "import.sqlite3"
    service = build_service(database_path)
    imported_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)

    first_preview = service.create_preview_from_text(
        "lemma_cs,translation_ru,notes\nkniha,книга,first\n",
        imported_at=imported_at,
        deck_name="Основная",
    )
    first_result = service.confirm_preview(first_preview.token)

    assert first_result.imported_count == 1
    assert first_result.duplicate_count == 0

    second_preview = service.create_preview_from_text(
        "lemma_cs,translation_ru,notes\nkniha,книга,second\n",
        imported_at=imported_at,
        deck_name="Основная",
    )

    assert second_preview.duplicate_count == 1
    assert second_preview.token is not None

    second_result = service.confirm_preview(second_preview.token)
    assert second_result.imported_count == 0
    assert second_result.duplicate_count == 1


def test_preview_reports_missing_headers_without_persisted_token(tmp_path: Path) -> None:
    service = build_service(tmp_path / "import.sqlite3")

    preview = service.create_preview_from_text(
        "notes\nmissing headers\n",
        imported_at=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
        deck_name="Основная",
    )

    assert preview.token is None
    assert preview.error_message == "Missing required headers: czech, russian"
    assert preview.ready_count == 0


def build_service(database_path: Path) -> ImportService:
    from czech_vocab.repositories import initialize_database

    initialize_database(database_path)
    return ImportService(database_path)
