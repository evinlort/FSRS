from pathlib import Path

from czech_vocab.repositories import (
    AppSettingsRecord,
    AppSettingsRepository,
    DeckRecord,
    DeckRepository,
)


class DeckSettingsService:
    def __init__(self, database_path: Path) -> None:
        self._deck_repository = DeckRepository(database_path)
        self._settings_repository = AppSettingsRepository(database_path)

    def list_decks(self) -> list[DeckRecord]:
        return self._deck_repository.list_decks()

    def get_default_deck(self) -> DeckRecord:
        return self._deck_repository.get_default_deck()

    def get_app_settings(self) -> AppSettingsRecord:
        return self._settings_repository.get_settings()

    def update_app_settings(
        self,
        *,
        default_desired_retention: float,
        default_daily_new_limit: int,
        default_target_deck_card_count: int,
    ) -> AppSettingsRecord:
        return self._settings_repository.update_settings(
            default_desired_retention=default_desired_retention,
            default_daily_new_limit=default_daily_new_limit,
            default_target_deck_card_count=default_target_deck_card_count,
        )

    def create_deck(self, name: str) -> DeckRecord:
        settings = self.get_app_settings()
        return self._deck_repository.create_deck(
            name=name,
            desired_retention=settings.default_desired_retention,
            daily_new_limit=settings.default_daily_new_limit,
        )

    def update_deck_settings(
        self,
        *,
        deck_id: int,
        desired_retention: float,
        daily_new_limit: int,
    ) -> DeckRecord:
        return self._deck_repository.update_settings(
            deck_id=deck_id,
            desired_retention=desired_retention,
            daily_new_limit=daily_new_limit,
        )

    def resolve_import_deck(self, deck_name: str | None) -> DeckRecord:
        if not deck_name:
            return self.get_default_deck()
        existing = self._deck_repository.get_deck_by_name(deck_name)
        if existing is not None:
            return existing
        return self.create_deck(deck_name)
