from flask import Blueprint, current_app, render_template, request

from czech_vocab.services import ImportService

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
