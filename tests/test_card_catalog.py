from datetime import UTC, datetime, timedelta

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import (
    REVERSE_REVIEW_DIRECTION,
    CardCreate,
    CardRepository,
    build_identity_key,
)
from czech_vocab.services import DeckSettingsService


def test_cards_page_lists_cards_for_selected_deck_ordered_by_lemma(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    deck_service = DeckSettingsService(app.config["DATABASE_PATH"])
    travel_deck = deck_service.create_deck("Путешествия")
    create_catalog_card(app.config["DATABASE_PATH"], "vlak", "поезд", "transport", now)
    create_catalog_card(app.config["DATABASE_PATH"], "auto", "машина", "vehicle", now)
    create_catalog_card(
        app.config["DATABASE_PATH"],
        "lod",
        "лодка",
        "travel",
        now,
        deck_id=travel_deck.id,
    )

    response = client.get("/cards?deck=1")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert page.index("auto") < page.index("vlak")
    assert "lod" not in page
    assert "Состояние: new" in page
    assert "Срок:" in page


def test_cards_page_combines_deck_status_and_search_scope_filters(client, app) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    deck_service = DeckSettingsService(app.config["DATABASE_PATH"])
    travel_deck = deck_service.create_deck("Путешествия")
    create_catalog_card(
        app.config["DATABASE_PATH"],
        "strom",
        "дерево",
        "forest note",
        now - timedelta(hours=2),
        learned=True,
    )
    create_catalog_card(
        app.config["DATABASE_PATH"],
        "les",
        "лес",
        "forest note",
        now + timedelta(days=1),
        learned=True,
    )
    create_catalog_card(
        app.config["DATABASE_PATH"],
        "lod",
        "лодка",
        "river travel",
        now,
        learned=False,
        deck_id=travel_deck.id,
    )

    due_response = client.get("/cards?deck=1&status=due")
    russian_response = client.get("/cards?deck=all&search_in=russian&q=ЛОД")
    notes_response = client.get("/cards?deck=1&search_in=all&q=forest")

    due_page = due_response.get_data(as_text=True)
    russian_page = russian_response.get_data(as_text=True)
    notes_page = notes_response.get_data(as_text=True)
    assert '<h2 class="card-list__title">strom</h2>' in due_page
    assert '<h2 class="card-list__title">les</h2>' not in due_page
    assert '<h2 class="card-list__title">lod</h2>' in russian_page
    assert '<h2 class="card-list__title">strom</h2>' in notes_page
    assert '<h2 class="card-list__title">les</h2>' in notes_page


def test_cards_page_supports_new_and_learned_status_filters(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_catalog_card(app.config["DATABASE_PATH"], "novy", "новый", "fresh", now, learned=False)
    create_catalog_card(
        app.config["DATABASE_PATH"],
        "stary",
        "старый",
        "known",
        now + timedelta(days=2),
        learned=True,
    )

    new_page = client.get("/cards?status=new").get_data(as_text=True)
    learned_page = client.get("/cards?status=learned").get_data(as_text=True)

    assert "novy" in new_page
    assert "stary" not in new_page
    assert "stary" in learned_page
    assert "novy" not in learned_page


def test_cards_page_paginates_and_preserves_all_filters(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    for index in range(55):
        create_catalog_card(
            app.config["DATABASE_PATH"],
            f"slovo-{index:02d}",
            f"перевод-{index:02d}",
            "alpha catalog",
            now + timedelta(minutes=index),
        )

    response = client.get("/cards?deck=1&status=all&search_in=all&q=alpha&page=1")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "slovo-00" in page
    assert "slovo-49" in page
    assert "slovo-50" not in page
    assert "deck=1" in page
    assert "status=all" in page
    assert "search_in=all" in page
    assert "q=alpha" in page

    second_page = client.get("/cards?deck=1&status=all&search_in=all&q=alpha&page=2")
    second_page_text = second_page.get_data(as_text=True)
    assert "slovo-50" in second_page_text
    assert "slovo-54" in second_page_text
    assert "slovo-49" not in second_page_text


def test_cards_page_distinguishes_empty_catalog_from_no_matches(client, app) -> None:
    empty_response = client.get("/cards")

    assert "Карточек пока нет" in empty_response.get_data(as_text=True)
    assert 'href="/import"' in empty_response.get_data(as_text=True)

    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    create_catalog_card(app.config["DATABASE_PATH"], "kniha", "книга", "book", now)
    no_match_response = client.get("/cards?deck=1&q=xyz&search_in=czech")
    no_match_page = no_match_response.get_data(as_text=True)

    assert "Совпадений не найдено" in no_match_page
    assert 'href="/cards?deck=1&amp;status=all&amp;search_in=czech"' in no_match_page


def test_cards_page_ignores_reverse_direction_progress_for_status_filters(client, app) -> None:
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    card = create_catalog_card(
        app.config["DATABASE_PATH"],
        "most",
        "мост",
        "bridge",
        now + timedelta(days=2),
        learned=False,
    )
    repository = CardRepository(app.config["DATABASE_PATH"])
    scheduler = FsrsScheduler(enable_fuzzing=False)
    reverse_state = scheduler.create_default_state(card_id=card.id, now=now - timedelta(days=1))
    repository.update_schedule_state(
        card_id=card.id,
        direction=REVERSE_REVIEW_DIRECTION,
        fsrs_state=reverse_state,
        due_at=now - timedelta(minutes=10),
        last_review_at=now - timedelta(days=1),
    )
    repository.insert_review_log(
        card_id=card.id,
        direction=REVERSE_REVIEW_DIRECTION,
        rating="Good",
        reviewed_at=now - timedelta(hours=1),
        review_duration_seconds=12,
    )

    due_page = client.get("/cards?status=due").get_data(as_text=True)
    new_page = client.get("/cards?status=new").get_data(as_text=True)

    assert "most" not in due_page
    assert "most" in new_page


def create_catalog_card(
    database_path,
    lemma: str,
    translation: str,
    notes: str,
    due_at: datetime,
    *,
    learned: bool = False,
    deck_id: int = 1,
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
            metadata={"topic": "catalog"},
            fsrs_state=scheduler.create_default_state(card_id=0, now=due_at),
            due_at=due_at,
            last_review_at=None,
            deck_id=deck_id,
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
    if learned:
        repository.insert_review_log(
            card_id=created.id,
            rating="Good",
            reviewed_at=due_at - timedelta(days=1),
            review_duration_seconds=12,
        )
        repository.update_schedule_state(
            card_id=created.id,
            fsrs_state=state,
            due_at=due_at,
            last_review_at=due_at - timedelta(days=1),
        )
    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    return updated
