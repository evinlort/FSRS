import sqlite3
from dataclasses import dataclass
from pathlib import Path

from czech_vocab.repositories import AppSettingsRepository, DeckRepository

RETENTION_ERROR = "Укажите retention числом от 0 до 1."
NEW_LIMIT_ERROR = "Лимит новых карточек должен быть целым числом 0 или больше."
TARGET_COUNT_ERROR = "Размер новой колоды должен быть целым числом 1 или больше."


@dataclass(frozen=True)
class SettingsDeckData:
    deck_id: int
    name: str
    desired_retention: str
    daily_new_limit: str


@dataclass(frozen=True)
class SettingsPageData:
    default_desired_retention: str
    default_daily_new_limit: str
    default_target_deck_card_count: str
    decks: list[SettingsDeckData]
    errors: dict[str, str]


class SettingsValidationError(ValueError):
    def __init__(self, page_data: SettingsPageData) -> None:
        super().__init__("Settings validation failed.")
        self.page_data = page_data


class SettingsPageService:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._deck_repository = DeckRepository(database_path)
        self._settings_repository = AppSettingsRepository(database_path)

    def get_page_data(
        self,
        *,
        errors: dict[str, str] | None = None,
        default_values: dict[str, str] | None = None,
        deck_values: dict[int, dict[str, str]] | None = None,
    ) -> SettingsPageData:
        settings = self._settings_repository.get_settings()
        decks = self._deck_repository.list_decks()
        defaults = default_values or {}
        custom_decks = deck_values or {}
        return SettingsPageData(
            default_desired_retention=defaults.get(
                "default_desired_retention",
                _format_retention(settings.default_desired_retention),
            ),
            default_daily_new_limit=defaults.get(
                "default_daily_new_limit",
                str(settings.default_daily_new_limit),
            ),
            default_target_deck_card_count=defaults.get(
                "default_target_deck_card_count",
                str(settings.default_target_deck_card_count),
            ),
            decks=[
                SettingsDeckData(
                    deck_id=deck.id,
                    name=deck.name,
                    desired_retention=custom_decks.get(deck.id, {}).get(
                        "desired_retention",
                        _format_retention(deck.desired_retention),
                    ),
                    daily_new_limit=custom_decks.get(deck.id, {}).get(
                        "daily_new_limit",
                        str(deck.daily_new_limit),
                    ),
                )
                for deck in decks
            ],
            errors=errors or {},
        )

    def update_settings(
        self,
        *,
        default_desired_retention: str,
        default_daily_new_limit: str,
        default_target_deck_card_count: str,
        deck_updates: dict[int, dict[str, str]],
    ) -> SettingsPageData:
        page_data = self.get_page_data(
            default_values={
                "default_desired_retention": default_desired_retention,
                "default_daily_new_limit": default_daily_new_limit,
                "default_target_deck_card_count": default_target_deck_card_count,
            },
            deck_values=deck_updates,
        )
        errors = _collect_errors(page_data)
        if errors:
            raise SettingsValidationError(
                self.get_page_data(
                    errors=errors,
                    default_values={
                        "default_desired_retention": default_desired_retention,
                        "default_daily_new_limit": default_daily_new_limit,
                        "default_target_deck_card_count": default_target_deck_card_count,
                    },
                    deck_values=deck_updates,
                )
            )
        with self._connect() as connection:
            self._settings_repository.update_settings(
                default_desired_retention=float(default_desired_retention),
                default_daily_new_limit=int(default_daily_new_limit),
                default_target_deck_card_count=int(default_target_deck_card_count),
                connection=connection,
            )
            for deck in page_data.decks:
                self._deck_repository.update_settings(
                    deck_id=deck.deck_id,
                    desired_retention=float(deck.desired_retention),
                    daily_new_limit=int(deck.daily_new_limit),
                    connection=connection,
                )
        return self.get_page_data()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _collect_errors(page_data: SettingsPageData) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not _is_valid_retention(page_data.default_desired_retention):
        errors["default_desired_retention"] = RETENTION_ERROR
    if not _is_valid_new_limit(page_data.default_daily_new_limit):
        errors["default_daily_new_limit"] = NEW_LIMIT_ERROR
    if not _is_valid_target_count(page_data.default_target_deck_card_count):
        errors["default_target_deck_card_count"] = TARGET_COUNT_ERROR
    for deck in page_data.decks:
        if not _is_valid_retention(deck.desired_retention):
            errors[f"deck_{deck.deck_id}_desired_retention"] = RETENTION_ERROR
        if not _is_valid_new_limit(deck.daily_new_limit):
            errors[f"deck_{deck.deck_id}_daily_new_limit"] = NEW_LIMIT_ERROR
    return errors


def _is_valid_retention(raw_value: str) -> bool:
    try:
        value = float(raw_value)
    except ValueError:
        return False
    return 0 < value < 1


def _is_valid_new_limit(raw_value: str) -> bool:
    try:
        value = int(raw_value)
    except ValueError:
        return False
    return value >= 0


def _is_valid_target_count(raw_value: str) -> bool:
    try:
        value = int(raw_value)
    except ValueError:
        return False
    return value >= 1


def _format_retention(value: float) -> str:
    return f"{value:.2f}"
