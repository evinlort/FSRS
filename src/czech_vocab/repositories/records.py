import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class CardCreate:
    identity_key: str
    lemma: str
    translation: str
    notes: str
    metadata: dict[str, Any]
    fsrs_state: dict[str, Any]
    due_at: datetime | None
    last_review_at: datetime | None
    deck_id: int = 1


@dataclass(frozen=True)
class CardRecord:
    id: int
    deck_id: int
    identity_key: str
    lemma: str
    translation: str
    notes: str
    metadata: dict[str, Any]
    fsrs_state: dict[str, Any]
    due_at: datetime | None
    last_review_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DeckRecord:
    id: int
    name: str
    desired_retention: float
    daily_new_limit: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AppSettingsRecord:
    default_desired_retention: float
    default_daily_new_limit: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ReviewLogRecord:
    id: int
    card_id: int
    rating: str
    reviewed_at: datetime
    review_duration_seconds: int | None
    undone_at: datetime | None


@dataclass(frozen=True)
class ImportPreviewRecord:
    token: str
    deck_name: str
    rows: list[dict[str, Any]]
    rejected_messages: list[str]
    duplicate_count: int
    imported_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class UndoReviewSnapshot:
    card_id: int
    deck_id: int
    review_log_id: int
    fsrs_state: dict[str, Any]
    due_at: datetime | None
    last_review_at: datetime | None


def build_identity_key(lemma: str, translation: str) -> str:
    material = "\0".join((_normalize_identity_text(lemma), _normalize_identity_text(translation)))
    return sha256(material.encode("utf-8")).hexdigest()


def dump_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def matches_query(row: sqlite3.Row, needle: str) -> bool:
    haystacks = (row["lemma"], row["translation"], row["notes"])
    return any(needle in value.casefold() for value in haystacks)


def parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def row_to_card(row: sqlite3.Row) -> CardRecord:
    return CardRecord(
        id=row["id"],
        deck_id=row["deck_id"],
        identity_key=row["identity_key"],
        lemma=row["lemma"],
        translation=row["translation"],
        notes=row["notes"],
        metadata=json.loads(row["metadata_json"]),
        fsrs_state=json.loads(row["fsrs_state_json"]),
        due_at=parse_datetime(row["due_at"]),
        last_review_at=parse_datetime(row["last_review_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def row_to_deck(row: sqlite3.Row) -> DeckRecord:
    return DeckRecord(
        id=row["id"],
        name=row["name"],
        desired_retention=row["desired_retention"],
        daily_new_limit=row["daily_new_limit"],
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def row_to_settings(row: sqlite3.Row) -> AppSettingsRecord:
    return AppSettingsRecord(
        default_desired_retention=row["default_desired_retention"],
        default_daily_new_limit=row["default_daily_new_limit"],
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def row_to_import_preview(row: sqlite3.Row) -> ImportPreviewRecord:
    return ImportPreviewRecord(
        token=row["token"],
        deck_name=row["deck_name"],
        rows=json.loads(row["rows_json"]),
        rejected_messages=json.loads(row["rejected_messages_json"]),
        duplicate_count=row["duplicate_count"],
        imported_at=parse_datetime(row["imported_at"]),
        created_at=parse_datetime(row["created_at"]),
    )


def serialize_datetime(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_identity_text(value: str) -> str:
    return " ".join(value.split()).casefold()
