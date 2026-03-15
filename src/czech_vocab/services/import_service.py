from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from czech_vocab.domain import FsrsScheduler
from czech_vocab.importers import MissingRequiredHeadersError, ParsedCsvRow, parse_vocabulary_csv
from czech_vocab.repositories import (
    CardCreate,
    CardRepository,
    ImportPreviewRepository,
    build_identity_key,
    build_lemma_key,
)

GLOBAL_BASE_NAME = "Глобальная база"


@dataclass(frozen=True)
class ImportPreview:
    token: str | None
    target_deck_name: str
    ready_count: int
    duplicate_count: int
    rejected_count: int
    rejected_messages: list[str]
    sample_rows: list[ParsedCsvRow]
    error_message: str | None = None


@dataclass(frozen=True)
class ImportResult:
    imported_count: int
    duplicate_count: int
    rejected_count: int
    target_deck_name: str
    rejected_messages: list[str]


class ImportService:
    def __init__(self, database_path: Path, *, scheduler: FsrsScheduler | None = None) -> None:
        self._repository = CardRepository(database_path)
        self._preview_repository = ImportPreviewRepository(database_path)
        self._scheduler = scheduler or FsrsScheduler()

    def create_preview_from_bytes(
        self,
        csv_bytes: bytes,
        *,
        imported_at: datetime | None = None,
    ) -> ImportPreview:
        try:
            csv_text = csv_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return _error_preview("Unable to decode CSV as UTF-8.")
        return self.create_preview_from_text(csv_text, imported_at=imported_at)

    def create_preview_from_text(
        self,
        csv_text: str,
        *,
        imported_at: datetime | None = None,
    ) -> ImportPreview:
        try:
            parsed = parse_vocabulary_csv(StringIO(csv_text))
        except MissingRequiredHeadersError as exc:
            return _error_preview(str(exc))
        review_time = imported_at.astimezone(UTC) if imported_at else datetime.now(UTC)
        ready_rows, duplicate_count = self._split_ready_rows(parsed.rows)
        rejected_messages = [
            f"Line {error.line_number}: {error.message}" for error in parsed.row_errors
        ]
        token = None
        if parsed.rows:
            record = self._preview_repository.create_preview(
                deck_name=GLOBAL_BASE_NAME,
                rows=[_row_payload(row) for row in parsed.rows],
                rejected_messages=rejected_messages,
                duplicate_count=duplicate_count,
                imported_at=review_time,
            )
            token = record.token
        return ImportPreview(
            token=token,
            target_deck_name=GLOBAL_BASE_NAME,
            ready_count=len(ready_rows),
            duplicate_count=duplicate_count,
            rejected_count=len(rejected_messages),
            rejected_messages=rejected_messages,
            sample_rows=ready_rows[:5],
        )

    def confirm_preview(self, preview_token: str) -> ImportResult:
        preview = self._preview_repository.get_preview(preview_token)
        if preview is None:
            raise LookupError("Preview not found")
        rows = [_stored_row_to_parsed(item) for item in preview.rows]
        ready_rows, duplicate_count = self._split_ready_rows(rows)
        imported_count = self._persist_rows(ready_rows, review_time=preview.imported_at)
        self._preview_repository.delete_preview(preview_token)
        return ImportResult(
            imported_count=imported_count,
            duplicate_count=duplicate_count,
            rejected_count=len(preview.rejected_messages),
            target_deck_name=preview.deck_name,
            rejected_messages=preview.rejected_messages,
        )

    def _persist_rows(
        self,
        rows: list[ParsedCsvRow],
        *,
        review_time: datetime,
    ) -> int:
        imported_count = 0
        with self._repository.connect() as connection:
            for row in rows:
                created_card = self._repository.create_card(
                    CardCreate(
                        identity_key=build_identity_key(row.lemma, row.translation),
                        lemma=row.lemma,
                        translation=row.translation,
                        notes=row.notes,
                        metadata=row.metadata,
                        fsrs_state={},
                        due_at=None,
                        last_review_at=None,
                        deck_id=None,
                    ),
                    connection=connection,
                )
                default_state = self._scheduler.create_default_state(
                    card_id=created_card.id,
                    now=review_time,
                )
                scheduled_card = self._scheduler.deserialize_card(default_state)
                self._repository.update_schedule_state(
                    card_id=created_card.id,
                    fsrs_state=default_state,
                    due_at=scheduled_card.due,
                    last_review_at=scheduled_card.last_review,
                    connection=connection,
                )
                imported_count += 1
        return imported_count

    def _split_ready_rows(
        self,
        rows: list[ParsedCsvRow],
    ) -> tuple[list[ParsedCsvRow], int]:
        seen_keys: set[str] = set()
        ready_rows: list[ParsedCsvRow] = []
        duplicate_count = 0
        for row in rows:
            lemma_key = build_lemma_key(row.lemma)
            existing = self._repository.get_card_by_lemma_key(lemma_key) is not None
            if existing or lemma_key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(lemma_key)
            ready_rows.append(row)
        return ready_rows, duplicate_count


def _error_preview(message: str) -> ImportPreview:
    return ImportPreview(
        token=None,
        target_deck_name=GLOBAL_BASE_NAME,
        ready_count=0,
        duplicate_count=0,
        rejected_count=0,
        rejected_messages=[],
        sample_rows=[],
        error_message=message,
    )


def _row_payload(row: ParsedCsvRow) -> dict[str, object]:
    return {
        "line_number": row.line_number,
        "lemma": row.lemma,
        "translation": row.translation,
        "notes": row.notes,
        "metadata": row.metadata,
    }


def _stored_row_to_parsed(payload: dict[str, object]) -> ParsedCsvRow:
    return ParsedCsvRow(
        line_number=payload["line_number"],
        lemma=payload["lemma"],
        translation=payload["translation"],
        notes=payload["notes"],
        metadata=payload["metadata"],
    )
