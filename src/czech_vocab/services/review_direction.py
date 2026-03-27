from dataclasses import dataclass

from czech_vocab.repositories import (
    ALLOWED_REVIEW_DIRECTIONS,
    DEFAULT_REVIEW_DIRECTION,
    FORWARD_REVIEW_DIRECTION,
    REVERSE_REVIEW_DIRECTION,
)


@dataclass(frozen=True)
class ReviewDirectionOption:
    value: str
    label: str


_DIRECTION_LABELS = {
    FORWARD_REVIEW_DIRECTION: "Чешский → Русский",
    REVERSE_REVIEW_DIRECTION: "Русский → Чешский",
}


def parse_review_direction(raw_direction: str | None) -> str:
    if raw_direction in ALLOWED_REVIEW_DIRECTIONS:
        return raw_direction
    return DEFAULT_REVIEW_DIRECTION


def review_direction_label(direction: str) -> str:
    return _DIRECTION_LABELS[parse_review_direction(direction)]


def review_direction_options() -> list[ReviewDirectionOption]:
    return [
        ReviewDirectionOption(
            FORWARD_REVIEW_DIRECTION,
            _DIRECTION_LABELS[FORWARD_REVIEW_DIRECTION],
        ),
        ReviewDirectionOption(
            REVERSE_REVIEW_DIRECTION,
            _DIRECTION_LABELS[REVERSE_REVIEW_DIRECTION],
        ),
    ]


def review_prompt_text(*, lemma: str, translation: str, direction: str) -> str:
    if parse_review_direction(direction) == REVERSE_REVIEW_DIRECTION:
        return translation
    return lemma


def review_answer_label(direction: str) -> str:
    if parse_review_direction(direction) == REVERSE_REVIEW_DIRECTION:
        return "Чешское слово"
    return "Перевод"


def review_answer_text(*, lemma: str, translation: str, direction: str) -> str:
    if parse_review_direction(direction) == REVERSE_REVIEW_DIRECTION:
        return lemma
    return translation
