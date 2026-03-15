from czech_vocab.services import DeckSettingsService


def test_settings_page_renders_global_deck_sections_and_shortcuts(client, app) -> None:
    service = DeckSettingsService(app.config["DATABASE_PATH"])
    service.create_deck("Путешествия")

    response = client.get("/settings")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "<title>Настройки" in page
    assert "Общие настройки" in page
    assert "Колоды" in page
    assert "Горячие клавиши" in page
    assert 'name="default_desired_retention"' in page
    assert 'name="default_daily_new_limit"' in page
    assert 'name="default_target_deck_card_count"' in page
    assert 'name="deck_1_desired_retention"' in page
    assert 'name="deck_1_daily_new_limit"' in page
    assert "Путешествия" in page
    assert "Space" in page


def test_settings_page_shows_inline_errors_and_preserves_values(client, app) -> None:
    deck = DeckSettingsService(app.config["DATABASE_PATH"]).create_deck("Путешествия")

    response = client.post(
        "/settings",
        data={
            "default_desired_retention": "abc",
            "default_daily_new_limit": "-2",
            "default_target_deck_card_count": "0",
            "deck_1_desired_retention": "0.91",
            "deck_1_daily_new_limit": "18",
            f"deck_{deck.id}_desired_retention": "1.50",
            f"deck_{deck.id}_daily_new_limit": "x",
        },
    )

    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "Укажите retention числом от 0 до 1." in page
    assert "Лимит новых карточек должен быть целым числом 0 или больше." in page
    assert "Размер новой колоды должен быть целым числом 1 или больше." in page
    assert 'value="abc"' in page
    assert 'value="-2"' in page
    assert 'value="0"' in page
    assert 'value="1.50"' in page
    assert 'value="x"' in page


def test_settings_page_updates_values_and_redirects(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    service = DeckSettingsService(database_path)
    deck = service.create_deck("Путешествия")

    response = client.post(
        "/settings",
        data={
            "default_desired_retention": "0.86",
            "default_daily_new_limit": "11",
            "default_target_deck_card_count": "25",
            "deck_1_desired_retention": "0.92",
            "deck_1_daily_new_limit": "17",
            f"deck_{deck.id}_desired_retention": "0.84",
            f"deck_{deck.id}_daily_new_limit": "5",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")
    settings = service.get_app_settings()
    decks = {item.id: item for item in service.list_decks()}
    assert settings.default_desired_retention == 0.86
    assert settings.default_daily_new_limit == 11
    assert settings.default_target_deck_card_count == 25
    assert decks[1].desired_retention == 0.92
    assert decks[1].daily_new_limit == 17
    assert decks[deck.id].desired_retention == 0.84
    assert decks[deck.id].daily_new_limit == 5
