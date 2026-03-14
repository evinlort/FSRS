from datetime import UTC, datetime

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardCreate, CardRepository, build_identity_key


def test_review_page_renders_due_card_and_grade_buttons(client, app) -> None:
    due_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_due_card(
        app.config["DATABASE_PATH"],
        lemma="kniha",
        translation="книга",
        notes="common noun",
        metadata={"level": "A1"},
        due_at=due_at,
    )

    response = client.get("/review")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "kniha" in page
    assert "книга" in page
    assert "common noun" in page
    assert "level" in page
    assert "A1" in page
    for grade in ("Again", "Hard", "Good", "Easy"):
        assert f'value="{grade}"' in page


def test_review_page_shows_empty_state_when_nothing_is_due(client) -> None:
    response = client.get("/review")

    assert response.status_code == 200
    assert "No cards are due right now." in response.get_data(as_text=True)


def test_posting_valid_grade_redirects_and_persists_review(client, app) -> None:
    due_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_due_card(
        app.config["DATABASE_PATH"],
        lemma="pes",
        translation="собака",
        notes="animal",
        metadata={},
        due_at=due_at,
    )
    repository = CardRepository(app.config["DATABASE_PATH"])

    response = client.post(f"/review/{created.id}/grade", data={"rating": "Good"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/review")
    stored = repository.get_card_by_id(created.id)
    assert stored is not None
    assert stored.last_review_at is not None
    assert stored.due_at is not None
    assert stored.due_at >= stored.last_review_at
    logs = repository.list_review_logs(created.id)
    assert len(logs) == 1
    assert logs[0].rating == "Good"


def test_invalid_grade_returns_400_and_does_not_create_review_log(client, app) -> None:
    due_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = create_due_card(
        app.config["DATABASE_PATH"],
        lemma="dum",
        translation="дом",
        notes="building",
        metadata={},
        due_at=due_at,
    )
    repository = CardRepository(app.config["DATABASE_PATH"])

    response = client.post(f"/review/{created.id}/grade", data={"rating": "Maybe"})

    assert response.status_code == 400
    assert "Unsupported rating: Maybe" in response.get_data(as_text=True)
    assert repository.list_review_logs(created.id) == []


def create_due_card(
    database_path,
    *,
    lemma: str,
    translation: str,
    notes: str,
    metadata: dict,
    due_at,
):
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    identity_key = build_identity_key(lemma, translation)
    created = repository.create_card(
        CardCreate(
            identity_key=identity_key,
            lemma=lemma,
            translation=translation,
            notes=notes,
            metadata=metadata,
            fsrs_state=scheduler.create_default_state(card_id=0, now=due_at),
            due_at=due_at,
            last_review_at=None,
        ),
    )
    state = scheduler.create_default_state(card_id=created.id, now=due_at)
    restored = scheduler.deserialize_card(state)
    repository.update_schedule_state(
        card_id=created.id,
        fsrs_state=state,
        due_at=restored.due,
        last_review_at=restored.last_review,
    )
    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    return updated
