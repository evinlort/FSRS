import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def app(tmp_path: Path):
    from czech_vocab.web.app import create_app

    instance_path = tmp_path / "instance"
    database_path = instance_path / "test.sqlite3"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": database_path,
        },
        instance_path=instance_path,
    )

    return app


@pytest.fixture
def client(app):
    return app.test_client()
