from pathlib import Path
from typing import Any

from flask import Flask

from czech_vocab.repositories.schema import initialize_database
from czech_vocab.web.routes import main_bp

DEFAULT_DATABASE_NAME = "czech_vocab.sqlite3"


def create_app(
    test_config: dict[str, Any] | None = None,
    *,
    instance_path: Path | None = None,
) -> Flask:
    app = Flask(
        __name__,
        instance_path=str(instance_path) if instance_path else None,
        instance_relative_config=True,
    )
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        DATABASE_PATH=Path(app.instance_path) / DEFAULT_DATABASE_NAME,
    )
    if test_config:
        app.config.update(test_config)
    initialize_database(Path(app.config["DATABASE_PATH"]))
    app.register_blueprint(main_bp)
    return app
