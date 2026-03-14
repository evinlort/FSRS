from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from czech_vocab.domain import FsrsScheduler
from czech_vocab.importers import MissingRequiredHeadersError, parse_vocabulary_csv
from czech_vocab.repositories import CardCreate, CardRepository, build_identity_key


@dataclass(frozen=True)
class ImportSummary:
    created_count: int
    updated_count: int
    rejected_count: int
    messages: list[str]


class ImportService:
    def __init__(self, database_path: Path, *, scheduler: FsrsScheduler | None = None) -> None:
        self._repository = CardRepository(database_path)
        self._scheduler = scheduler or FsrsScheduler()

    def import_csv_bytes(
        self,
        csv_bytes: bytes,
        *,
        imported_at: datetime | None = None,
    ) -> ImportSummary:
        try:
            csv_text = csv_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return ImportSummary(0, 0, 0, ["Unable to decode CSV as UTF-8."])
        return self.import_csv_text(csv_text, imported_at=imported_at)

    def import_csv_text(
        self,
        csv_text: str,
        *,
        imported_at: datetime | None = None,
    ) -> ImportSummary:
        try:
            result = parse_vocabulary_csv(StringIO(csv_text))
        except MissingRequiredHeadersError as exc:
            return ImportSummary(0, 0, 0, [str(exc)])
        review_time = imported_at.astimezone(UTC) if imported_at else datetime.now(UTC)
        return self._persist_rows(result.rows, result.row_errors, review_time)

    def _persist_rows(self, rows, row_errors, review_time: datetime) -> ImportSummary:
        created_count = 0
        updated_count = 0
        messages = [f"Line {error.line_number}: {error.message}" for error in row_errors]
        with self._repository.connect() as connection:
            for row in rows:
                identity_key = build_identity_key(row.lemma, row.translation)
                existing = self._repository.get_card_by_identity_key(
                    identity_key,
                    connection=connection,
                )
                if existing is not None:
                    self._repository.update_imported_content(
                        card_id=existing.id,
                        lemma=row.lemma,
                        translation=row.translation,
                        notes=row.notes,
                        metadata=row.metadata,
                        connection=connection,
                    )
                    updated_count += 1
                    continue
                created_card = self._repository.create_card(
                    CardCreate(
                        identity_key=identity_key,
                        lemma=row.lemma,
                        translation=row.translation,
                        notes=row.notes,
                        metadata=row.metadata,
                        fsrs_state={},
                        due_at=None,
                        last_review_at=None,
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
                created_count += 1
        return ImportSummary(
            created_count=created_count,
            updated_count=updated_count,
            rejected_count=len(row_errors),
            messages=messages,
        )
