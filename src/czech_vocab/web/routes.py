from datetime import UTC, datetime

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from czech_vocab.services import CardCatalogService, ImportService, StudyService

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def home() -> str:
    return render_template("home.html")


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
    review_card = service.get_next_due_card(now=datetime.now(UTC))
    return render_template("review.html", review_card=review_card)


@main_bp.post("/review/<int:card_id>/grade")
def submit_review(card_id: int):
    service = StudyService(current_app.config["DATABASE_PATH"])
    rating = request.form.get("rating", "")
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
    return redirect(url_for("main.review_page"))


@main_bp.get("/cards")
def cards_page() -> str:
    service = CardCatalogService(current_app.config["DATABASE_PATH"])
    query = request.args.get("q", "")
    page = _parse_page(request.args.get("page", "1"))
    catalog_page = service.get_page(query=query, page=page)
    return render_template("cards.html", catalog_page=catalog_page)


def _parse_page(raw_page: str) -> int:
    try:
        return int(raw_page)
    except ValueError:
        return 1
