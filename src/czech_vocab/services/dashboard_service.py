from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from czech_vocab.repositories import CardRepository
from czech_vocab.repositories.records import serialize_datetime


@dataclass(frozen=True)
class DashboardData:
    total_cards: int
    due_cards: int


class DashboardService:
    def __init__(self, database_path: Path) -> None:
        self._repository = CardRepository(database_path)

    def get_dashboard_data(self, *, now: datetime) -> DashboardData:
        with self._repository.connect() as connection:
            total_cards = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            due_cards = connection.execute(
                "SELECT COUNT(*) FROM cards WHERE due_at IS NOT NULL AND due_at <= ?",
                (serialize_datetime(now),),
            ).fetchone()[0]
        return DashboardData(total_cards=total_cards, due_cards=due_cards)
