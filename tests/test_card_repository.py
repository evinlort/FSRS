import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from czech_vocab.repositories import (
    AppSettingsRepository,
    CardCreate,
    CardRepository,
    CardReviewStateRecord,
    DeckRepository,
    ReviewLogRecord,
    build_identity_key,
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

    assert {
        "cards",
        "review_logs",
        "card_review_states",
        "decks",
        "app_settings",
        "import_previews",
        "deck_cards",
        "deck_population_drafts",
    } <= {
        name for (name,) in rows
    }
    settings = AppSettingsRepository(database_path).get_settings()
    default_deck = DeckRepository(database_path).get_default_deck()
    assert settings.default_desired_retention == 0.90
    assert settings.default_daily_new_limit == 20
    assert settings.default_target_deck_card_count == 20
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
    assert updated.identity_key == build_identity_key("vlak nový", "поезд новый")
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

    logs = repository.list_review_logs(created.id)

    assert len(logs) == 1
    assert logs[0] == ReviewLogRecord(
        id=logs[0].id,
        card_id=created.id,
        direction="cz_to_ru",
        rating="Good",
        reviewed_at=reviewed_at,
        review_duration_seconds=17,
        undone_at=None,
    )


def test_get_review_state_defaults_to_forward_direction(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    due_at = datetime(2026, 3, 14, 10, 0, tzinfo=UTC)
    created = repository.create_card(
        CardCreate(
            identity_key="identity-forward",
            lemma="kniha",
            translation="книга",
            notes="common noun",
            metadata={"level": "A1"},
            fsrs_state={"state": "learning"},
            due_at=due_at,
            last_review_at=None,
        ),
    )

    assert repository.get_review_state(created.id) == CardReviewStateRecord(
        card_id=created.id,
        direction="cz_to_ru",
        fsrs_state={"state": "learning"},
        due_at=due_at,
        last_review_at=None,
        created_at=repository.get_review_state(created.id).created_at,
        updated_at=repository.get_review_state(created.id).updated_at,
    )


def test_reverse_schedule_state_is_stored_without_overwriting_forward_state(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    forward_due = datetime(2026, 3, 14, 10, 0, tzinfo=UTC)
    reverse_due = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)
    created = repository.create_card(
        CardCreate(
            identity_key="identity-reverse",
            lemma="pes",
            translation="собака",
            notes="animal",
            metadata={},
            fsrs_state={"state": "learning"},
            due_at=forward_due,
            last_review_at=None,
        ),
    )

    repository.update_schedule_state(
        card_id=created.id,
        direction="ru_to_cz",
        fsrs_state={"state": "review", "stability": 3.2},
        due_at=reverse_due,
        last_review_at=forward_due,
    )

    forward_state = repository.get_review_state(created.id, direction="cz_to_ru")
    reverse_state = repository.get_review_state(created.id, direction="ru_to_cz")
    stored = repository.get_card_by_id(created.id)

    assert forward_state is not None
    assert reverse_state is not None
    assert forward_state.due_at == forward_due
    assert reverse_state.due_at == reverse_due
    assert reverse_state.last_review_at == forward_due
    assert stored is not None
    assert stored.due_at == forward_due


def test_list_review_logs_can_filter_by_direction(tmp_path: Path) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    created = repository.create_card(
        CardCreate(
            identity_key="identity-logs",
            lemma="most",
            translation="мост",
            notes="bridge",
            metadata={},
            fsrs_state={"state": "learning"},
            due_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
            last_review_at=None,
        ),
    )
    reviewed_at = datetime(2026, 3, 14, 11, 0, tzinfo=UTC)

    repository.insert_review_log(
        card_id=created.id,
        direction="cz_to_ru",
        rating="Good",
        reviewed_at=reviewed_at,
        review_duration_seconds=17,
    )
    repository.insert_review_log(
        card_id=created.id,
        direction="ru_to_cz",
        rating="Again",
        reviewed_at=reviewed_at + timedelta(minutes=5),
        review_duration_seconds=21,
    )

    assert [log.direction for log in repository.list_review_logs(created.id)] == [
        "cz_to_ru",
        "ru_to_cz",
    ]
    reverse_logs = repository.list_review_logs(created.id, direction="ru_to_cz")

    assert [log.direction for log in reverse_logs] == ["ru_to_cz"]


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


def test_update_card_content_moves_card_between_decks_without_changing_card_id(
    tmp_path: Path,
) -> None:
    repository = build_repository(tmp_path / "cards.sqlite3")
    deck_repository = DeckRepository(tmp_path / "cards.sqlite3")
    second_deck = deck_repository.create_deck(
        name="Путешествия",
        desired_retention=0.88,
        daily_new_limit=12,
    )

    created = repository.create_card(
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

    repository.update_card_content(
        card_id=created.id,
        deck_id=second_deck.id,
        identity_key="identity-shared",
        lemma="kniha",
        translation="книга",
        notes="deck two",
        metadata={"topic": "travel"},
    )

    updated = repository.get_card_by_id(created.id)
    assert updated is not None
    assert updated.id == created.id
    assert updated.deck_id == second_deck.id
    assert updated.notes == "deck two"
    assert updated.metadata == {"topic": "travel"}
    assert repository.get_card_by_identity_key("identity-shared", deck_id=1) is None
    assert repository.get_card_by_identity_key("identity-shared", deck_id=second_deck.id) == updated


def build_repository(database_path: Path) -> CardRepository:
    initialize_database(database_path)
    return CardRepository(database_path)
