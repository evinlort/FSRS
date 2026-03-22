import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from czech_vocab.domain import FsrsScheduler
from czech_vocab.importers import MissingRequiredHeadersError, ParsedCsvRow, parse_vocabulary_csv
from czech_vocab.repositories import (
    CardCreate,
    CardRepository,
    DeckCardRepository,
    DeckRepository,
    ImportPreviewRepository,
    build_identity_key,
    build_lemma_key,
)
from czech_vocab.services.deck_settings_service import DeckSettingsService


@dataclass(frozen=True)
class CsvDeckImportPreview:
    token: str | None
    target_deck_name: str
    accepted_count: int
    created_count: int
    updated_count: int
    duplicate_count: int
    rejected_count: int
    rejected_messages: list[str]
    sample_rows: list[ParsedCsvRow]
    error_message: str | None = None


@dataclass(frozen=True)
class CsvDeckImportResult:
    deck_id: int
    deck_name: str
    assigned_count: int
    created_count: int
    updated_count: int
    duplicate_count: int
    rejected_count: int
    rejected_messages: list[str]


@dataclass(frozen=True)
class _RowSummary:
    rows: list[ParsedCsvRow]
    duplicate_count: int
    created_count: int
    updated_count: int


class CsvDeckImportService:
    def __init__(self, database_path: Path, *, scheduler: FsrsScheduler | None = None) -> None:
        self._repository = CardRepository(database_path)
        self._deck_cards = DeckCardRepository(database_path)
        self._decks = DeckRepository(database_path)
        self._settings = DeckSettingsService(database_path)
        self._preview_repository = ImportPreviewRepository(database_path)
        self._scheduler = scheduler or FsrsScheduler()

    def create_preview_from_bytes(
        self,
        *,
        deck_name: str,
        csv_bytes: bytes,
        imported_at: datetime | None = None,
    ) -> CsvDeckImportPreview:
        _validate_deck_name(deck_name)
        try:
            csv_text = csv_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            return _error_preview(deck_name, 'Unable to decode CSV as UTF-8.')
        return self.create_preview_from_text(
            deck_name=deck_name,
            csv_text=csv_text,
            imported_at=imported_at,
        )

    def create_preview_from_text(
        self,
        *,
        deck_name: str,
        csv_text: str,
        imported_at: datetime | None = None,
    ) -> CsvDeckImportPreview:
        clean_name = _validate_deck_name(deck_name)
        if self._decks.get_deck_by_name(clean_name) is not None:
            raise ValueError('Deck already exists.')
        try:
            parsed = parse_vocabulary_csv(StringIO(csv_text))
        except MissingRequiredHeadersError as exc:
            return _error_preview(clean_name, str(exc))
        review_time = imported_at.astimezone(UTC) if imported_at else datetime.now(UTC)
        summary = self._summarize_rows(parsed.rows)
        rejected_messages = [
            f'Line {error.line_number}: {error.message}' for error in parsed.row_errors
        ]
        token = None
        if summary.rows:
            record = self._preview_repository.create_preview(
                deck_name=clean_name,
                rows=[_row_payload(row) for row in summary.rows],
                rejected_messages=rejected_messages,
                duplicate_count=summary.duplicate_count,
                imported_at=review_time,
            )
            token = record.token
        return CsvDeckImportPreview(
            token=token,
            target_deck_name=clean_name,
            accepted_count=len(summary.rows),
            created_count=summary.created_count,
            updated_count=summary.updated_count,
            duplicate_count=summary.duplicate_count,
            rejected_count=len(rejected_messages),
            rejected_messages=rejected_messages,
            sample_rows=summary.rows[:5],
        )

    def confirm_preview(self, preview_token: str) -> CsvDeckImportResult:
        preview = self._preview_repository.get_preview(preview_token)
        if preview is None:
            raise LookupError('Preview not found')
        rows = [_stored_row_to_parsed(item) for item in preview.rows]
        if not rows:
            raise ValueError('No accepted rows.')
        clean_name = _validate_deck_name(preview.deck_name)
        settings = self._settings.get_app_settings()
        created_count = 0
        updated_count = 0
        with self._repository.connect() as connection:
            if self._decks.get_deck_by_name(clean_name) is not None:
                raise ValueError('Deck already exists.')
            try:
                deck = self._decks.create_deck(
                    name=clean_name,
                    desired_retention=settings.default_desired_retention,
                    daily_new_limit=settings.default_daily_new_limit,
                    connection=connection,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError('Deck already exists.') from exc
            for row in rows:
                existing = self._repository.get_card_by_lemma_key(
                    build_lemma_key(row.lemma),
                    connection=connection,
                )
                if existing is None:
                    self._create_card_from_row(
                        row=row,
                        deck_id=deck.id,
                        review_time=preview.imported_at,
                        connection=connection,
                    )
                    created_count += 1
                    continue
                self._repository.update_imported_content(
                    card_id=existing.id,
                    lemma=row.lemma,
                    translation=row.translation,
                    notes=row.notes,
                    metadata=_merged_metadata(existing.metadata, row.metadata),
                    connection=connection,
                )
                self._deck_cards.assign_card_to_deck(
                    card_id=existing.id,
                    deck_id=deck.id,
                    connection=connection,
                )
                updated_count += 1
        self._preview_repository.delete_preview(preview_token)
        return CsvDeckImportResult(
            deck_id=deck.id,
            deck_name=deck.name,
            assigned_count=len(rows),
            created_count=created_count,
            updated_count=updated_count,
            duplicate_count=preview.duplicate_count,
            rejected_count=len(preview.rejected_messages),
            rejected_messages=preview.rejected_messages,
        )

    def _create_card_from_row(
        self,
        *,
        row: ParsedCsvRow,
        deck_id: int,
        review_time: datetime,
        connection,
    ) -> None:
        created = self._repository.create_card(
            CardCreate(
                identity_key=build_identity_key(row.lemma, row.translation),
                lemma=row.lemma,
                translation=row.translation,
                notes=row.notes,
                metadata=row.metadata,
                fsrs_state={},
                due_at=None,
                last_review_at=None,
                deck_id=deck_id,
            ),
            connection=connection,
        )
        default_state = self._scheduler.create_default_state(card_id=created.id, now=review_time)
        scheduled = self._scheduler.deserialize_card(default_state)
        self._repository.update_schedule_state(
            card_id=created.id,
            fsrs_state=default_state,
            due_at=scheduled.due,
            last_review_at=scheduled.last_review,
            connection=connection,
        )

    def _summarize_rows(self, rows: list[ParsedCsvRow]) -> _RowSummary:
        seen_keys: set[str] = set()
        accepted_rows: list[ParsedCsvRow] = []
        duplicate_count = 0
        created_count = 0
        updated_count = 0
        for row in rows:
            lemma_key = build_lemma_key(row.lemma)
            if lemma_key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(lemma_key)
            accepted_rows.append(row)
            if self._repository.get_card_by_lemma_key(lemma_key) is None:
                created_count += 1
            else:
                updated_count += 1
        return _RowSummary(
            rows=accepted_rows,
            duplicate_count=duplicate_count,
            created_count=created_count,
            updated_count=updated_count,
        )


def _validate_deck_name(deck_name: str) -> str:
    clean_name = deck_name.strip()
    if not clean_name:
        raise ValueError('Deck name is required.')
    return clean_name


def _merged_metadata(
    existing_metadata: dict[str, str],
    row_metadata: dict[str, str],
) -> dict[str, str]:
    merged = dict(existing_metadata)
    merged.update(row_metadata)
    return merged


def _error_preview(deck_name: str, message: str) -> CsvDeckImportPreview:
    return CsvDeckImportPreview(
        token=None,
        target_deck_name=deck_name.strip(),
        accepted_count=0,
        created_count=0,
        updated_count=0,
        duplicate_count=0,
        rejected_count=0,
        rejected_messages=[],
        sample_rows=[],
        error_message=message,
    )


def _row_payload(row: ParsedCsvRow) -> dict[str, object]:
    return {
        'line_number': row.line_number,
        'lemma': row.lemma,
        'translation': row.translation,
        'notes': row.notes,
        'metadata': row.metadata,
    }


def _stored_row_to_parsed(payload: dict[str, object]) -> ParsedCsvRow:
    return ParsedCsvRow(
        line_number=payload['line_number'],
        lemma=payload['lemma'],
        translation=payload['translation'],
        notes=payload['notes'],
        metadata=payload['metadata'],
    )
