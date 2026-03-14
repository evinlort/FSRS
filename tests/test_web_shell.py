from pathlib import Path

from czech_vocab.web.app import create_app


def test_home_page_renders_russian_shell_navigation(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '<html lang="ru">' in page
    assert "<title>Главная" in page
    assert 'href="/static/styles.css"' in page
    assert 'href="/static/favicon.svg"' in page
    assert 'src="/static/app.js"' in page
    assert 'href="#main-content"' in page
    assert 'aria-controls="primary-nav"' in page
    assert 'href="/"' in page
    assert 'href="/import"' in page
    assert 'href="/review"' in page
    assert 'href="/cards"' in page
    assert 'href="/stats"' in page
    assert 'href="/settings"' in page
    assert "Повторение" in page


def test_favicon_route_redirects_to_static_asset(client) -> None:
    response = client.get("/favicon.ico")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/static/favicon.svg")


def test_existing_pages_render_page_titles_inside_shared_layout(client) -> None:
    import_page = client.get("/import")
    review_page = client.get("/review")
    cards_page = client.get("/cards")

    assert "<title>Импорт" in import_page.get_data(as_text=True)
    assert "<title>Повторение" in review_page.get_data(as_text=True)
    assert "<title>Карточки" in cards_page.get_data(as_text=True)


def test_stats_and_settings_pages_render_in_shell(client) -> None:
    stats_page = client.get("/stats")
    settings_page = client.get("/settings")

    assert stats_page.status_code == 200
    assert settings_page.status_code == 200
    assert "<title>Статистика" in stats_page.get_data(as_text=True)
    assert "<title>Настройки" in settings_page.get_data(as_text=True)


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
