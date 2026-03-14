from datetime import UTC, datetime

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from czech_vocab.services import (
    CardCatalogService,
    DashboardService,
    DeckSettingsService,
    ImportService,
    StudyService,
)

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def home() -> str:
    service = DashboardService(current_app.config["DATABASE_PATH"])
    dashboard = service.get_dashboard_data(now=datetime.now(UTC))
    return render_template("home.html", dashboard=dashboard)


@main_bp.get("/import")
def import_page() -> str:
    return render_template("import.html", summary=None)


@main_bp.post("/import")
def import_csv() -> str:
    file = request.files.get("csv_file")
    if file is None or file.filename == "":
        summary = {"created_count": 0, "updated_count": 0, "rejected_count": 0, "messages": []}
        summary["messages"].append("Please choose a CSV file.")
        return render_template("import.html", summary=summary)
    service = ImportService(current_app.config["DATABASE_PATH"])
    summary = service.import_csv_bytes(file.read())
    return render_template("import.html", summary=summary)


@main_bp.get("/review")
def review_page() -> str:
    service = StudyService(current_app.config["DATABASE_PATH"])
    deck_service = DeckSettingsService(current_app.config["DATABASE_PATH"])
    requested_deck_id = None
    if request.args.get("deck"):
        requested_deck_id = _parse_page(request.args.get("deck", ""))
    selected_deck = _resolve_deck(deck_service, requested_deck_id)
    queue_state = service.get_queue_state(now=datetime.now(UTC), deck_id=selected_deck.id)
    return render_template(
        "review.html",
        review_card=queue_state.card,
        review_empty_reason=queue_state.empty_reason,
        review_deck=selected_deck,
    )


@main_bp.post("/review/<int:card_id>/grade")
def submit_review(card_id: int):
    service = StudyService(current_app.config["DATABASE_PATH"])
    rating = request.form.get("rating", "")
    deck_id = request.form.get("deck", "")
    try:
        service.submit_review(
            card_id=card_id,
            rating=rating,
            review_at=datetime.now(UTC),
        )
    except ValueError as exc:
        return str(exc), 400
    except LookupError as exc:
        return str(exc), 404
    if deck_id:
        return redirect(url_for("main.review_page", deck=deck_id))
    return redirect(url_for("main.review_page"))


@main_bp.get("/cards")
def cards_page() -> str:
    service = CardCatalogService(current_app.config["DATABASE_PATH"])
    query = request.args.get("q", "")
    page = _parse_page(request.args.get("page", "1"))
    catalog_page = service.get_page(query=query, page=page)
    return render_template("cards.html", catalog_page=catalog_page)


@main_bp.get("/stats")
def stats_page() -> str:
    return render_template(
        "placeholder.html",
        page_name="Статистика",
        page_message="Раздел статистики будет добавлен на следующем UI-шаге.",
    )


@main_bp.get("/settings")
def settings_page() -> str:
    return render_template(
        "placeholder.html",
        page_name="Настройки",
        page_message="Раздел настроек будет добавлен на следующем UI-шаге.",
    )


def _parse_page(raw_page: str) -> int:
    try:
        return int(raw_page)
    except ValueError:
        return 1


def _resolve_deck(deck_service: DeckSettingsService, deck_id: int | None):
    if deck_id is None:
        return deck_service.get_default_deck()
    for deck in deck_service.list_decks():
        if deck.id == deck_id:
            return deck
    return deck_service.get_default_deck()
