import csv
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

HEADER_ALIASES = {
    "czech": {"lemma_cs", "czech", "czech_word", "word_cs", "lemma", "word"},
    "russian": {"translation_ru", "russian", "translation", "ru_translation"},
    "notes": {"notes", "note", "comment", "comments"},
}


@dataclass(frozen=True)
class ParsedCsvRow:
    line_number: int
    lemma: str
    translation: str
    notes: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class CsvRowError:
    line_number: int
    message: str


@dataclass(frozen=True)
class CsvParseResult:
    rows: list[ParsedCsvRow]
    row_errors: list[CsvRowError]


class MissingRequiredHeadersError(ValueError):
    def __init__(self, missing_headers: tuple[str, ...]) -> None:
        self.missing_headers = missing_headers
        joined = ", ".join(missing_headers)
        super().__init__(f"Missing required headers: {joined}")


def parse_vocabulary_csv_file(path: Path) -> CsvParseResult:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return parse_vocabulary_csv(handle)


def parse_vocabulary_csv(handle: TextIO) -> CsvParseResult:
    reader = csv.DictReader(handle)
    header_lookup = _build_header_lookup(reader.fieldnames)
    rows: list[ParsedCsvRow] = []
    row_errors: list[CsvRowError] = []
    for line_number, row in enumerate(reader, start=2):
        parsed_row, row_error = _parse_row(row, header_lookup, line_number)
        if parsed_row is not None:
            rows.append(parsed_row)
        if row_error is not None:
            row_errors.append(row_error)
    return CsvParseResult(rows=rows, row_errors=row_errors)


def _build_header_lookup(fieldnames: list[str] | None) -> dict[str, str]:
    normalized = {normalize_header(name): name for name in fieldnames or []}
    missing = tuple(
        logical_name
        for logical_name in ("czech", "russian")
        if _find_header(normalized, logical_name) is None
    )
    if missing:
        raise MissingRequiredHeadersError(missing)
    return {
        logical_name: _find_header(normalized, logical_name)
        for logical_name in ("czech", "russian", "notes")
    }


def _find_header(normalized_headers: dict[str, str], logical_name: str) -> str | None:
    for alias in HEADER_ALIASES[logical_name]:
        if alias in normalized_headers:
            return normalized_headers[alias]
    return None


def _parse_row(
    row: dict[str | None, str | None],
    header_lookup: dict[str, str | None],
    line_number: int,
) -> tuple[ParsedCsvRow | None, CsvRowError | None]:
    lemma = _get_required_value(row, header_lookup["czech"])
    if not lemma:
        return None, CsvRowError(line_number, "Missing required value: czech")
    translation = _get_required_value(row, header_lookup["russian"])
    if not translation:
        return None, CsvRowError(line_number, "Missing required value: russian")
    notes = _get_optional_value(row, header_lookup["notes"])
    metadata = _extract_metadata(row, header_lookup)
    return ParsedCsvRow(line_number, lemma, translation, notes, metadata), None


def _get_required_value(row: dict[str | None, str | None], header_name: str | None) -> str:
    return _normalize_value(row.get(header_name)) if header_name else ""


def _get_optional_value(row: dict[str | None, str | None], header_name: str | None) -> str:
    return _normalize_value(row.get(header_name)) if header_name else ""


def _extract_metadata(
    row: dict[str | None, str | None],
    header_lookup: dict[str, str | None],
) -> dict[str, str]:
    reserved = {name for name in header_lookup.values() if name is not None}
    metadata: dict[str, str] = {}
    for header_name, value in row.items():
        if header_name is None or header_name in reserved:
            continue
        metadata[normalize_header(header_name)] = _normalize_value(value)
    return metadata


def _normalize_value(value: str | None) -> str:
    return value.strip() if value else ""


def normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_").replace("-", "_")
