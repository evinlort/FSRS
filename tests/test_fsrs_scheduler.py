from datetime import UTC, datetime

import pytest

from czech_vocab.domain.fsrs_scheduler import FsrsScheduler, ReviewLogData


def test_create_default_state_uses_mvp_defaults() -> None:
    scheduler = FsrsScheduler(enable_fuzzing=False)
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)

    card_state = scheduler.create_default_state(card_id=7, now=now)
    restored = scheduler.deserialize_card(card_state)

    assert scheduler.desired_retention == 0.90
    assert restored.card_id == 7
    assert restored.last_review is None
    assert restored.due == now


@pytest.mark.parametrize("rating", ["Again", "Hard", "Good", "Easy"])
def test_apply_rating_updates_state_for_each_supported_grade(rating: str) -> None:
    scheduler = FsrsScheduler(enable_fuzzing=False)
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    initial_state = scheduler.create_default_state(card_id=11, now=review_at)

    result = scheduler.apply_rating(
        card_state=initial_state,
        rating=rating,
        review_at=review_at,
        review_duration_seconds=9,
    )

    restored = scheduler.deserialize_card(result.card_state)
    assert restored.card_id == 11
    assert result.last_review_at == review_at
    assert result.due_at >= review_at
    assert result.review_log == ReviewLogData(
        card_id=11,
        rating=rating,
        reviewed_at=review_at,
        review_duration_seconds=9,
    )


def test_card_state_round_trips_after_review() -> None:
    scheduler = FsrsScheduler(enable_fuzzing=False)
    review_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    initial_state = scheduler.create_default_state(card_id=29, now=review_at)

    result = scheduler.apply_rating(
        card_state=initial_state,
        rating="Good",
        review_at=review_at,
    )

    round_tripped_state = scheduler.serialize_card(
        scheduler.deserialize_card(result.card_state),
    )

    assert round_tripped_state == result.card_state


def test_invalid_rating_is_rejected() -> None:
    scheduler = FsrsScheduler(enable_fuzzing=False)
    initial_state = scheduler.create_default_state(
        card_id=3,
        now=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="Unsupported rating: Maybe"):
        scheduler.apply_rating(
            card_state=initial_state,
            rating="Maybe",
            review_at=datetime(2026, 3, 14, 12, 5, tzinfo=UTC),
        )
