from datetime import UTC, datetime

from czech_vocab.repositories import (
    CardCreate,
    CardRepository,
    DeckCardRepository,
    build_identity_key,
)
from czech_vocab.services import DeckSettingsService


def test_dashboard_links_to_add_cards_page_and_route_uses_default_count(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck = DeckSettingsService(database_path).create_deck("Путешествия")
    create_global_card(database_path, "kniha", "книга")

    home_page = client.get("/").get_data(as_text=True)
    add_page = client.get(f"/decks/{deck.id}/add")

    assert f'href="/decks/{deck.id}/add"' in home_page
    assert add_page.status_code == 200
    page = add_page.get_data(as_text=True)
    assert "Добавить карточки в колоду" in page
    assert "Путешествия" in page
    assert 'name="requested_count"' in page
    assert 'value="20"' in page


def test_add_random_cards_route_assigns_available_cards_and_redirects(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck = DeckSettingsService(database_path).create_deck("Путешествия")
    create_global_card(database_path, "auto", "машина")
    create_global_card(database_path, "dum", "дом")
    create_global_card(database_path, "kniha", "книга")

    response = client.post(
        f"/decks/{deck.id}/add",
        data={
            "requested_count": "2",
            "save_default_count": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "В колоду «Путешествия» добавлено 2 карточек." in page

    with CardRepository(database_path).connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM deck_cards WHERE deck_id = ?",
            (deck.id,),
        ).fetchone()[0]
    assert count == 2
    settings = DeckSettingsService(database_path).get_app_settings()
    assert settings.default_target_deck_card_count == 2


def test_add_random_cards_route_handles_insufficient_pool_and_empty_pool(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck = DeckSettingsService(database_path).create_deck("Путешествия")
    create_global_card(database_path, "auto", "машина")

    partial = client.post(
        f"/decks/{deck.id}/add",
        data={"requested_count": "3"},
        follow_redirects=True,
    )

    assert partial.status_code == 200
    assert "В колоду «Путешествия» добавлено 1 карточек." in partial.get_data(as_text=True)

    empty = client.post(
        f"/decks/{deck.id}/add",
        data={"requested_count": "1"},
    )

    assert empty.status_code == 400
    page = empty.get_data(as_text=True)
    assert "Свободных карточек пока нет" in page
    assert 'href="/import"' in page


def test_add_random_cards_route_preserves_invalid_count_input(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck = DeckSettingsService(database_path).create_deck("Путешествия")
    create_global_card(database_path, "auto", "машина")

    response = client.post(
        f"/decks/{deck.id}/add",
        data={"requested_count": "0"},
    )

    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "Количество карточек должно быть целым числом 1 или больше." in page
    assert 'value="0"' in page


def test_manual_add_redirects_to_selection_page_and_excludes_assigned_cards(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck_service = DeckSettingsService(database_path)
    deck = deck_service.create_deck("Путешествия")
    other = deck_service.create_deck("Работа")
    first = create_global_card(database_path, "kniha", "книга")
    create_global_card(database_path, "dum", "дом")
    blocked = create_global_card(database_path, "vlak", "поезд")
    DeckCardRepository(database_path).assign_card_to_deck(card_id=blocked.id, deck_id=other.id)

    start_response = client.post(
        f"/decks/{deck.id}/add",
        data={
            "requested_count": "3",
            "mode": "manual",
        },
    )

    assert start_response.status_code == 302
    assert "/deck-drafts/" in start_response.headers["Location"]
    select_page = client.get(start_response.headers["Location"]).get_data(as_text=True)
    assert f'value="{first.id}"' in select_page
    assert "поезд" not in select_page
    assert "текущая колода и карточки из других колод здесь не показываются" in select_page


def test_manual_add_selection_can_add_checked_cards_only(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck = DeckSettingsService(database_path).create_deck("Путешествия")
    first = create_global_card(database_path, "kniha", "книга")
    create_global_card(database_path, "dum", "дом")
    create_global_card(database_path, "lod", "лодка")

    start_response = client.post(
        f"/decks/{deck.id}/add",
        data={
            "requested_count": "3",
            "mode": "manual",
        },
    )

    response = client.post(
        start_response.headers["Location"],
        data={
            "action": "confirm",
            "search_in": "czech",
            "q": "",
            "selected_card_ids": [str(first.id)],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "В колоду «Путешествия» добавлено 1 карточек." in page

    with CardRepository(database_path).connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM deck_cards WHERE deck_id = ?",
            (deck.id,),
        ).fetchone()[0]
    assert count == 1


def test_mixed_add_selection_adds_manual_and_random_fill(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    deck = DeckSettingsService(database_path).create_deck("Путешествия")
    first = create_global_card(database_path, "kniha", "книга")
    create_global_card(database_path, "dum", "дом")
    create_global_card(database_path, "lod", "лодка")

    start_response = client.post(
        f"/decks/{deck.id}/add",
        data={
            "requested_count": "2",
            "mode": "mixed",
        },
    )

    response = client.post(
        start_response.headers["Location"],
        data={
            "action": "confirm",
            "search_in": "czech",
            "q": "",
            "selected_card_ids": [str(first.id)],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "В колоду «Путешествия» добавлено 2 карточек." in page

    with CardRepository(database_path).connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM deck_cards WHERE deck_id = ?",
            (deck.id,),
        ).fetchone()[0]
    assert count == 2


def create_global_card(database_path, lemma: str, translation: str):
    repository = CardRepository(database_path)
    now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    return repository.create_card(
        CardCreate(
            identity_key=build_identity_key(lemma, translation),
            lemma=lemma,
            translation=translation,
            notes="",
            metadata={},
            fsrs_state={},
            due_at=now,
            last_review_at=None,
            deck_id=None,
        )
    )
