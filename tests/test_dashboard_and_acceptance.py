from datetime import UTC, datetime, timedelta
from io import BytesIO

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardCreate, CardRepository, build_identity_key


def test_home_page_shows_live_totals_and_due_counts(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_dashboard_card(
        app.config["DATABASE_PATH"],
        lemma="kniha",
        translation="книга",
        due_at=now - timedelta(hours=1),
    )
    create_dashboard_card(
        app.config["DATABASE_PATH"],
        lemma="vlak",
        translation="поезд",
        due_at=now + timedelta(days=2),
    )

    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Всего карточек: 2" in page
    assert "К повторению: 1" in page
    assert 'href="/import"' in page
    assert 'href="/review"' in page
    assert 'href="/cards"' in page


def test_acceptance_flow_covers_import_review_and_catalog(client, app) -> None:
    repository = CardRepository(app.config["DATABASE_PATH"])
    upload_response = client.post(
        "/import",
        data={
            "csv_file": (
                BytesIO("lemma_cs,translation_ru,notes\nkniha,книга,book note\n".encode("utf-8")),
                "cards.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert upload_response.status_code == 200
    assert "Создано: 1" in upload_response.get_data(as_text=True)
    home_after_import = client.get("/").get_data(as_text=True)
    assert "Всего карточек: 1" in home_after_import
    assert "К повторению: 1" in home_after_import

    review_page = client.get("/review")
    assert review_page.status_code == 200
    assert "kniha" in review_page.get_data(as_text=True)

    card = repository.get_card_by_identity_key(build_identity_key("kniha", "книга"))
    assert card is not None
    review_response = client.post(f"/review/{card.id}/grade", data={"rating": "Good"})

    assert review_response.status_code == 302
    logs = repository.list_review_logs(card.id)
    assert len(logs) == 1
    assert logs[0].rating == "Good"

    home_after_review = client.get("/").get_data(as_text=True)
    assert "К повторению: 0" in home_after_review
    catalog_page = client.get("/cards?q=kniha").get_data(as_text=True)
    assert "kniha" in catalog_page
    assert "книга" in catalog_page


def create_dashboard_card(database_path, *, lemma: str, translation: str, due_at: datetime):
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    identity_key = build_identity_key(lemma, translation)
    created = repository.create_card(
        CardCreate(
            identity_key=identity_key,
            lemma=lemma,
            translation=translation,
            notes="",
            metadata={},
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
