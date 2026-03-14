from datetime import UTC, datetime

from czech_vocab.domain import FsrsScheduler
from czech_vocab.repositories import CardCreate, CardRepository, build_identity_key
from czech_vocab.services import DeckSettingsService


def test_edit_page_renders_all_editable_fields(client, app) -> None:
    card = create_editable_card(
        app.config["DATABASE_PATH"],
        lemma="kniha",
        translation="книга",
        notes="book note",
        metadata={"cefr_level": "A1", "topic": "study"},
    )

    response = client.get(f"/cards/{card.id}/edit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="lemma"' in page
    assert 'name="translation"' in page
    assert 'name="notes"' in page
    assert 'name="deck_id"' in page
    assert 'name="metadata_key_1"' in page
    assert 'name="metadata_value_1"' in page
    assert "cefr_level" in page
    assert "A1" in page


def test_edit_page_updates_card_and_redirects_to_target_deck_catalog(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    card = create_editable_card(
        database_path,
        lemma="kniha",
        translation="книга",
        notes="book note",
        metadata={"topic": "study"},
    )
    target_deck = DeckSettingsService(database_path).create_deck("Путешествия")
    repository = CardRepository(database_path)

    response = client.post(
        f"/cards/{card.id}/edit",
        data={
            "deck_id": str(target_deck.id),
            "lemma": "kniha nova",
            "translation": "новая книга",
            "notes": "updated note",
            "metadata_key_1": " CEFR Level ",
            "metadata_value_1": "A2",
            "metadata_key_2": "topic-name",
            "metadata_value_2": "travel",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/cards?deck={target_deck.id}")
    updated = repository.get_card_by_id(card.id)
    assert updated is not None
    assert updated.deck_id == target_deck.id
    assert updated.lemma == "kniha nova"
    assert updated.translation == "новая книга"
    assert updated.notes == "updated note"
    assert updated.metadata == {"cefr_level": "A2", "topic_name": "travel"}


def test_edit_page_preserves_input_on_validation_error(client, app) -> None:
    card = create_editable_card(
        app.config["DATABASE_PATH"],
        lemma="pes",
        translation="собака",
        notes="animal",
        metadata={"topic": "home"},
    )

    response = client.post(
        f"/cards/{card.id}/edit",
        data={
            "deck_id": "1",
            "lemma": "",
            "translation": "собака новая",
            "notes": "changed",
            "metadata_key_1": "source tag",
            "metadata_value_1": "edited",
        },
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Заполните чешское слово и перевод." in page
    assert 'value="собака новая"' in page
    assert ">changed</textarea>" in page
    assert 'value="source tag"' in page
    assert 'value="edited"' in page


def test_edit_page_shows_duplicate_collision_without_changing_card(client, app) -> None:
    database_path = app.config["DATABASE_PATH"]
    first = create_editable_card(database_path, lemma="pes", translation="собака")
    second = create_editable_card(database_path, lemma="kocka", translation="кошка")
    repository = CardRepository(database_path)

    response = client.post(
        f"/cards/{second.id}/edit",
        data={
            "deck_id": str(first.deck_id),
            "lemma": "pes",
            "translation": "собака",
            "notes": "duplicate",
        },
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "В этой колоде уже есть карточка с таким словом и переводом." in page
    unchanged = repository.get_card_by_id(second.id)
    assert unchanged is not None
    assert unchanged.lemma == "kocka"
    assert unchanged.translation == "кошка"


def create_editable_card(
    database_path,
    *,
    lemma: str,
    translation: str,
    notes: str = "",
    metadata: dict[str, str] | None = None,
):
    repository = CardRepository(database_path)
    scheduler = FsrsScheduler(enable_fuzzing=False)
    due_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    created = repository.create_card(
        CardCreate(
            identity_key=build_identity_key(lemma, translation),
            lemma=lemma,
            translation=translation,
            notes=notes,
            metadata=metadata or {},
            fsrs_state=scheduler.create_default_state(card_id=0, now=due_at),
            due_at=due_at,
            last_review_at=None,
        )
    )
    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    return updated
