from datetime import UTC, datetime, timedelta

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardCreate, CardRepository, build_identity_key


def test_cards_page_lists_cards_ordered_by_lemma(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_catalog_card(app.config["DATABASE_PATH"], "vlak", "поезд", "transport", now)
    create_catalog_card(app.config["DATABASE_PATH"], "auto", "машина", "vehicle", now)
    create_catalog_card(app.config["DATABASE_PATH"], "dum", "дом", "building", now)

    response = client.get("/cards")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert page.index("auto") < page.index("dum") < page.index("vlak")
    assert "State: learning" in page
    assert "Due:" in page


def test_cards_page_searches_czech_russian_and_notes(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_catalog_card(app.config["DATABASE_PATH"], "kniha", "книга", "book note", now)
    create_catalog_card(app.config["DATABASE_PATH"], "strom", "дерево", "forest note", now)
    create_catalog_card(app.config["DATABASE_PATH"], "lod", "лодка", "river travel", now)

    czech_response = client.get("/cards?q=strom")
    russian_response = client.get("/cards?q=ЛОД")
    notes_response = client.get("/cards?q=forest")

    assert "strom" in czech_response.get_data(as_text=True)
    assert "lod" not in czech_response.get_data(as_text=True)
    assert "lod" in russian_response.get_data(as_text=True)
    assert "strom" in notes_response.get_data(as_text=True)


def test_cards_page_paginates_and_preserves_query_string(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    for index in range(55):
        create_catalog_card(
            app.config["DATABASE_PATH"],
            f"slovo-{index:02d}",
            f"перевод-{index:02d}",
            "alpha catalog",
            now + timedelta(minutes=index),
        )

    response = client.get("/cards?q=alpha&page=1")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "slovo-00" in page
    assert "slovo-49" in page
    assert "slovo-50" not in page
    assert '?q=alpha&amp;page=2' in page

    second_page = client.get("/cards?q=alpha&page=2").get_data(as_text=True)
    assert "slovo-50" in second_page
    assert "slovo-54" in second_page
    assert "slovo-49" not in second_page


def create_catalog_card(database_path, lemma: str, translation: str, notes: str, due_at: datetime):
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    identity_key = build_identity_key(lemma, translation)
    created = repository.create_card(
        CardCreate(
            identity_key=identity_key,
            lemma=lemma,
            translation=translation,
            notes=notes,
            metadata={"topic": "catalog"},
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
