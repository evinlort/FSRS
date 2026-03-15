from pathlib import Path

import pytest

from czech_vocab.repositories import initialize_database
from czech_vocab.services import DeckSettingsService
from czech_vocab.services.settings_page_service import SettingsPageService, SettingsValidationError


def test_settings_service_returns_global_and_deck_values(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.sqlite3"
    initialize_database(database_path)
    deck_service = DeckSettingsService(database_path)
    travel = deck_service.create_deck("Путешествия")
    service = SettingsPageService(database_path)

    page = service.get_page_data()

    assert page.default_desired_retention == "0.90"
    assert page.default_daily_new_limit == "20"
    assert page.default_target_deck_card_count == "20"
    assert [deck.name for deck in page.decks] == ["Основная", "Путешествия"]
    assert [deck.desired_retention for deck in page.decks] == ["0.90", "0.90"]
    assert [deck.daily_new_limit for deck in page.decks] == ["20", "20"]
    assert travel.id in [deck.deck_id for deck in page.decks]


def test_settings_service_rejects_invalid_numbers_with_field_errors(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.sqlite3"
    initialize_database(database_path)
    deck_service = DeckSettingsService(database_path)
    travel = deck_service.create_deck("Путешествия")
    service = SettingsPageService(database_path)

    with pytest.raises(SettingsValidationError) as exc:
        service.update_settings(
            default_desired_retention="1.20",
            default_daily_new_limit="-1",
            default_target_deck_card_count="0",
            deck_updates={
                1: {"desired_retention": "0.80", "daily_new_limit": "10"},
                travel.id: {"desired_retention": "oops", "daily_new_limit": "abc"},
            },
        )

    page = exc.value.page_data
    assert page.errors["default_desired_retention"] == "Укажите retention числом от 0 до 1."
    assert (
        page.errors["default_daily_new_limit"]
        == "Лимит новых карточек должен быть целым числом 0 или больше."
    )
    assert (
        page.errors["default_target_deck_card_count"]
        == "Размер новой колоды должен быть целым числом 1 или больше."
    )
    assert (
        page.errors[f"deck_{travel.id}_desired_retention"]
        == "Укажите retention числом от 0 до 1."
    )
    assert (
        page.errors[f"deck_{travel.id}_daily_new_limit"]
        == "Лимит новых карточек должен быть целым числом 0 или больше."
    )
    persisted = deck_service.get_app_settings()
    assert persisted.default_desired_retention == 0.90
    assert persisted.default_daily_new_limit == 20
    assert persisted.default_target_deck_card_count == 20


def test_settings_service_updates_global_and_deck_values(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.sqlite3"
    initialize_database(database_path)
    deck_service = DeckSettingsService(database_path)
    travel = deck_service.create_deck("Путешествия")
    service = SettingsPageService(database_path)

    page = service.update_settings(
        default_desired_retention="0.87",
        default_daily_new_limit="12",
        default_target_deck_card_count="24",
        deck_updates={
            1: {"desired_retention": "0.91", "daily_new_limit": "15"},
            travel.id: {"desired_retention": "0.83", "daily_new_limit": "6"},
        },
    )

    settings = deck_service.get_app_settings()
    decks = {deck.id: deck for deck in deck_service.list_decks()}
    assert settings.default_desired_retention == 0.87
    assert settings.default_daily_new_limit == 12
    assert settings.default_target_deck_card_count == 24
    assert decks[1].desired_retention == 0.91
    assert decks[1].daily_new_limit == 15
    assert decks[travel.id].desired_retention == 0.83
    assert decks[travel.id].daily_new_limit == 6
    assert page.default_desired_retention == "0.87"
    assert page.default_daily_new_limit == "12"
    assert page.default_target_deck_card_count == "24"
