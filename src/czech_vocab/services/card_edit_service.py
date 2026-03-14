from dataclasses import dataclass
from pathlib import Path

from czech_vocab.importers.csv_parser import normalize_header
from czech_vocab.repositories import CardRecord, CardRepository, build_identity_key
from czech_vocab.services.deck_settings_service import DeckSettingsService


@dataclass(frozen=True)
class CardEditMetadataRow:
    key: str
    value: str


@dataclass(frozen=True)
class CardEditForm:
    card_id: int
    deck_id: int
    lemma: str
    translation: str
    notes: str
    metadata_rows: list[CardEditMetadataRow]


class CardEditService:
    def __init__(self, database_path: Path) -> None:
        self._repository = CardRepository(database_path)
        self._deck_settings_service = DeckSettingsService(database_path)

    def get_form(self, card_id: int) -> CardEditForm:
        card = self._get_card(card_id)
        rows = [CardEditMetadataRow(key, value) for key, value in card.metadata.items()]
        rows.append(CardEditMetadataRow("", ""))
        return CardEditForm(
            card_id=card.id,
            deck_id=card.deck_id,
            lemma=card.lemma,
            translation=card.translation,
            notes=card.notes,
            metadata_rows=rows,
        )

    def list_decks(self):
        return self._deck_settings_service.list_decks()

    def update_card(
        self,
        *,
        card_id: int,
        deck_id: int,
        lemma: str,
        translation: str,
        notes: str,
        metadata_rows: list[tuple[str, str]],
    ) -> CardRecord:
        self._get_card(card_id)
        clean_lemma = lemma.strip()
        clean_translation = translation.strip()
        if not clean_lemma or not clean_translation:
            raise ValueError("Заполните чешское слово и перевод.")
        metadata = _normalize_metadata(metadata_rows)
        identity_key = build_identity_key(clean_lemma, clean_translation)
        existing = self._repository.get_card_by_identity_key(identity_key, deck_id=deck_id)
        if existing is not None and existing.id != card_id:
            raise ValueError("В этой колоде уже есть карточка с таким словом и переводом.")
        self._repository.update_card_content(
            card_id=card_id,
            deck_id=deck_id,
            identity_key=identity_key,
            lemma=clean_lemma,
            translation=clean_translation,
            notes=notes.strip(),
            metadata=metadata,
        )
        updated = self._repository.get_card_by_id(card_id)
        assert updated is not None
        return updated

    def _get_card(self, card_id: int) -> CardRecord:
        card = self._repository.get_card_by_id(card_id)
        if card is None:
            raise LookupError(f"Card not found: {card_id}")
        return card


def _normalize_metadata(rows: list[tuple[str, str]]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for raw_key, raw_value in rows:
        key = raw_key.strip()
        value = raw_value.strip()
        if not key or not value:
            continue
        metadata[normalize_header(key)] = value
    return metadata
