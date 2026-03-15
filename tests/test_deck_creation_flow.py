from datetime import UTC, datetime

from czech_vocab.repositories import CardCreate, CardRepository, DeckRepository, build_identity_key
from czech_vocab.services import DeckSettingsService


def test_dashboard_links_to_deck_creation_and_create_page_uses_default_count(client, app) -> None:
    create_global_card(app.config["DATABASE_PATH"], "kniha", "книга")

    home_page = client.get("/").get_data(as_text=True)
    create_page = client.get("/decks/new")

    assert 'href="/decks/new"' in home_page
    assert create_page.status_code == 200
    page = create_page.get_data(as_text=True)
    assert '<form method="post" action="/decks/new"' in page
    assert 'name="deck_name"' in page
    assert 'name="requested_count"' in page
    assert 'name="save_default_count"' in page
    assert 'value="20"' in page


def test_create_deck_route_assigns_random_cards_and_redirects_with_success(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    create_global_card(database_path, "auto", "машина")
    create_global_card(database_path, "dum", "дом")
    create_global_card(database_path, "kniha", "книга")

    response = client.post(
        "/decks/new",
        data={
            "deck_name": "Глаголы",
            "requested_count": "2",
            "mode": "random",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Колода «Глаголы» создана." in page
    assert "Глаголы" in page
    assert "2 карточек" in page

    deck = DeckRepository(database_path).get_deck_by_name("Глаголы")
    assert deck is not None
    with CardRepository(database_path).connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM deck_cards WHERE deck_id = ?",
            (deck.id,),
        ).fetchone()[0]
    assert count == 2


def test_create_deck_route_can_save_override_back_to_settings(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    create_global_card(database_path, "auto", "машина")
    create_global_card(database_path, "dum", "дом")
    create_global_card(database_path, "kniha", "книга")

    response = client.post(
        "/decks/new",
        data={
            "deck_name": "Путешествия",
            "requested_count": "3",
            "mode": "random",
            "save_default_count": "on",
        },
    )

    assert response.status_code == 302
    settings = DeckSettingsService(database_path).get_app_settings()
    assert settings.default_target_deck_card_count == 3


def test_create_deck_route_blocks_when_available_pool_is_empty(client) -> None:
    response = client.post(
        "/decks/new",
        data={
            "deck_name": "Глаголы",
            "requested_count": "2",
            "mode": "random",
        },
    )

    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "Свободных карточек пока нет" in page
    assert 'href="/import"' in page


def test_create_deck_route_preserves_input_on_validation_error(client, app) -> None:
    create_global_card(app.config["DATABASE_PATH"], "kniha", "книга")

    response = client.post(
        "/decks/new",
        data={
            "deck_name": "   ",
            "requested_count": "0",
            "mode": "random",
            "save_default_count": "on",
        },
    )

    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "Введите название колоды." in page
    assert "Количество карточек должно быть целым числом 1 или больше." in page
    assert 'value="0"' in page
    assert 'checked' in page


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
