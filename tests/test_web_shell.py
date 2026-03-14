from pathlib import Path

from czech_vocab.web.app import create_app


def test_home_page_renders_navigation(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Czech Vocabulary FSRS" in page
    assert 'href="/import"' in page
    assert 'href="/review"' in page
    assert 'href="/cards"' in page


def test_create_app_accepts_testing_overrides(tmp_path: Path) -> None:
    instance_path = tmp_path / "custom-instance"
    database_path = instance_path / "override.sqlite3"

    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": database_path,
        },
        instance_path=instance_path,
    )

    assert app.config["TESTING"] is True
    assert app.config["DATABASE_PATH"] == database_path
    assert instance_path.is_dir()
