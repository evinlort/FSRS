import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from czech_vocab.repositories import (
    AppSettingsRepository,
    CardCreate,
    CardRepository,
    DeckRepository,
    ReviewLogRecord,
    initialize_database,
)
from czech_vocab.web.app import create_app


def test_app_startup_bootstraps_sqlite_schema(tmp_path: Path) -> None:
    instance_path = tmp_path / "instance"
    database_path = instance_path / "cards.sqlite3"

    create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": database_path,
        },
        instance_path=instance_path,
    )

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()

    assert {"cards", "review_logs", "decks", "app_settings"} <= {name for (name,) in rows}
    settings = AppSettingsRepository(database_path).get_settings()
    default_deck = DeckRepository(database_path).get_default_deck()
    assert settings.default_desired_retention == 0.90
    assert settings.default_daily_new_limit == 20
    assert default_deck.name == "Основная"


def test_create_and_fetch_card_by_id_and_identity_key(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")

    created = repository.create_card(
        CardCreate(
            identity_key="identity-1",
            lemma="kniha",
            translation="книга",
            notes="common noun",
            metadata={"level": "A1"},
            fsrs_state={"state": "learning"},
            due_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
            last_review_at=None,
        ),
    )

    assert repository.get_card_by_id(created.id) == created
    assert repository.get_card_by_identity_key("identity-1") == created


def test_update_imported_content_preserves_schedule_state(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    due_at = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
    created = repository.create_card(
        CardCreate(
            identity_key="identity-2",
            lemma="vlak",
            translation="поезд",
            notes="old note",
            metadata={"topic": "travel"},
            fsrs_state={"state": "review", "stability": 5.2},
            due_at=due_at,
            last_review_at=datetime(2026, 3, 10, 8, 0, tzinfo=UTC),
        ),
    )

    repository.update_imported_content(
        card_id=created.id,
        lemma="vlak nový",
        translation="поезд новый",
        notes="new note",
        metadata={"topic": "transport"},
    )

    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    assert updated.lemma == "vlak nový"
    assert updated.translation == "поезд новый"
    assert updated.notes == "new note"
    assert updated.metadata == {"topic": "transport"}
    assert updated.fsrs_state == {"state": "review", "stability": 5.2}
    assert updated.due_at == due_at


def test_insert_review_log_and_read_it_back(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    created = repository.create_card(
        CardCreate(
            identity_key="identity-3",
            lemma="pes",
            translation="собака",
            notes="",
            metadata={},
            fsrs_state={"state": "learning"},
            due_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
            last_review_at=None,
        ),
    )
    reviewed_at = datetime(2026, 3, 14, 11, 0, tzinfo=UTC)

    repository.insert_review_log(
        card_id=created.id,
        rating="Good",
        reviewed_at=reviewed_at,
        review_duration_seconds=17,
    )

    assert repository.list_review_logs(created.id) == [
        ReviewLogRecord(
            card_id=created.id,
            rating="Good",
            reviewed_at=reviewed_at,
            review_duration_seconds=17,
        ),
    ]


def test_query_due_cards_and_search_cards(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    now = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    due_earlier = repository.create_card(
        CardCreate(
            identity_key="identity-4",
            lemma="auto",
            translation="машина",
            notes="vehicle",
            metadata={},
            fsrs_state={"state": "review"},
            due_at=now - timedelta(days=2),
            last_review_at=None,
        ),
    )
    due_later = repository.create_card(
        CardCreate(
            identity_key="identity-5",
            lemma="dum",
            translation="дом",
            notes="building",
            metadata={},
            fsrs_state={"state": "review"},
            due_at=now - timedelta(hours=1),
            last_review_at=None,
        ),
    )
    repository.create_card(
        CardCreate(
            identity_key="identity-6",
            lemma="jablko",
            translation="яблоко",
            notes="fruit",
            metadata={},
            fsrs_state={"state": "review"},
            due_at=now + timedelta(days=1),
            last_review_at=None,
        ),
    )

    assert [card.id for card in repository.query_due_cards(now)] == [
        due_earlier.id,
        due_later.id,
    ]
    assert [card.lemma for card in repository.search_cards("маш")] == ["auto"]


def test_cards_can_share_identity_across_different_decks(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    deck_repository = DeckRepository(tmp_path / "cards.sqlite3")
    second_deck = deck_repository.create_deck(
        name="Путешествия",
        desired_retention=0.88,
        daily_new_limit=12,
    )

    first_card = repository.create_card(
        CardCreate(
            identity_key="identity-shared",
            lemma="kniha",
            translation="книга",
            notes="deck one",
            metadata={},
            fsrs_state={},
            due_at=None,
            last_review_at=None,
        ),
    )
    second_card = repository.create_card(
        CardCreate(
            identity_key="identity-shared",
            lemma="kniha",
            translation="книга",
            notes="deck two",
            metadata={},
            fsrs_state={},
            due_at=None,
            last_review_at=None,
            deck_id=second_deck.id,
        ),
    )

    assert first_card.deck_id != second_card.deck_id
    assert repository.get_card_by_identity_key("identity-shared", deck_id=1) == first_card
    assert (
        repository.get_card_by_identity_key("identity-shared", deck_id=second_deck.id)
        == second_card
    )


def build_repository(database_path: Path) -> CardRepository:
    initialize_database(database_path)
    return CardRepository(database_path)
