from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from czech_vocab.repositories import AppSettingsRepository, CardRepository, DeckRepository

SUCCESS_RATINGS = {"Good", "Easy"}
FAIL_RATINGS = {"Again", "Hard"}


@dataclass(frozen=True)
class StatsDeckOption:
    value: str
    label: str


@dataclass(frozen=True)
class StatsSummaryRow:
    date_text: str
    reviewed_count: int
    success_count: int
    fail_count: int


@dataclass(frozen=True)
class StatsPageData:
    deck_options: list[StatsDeckOption]
    selected_deck: str
    due_today: int
    reviewed_today: int
    success_rate: str
    fail_rate: str
    desired_retention_text: str
    average_interval_text: str
    summary_rows: list[StatsSummaryRow]
    has_history: bool


class StatsService:
    def __init__(self, database_path: Path) -> None:
        self._repository = CardRepository(database_path)
        self._deck_repository = DeckRepository(database_path)
        self._settings_repository = AppSettingsRepository(database_path)

    def get_stats(self, *, now: datetime, deck: str = "all") -> StatsPageData:
        selected_deck = _select_deck(deck, self._deck_repository)
        deck_options = _build_deck_options(self._deck_repository)
        day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        horizon_start = day_start - timedelta(days=29)
        with self._repository.connect() as connection:
            due_today = _count_due_today(connection, selected_deck, day_end)
            reviewed_today = _count_reviews(connection, selected_deck, day_start, day_end)
            success_count, fail_count = _count_outcomes(
                connection,
                selected_deck,
                horizon_start,
                day_end,
            )
            average_interval_text = _average_interval_text(connection, selected_deck)
            summary_rows = _load_summary_rows(connection, selected_deck, horizon_start, day_end)
        desired_retention_text = _desired_retention_text(
            selected_deck,
            self._deck_repository,
            self._settings_repository,
        )
        return StatsPageData(
            deck_options=deck_options,
            selected_deck=selected_deck,
            due_today=due_today,
            reviewed_today=reviewed_today,
            success_rate=_rate_text(success_count, success_count + fail_count),
            fail_rate=_rate_text(fail_count, success_count + fail_count),
            desired_retention_text=desired_retention_text,
            average_interval_text=average_interval_text,
            summary_rows=summary_rows,
            has_history=bool(summary_rows),
        )


def _select_deck(raw_deck: str, deck_repository: DeckRepository) -> str:
    if raw_deck == "all":
        return "all"
    if raw_deck.isdigit() and deck_repository.get_deck_by_id(int(raw_deck)) is not None:
        return raw_deck
    return "all"


def _build_deck_options(deck_repository: DeckRepository) -> list[StatsDeckOption]:
    options = [StatsDeckOption(value="all", label="Все колоды")]
    options.extend(
        StatsDeckOption(value=str(deck.id), label=deck.name)
        for deck in deck_repository.list_decks()
    )
    return options


def _deck_filter_clause(selected_deck: str) -> tuple[str, tuple[object, ...]]:
    if selected_deck == "all":
        return "", ()
    return " AND cards.deck_id = ?", (int(selected_deck),)


def _count_due_today(connection, selected_deck: str, day_end: datetime) -> int:
    where_sql, params = _deck_filter_clause(selected_deck)
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM cards
        WHERE cards.due_at IS NOT NULL
          AND cards.due_at < ?{where_sql}
        """,
        (day_end.isoformat(), *params),
    ).fetchone()
    return row[0]


def _count_reviews(connection, selected_deck: str, day_start: datetime, day_end: datetime) -> int:
    where_sql, params = _deck_filter_clause(selected_deck)
    row = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM review_logs
        JOIN cards ON cards.id = review_logs.card_id
        WHERE review_logs.undone_at IS NULL
          AND review_logs.reviewed_at >= ?
          AND review_logs.reviewed_at < ?{where_sql}
        """,
        (day_start.isoformat(), day_end.isoformat(), *params),
    ).fetchone()
    return row[0]


def _count_outcomes(
    connection,
    selected_deck: str,
    horizon_start: datetime,
    day_end: datetime,
) -> tuple[int, int]:
    where_sql, params = _deck_filter_clause(selected_deck)
    rows = connection.execute(
        f"""
        SELECT review_logs.rating, COUNT(*) AS total
        FROM review_logs
        JOIN cards ON cards.id = review_logs.card_id
        WHERE review_logs.undone_at IS NULL
          AND review_logs.reviewed_at >= ?
          AND review_logs.reviewed_at < ?{where_sql}
        GROUP BY review_logs.rating
        """,
        (horizon_start.isoformat(), day_end.isoformat(), *params),
    ).fetchall()
    success = sum(row["total"] for row in rows if row["rating"] in SUCCESS_RATINGS)
    fail = sum(row["total"] for row in rows if row["rating"] in FAIL_RATINGS)
    return success, fail


def _average_interval_text(connection, selected_deck: str) -> str:
    where_sql, params = _deck_filter_clause(selected_deck)
    rows = connection.execute(
        f"""
        SELECT due_at, last_review_at
        FROM cards
        WHERE due_at IS NOT NULL
          AND last_review_at IS NOT NULL{where_sql}
        """,
        params,
    ).fetchall()
    intervals = []
    for row in rows:
        due_at = datetime.fromisoformat(row["due_at"])
        last_review_at = datetime.fromisoformat(row["last_review_at"])
        seconds = (due_at - last_review_at).total_seconds()
        if seconds > 0:
            intervals.append(seconds / 86400)
    if not intervals:
        return "Нет данных"
    average = sum(intervals) / len(intervals)
    return f"{average:.1f} дн."


def _load_summary_rows(
    connection,
    selected_deck: str,
    horizon_start: datetime,
    day_end: datetime,
) -> list[StatsSummaryRow]:
    where_sql, params = _deck_filter_clause(selected_deck)
    rows = connection.execute(
        f"""
        SELECT
            substr(review_logs.reviewed_at, 1, 10) AS review_date,
            SUM(
                CASE WHEN review_logs.rating IN ('Good', 'Easy') THEN 1 ELSE 0 END
            ) AS success_count,
            SUM(CASE WHEN review_logs.rating IN ('Again', 'Hard') THEN 1 ELSE 0 END) AS fail_count,
            COUNT(*) AS reviewed_count
        FROM review_logs
        JOIN cards ON cards.id = review_logs.card_id
        WHERE review_logs.undone_at IS NULL
          AND review_logs.reviewed_at >= ?
          AND review_logs.reviewed_at < ?{where_sql}
        GROUP BY review_date
        ORDER BY review_date DESC
        LIMIT 10
        """,
        (horizon_start.isoformat(), day_end.isoformat(), *params),
    ).fetchall()
    return [
        StatsSummaryRow(
            date_text=row["review_date"],
            reviewed_count=row["reviewed_count"],
            success_count=row["success_count"],
            fail_count=row["fail_count"],
        )
        for row in rows
    ]


def _desired_retention_text(
    selected_deck: str,
    deck_repository: DeckRepository,
    settings_repository: AppSettingsRepository,
) -> str:
    if selected_deck == "all":
        return f"{settings_repository.get_settings().default_desired_retention:.2f}"
    deck = deck_repository.get_deck_by_id(int(selected_deck))
    assert deck is not None
    return f"{deck.desired_retention:.2f}"


def _rate_text(part: int, total: int) -> str:
    if total == 0:
        return "Нет данных"
    return f"{round(part / total * 100):.0f}%"
