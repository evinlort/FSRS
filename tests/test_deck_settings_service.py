from pathlib import Path

from czech_vocab.repositories import initialize_database
from czech_vocab.services.deck_settings_service import DeckSettingsService


def test_global_settings_persist_and_new_decks_inherit_defaults(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.sqlite3"
    initialize_database(database_path)
    service = DeckSettingsService(database_path)

    original = service.get_app_settings()
    assert original.default_desired_retention == 0.90
    assert original.default_daily_new_limit == 20
    assert original.default_target_deck_card_count == 20

    updated = service.update_app_settings(
        default_desired_retention=0.87,
        default_daily_new_limit=9,
        default_target_deck_card_count=24,
    )
    created_deck = service.create_deck("Глаголы")

    assert updated.default_desired_retention == 0.87
    assert updated.default_daily_new_limit == 9
    assert updated.default_target_deck_card_count == 24
    assert created_deck.desired_retention == 0.87
    assert created_deck.daily_new_limit == 9
    assert [deck.name for deck in service.list_decks()] == ["Основная", "Глаголы"]


def test_deck_settings_can_be_updated_without_changing_global_defaults(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.sqlite3"
    initialize_database(database_path)
    service = DeckSettingsService(database_path)
    created_deck = service.create_deck("Существительные")

    updated_deck = service.update_deck_settings(
        deck_id=created_deck.id,
        desired_retention=0.95,
        daily_new_limit=4,
    )
    settings = service.get_app_settings()

    assert updated_deck.desired_retention == 0.95
    assert updated_deck.daily_new_limit == 4
    assert settings.default_desired_retention == 0.90
    assert settings.default_daily_new_limit == 20
    assert settings.default_target_deck_card_count == 20
