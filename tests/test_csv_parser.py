from io import StringIO
from pathlib import Path

import pytest

from czech_vocab.importers.csv_parser import (
    CsvRowError,
    MissingRequiredHeadersError,
    parse_vocabulary_csv,
    parse_vocabulary_csv_file,
)


def test_parse_sample_csv_file() -> None:
    result = parse_vocabulary_csv_file(Path("cz_ru_words_thesaurus.csv"))

    assert len(result.rows) == 1274
    assert result.row_errors == []
    assert result.rows[0].lemma == "aby"
    assert result.rows[0].translation == "чтобы"
    assert result.rows[0].notes == ""
    assert result.rows[0].metadata == {}


def test_parse_alias_headers_and_preserve_extra_metadata() -> None:
    csv_text = StringIO(
        " Czech Word ,ru-translation,Comment,Part Of Speech,CEFR Level\n"
        "kniha,книга,common noun,noun,A1\n"
    )

    result = parse_vocabulary_csv(csv_text)

    assert result.row_errors == []
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.lemma == "kniha"
    assert row.translation == "книга"
    assert row.notes == "common noun"
    assert row.metadata == {
        "part_of_speech": "noun",
        "cefr_level": "A1",
    }


def test_missing_required_headers_raises_clear_error() -> None:
    csv_text = StringIO("notes\nhelpful note\n")

    with pytest.raises(MissingRequiredHeadersError) as exc_info:
        parse_vocabulary_csv(csv_text)

    assert exc_info.value.missing_headers == ("czech", "russian")


def test_blank_required_values_become_row_errors() -> None:
    csv_text = StringIO(
        "lemma_cs,translation_ru,notes,tag\n"
        "pes,собака,valid row,animal\n"
        ",кошка,missing czech,animal\n"
        "vlak, ,missing translation,transport\n"
    )

    result = parse_vocabulary_csv(csv_text)

    assert [row.lemma for row in result.rows] == ["pes"]
    assert result.rows[0].metadata == {"tag": "animal"}
    assert result.row_errors == [
        CsvRowError(line_number=3, message="Missing required value: czech"),
        CsvRowError(line_number=4, message="Missing required value: russian"),
    ]
