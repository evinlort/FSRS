from datetime import UTC, datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from czech_vocab.repositories.records import (
    UndoReviewSnapshot,
    parse_datetime,
    serialize_datetime,
)
from czech_vocab.services import (
    CardCatalogService,
    CardEditForm,
    CardEditMetadataRow,
    CardEditService,
    DashboardService,
    DeckAddService,
    DeckCreateService,
    DeckPopulationService,
    DeckSettingsService,
    ImportService,
    SettingsPageService,
    SettingsValidationError,
    StatsService,
    StudyService,
)

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def home() -> str:
    service = DashboardService(current_app.config["DATABASE_PATH"])
    dashboard = service.get_dashboard_data(now=datetime.now(UTC))
    return render_template("home.html", dashboard=dashboard)


@main_bp.get("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.svg"))


@main_bp.get("/import")
def import_page() -> str:
    return _render_import_page()


@main_bp.get("/decks/new")
def new_deck_page() -> str:
    return _render_new_deck_page()


@main_bp.post("/decks/new")
def create_deck_page():
    service = DeckPopulationService(current_app.config["DATABASE_PATH"])
    form_state = _new_deck_form_state(service)
    errors = _validate_new_deck_form(form_state)
    if errors:
        return _render_new_deck_page(form_state=form_state, errors=errors), 400
    if form_state["mode"] in {"manual", "mixed"}:
        draft_service = DeckCreateService(current_app.config["DATABASE_PATH"])
        try:
            token = draft_service.start_create_flow(
                deck_name=form_state["deck_name"],
                requested_count=form_state["requested_count"],
                mode=form_state["mode"],
                save_default_count=form_state["save_default_count"],
            )
        except ValueError as exc:
            return _render_new_deck_page(
                form_state=form_state,
                errors={"form": _new_deck_error_message(str(exc))},
            ), 400
        return redirect(url_for("main.deck_draft_selection_page", token=token))
    try:
        result = service.create_random_deck(
            deck_name=form_state["deck_name"],
            requested_count=form_state["requested_count"],
            save_default_count=form_state["save_default_count"],
        )
    except ValueError as exc:
        return _render_new_deck_page(
            form_state=form_state,
            errors={"form": _new_deck_error_message(str(exc))},
        ), 400
    flash(_deck_created_flash(result.deck_name, result.assigned_count), "success")
    return redirect(url_for("main.home"))


@main_bp.get("/decks/<int:deck_id>/add")
def add_to_deck_page(deck_id: int):
    try:
        deck = _get_deck(deck_id)
    except LookupError as exc:
        return str(exc), 404
    return _render_deck_add_page(deck)


@main_bp.post("/decks/<int:deck_id>/add")
def submit_add_to_deck_page(deck_id: int):
    try:
        deck = _get_deck(deck_id)
    except LookupError as exc:
        return str(exc), 404
    service = DeckPopulationService(current_app.config["DATABASE_PATH"])
    form_state = _deck_add_form_state(service)
    errors = _validate_deck_add_form(form_state)
    if errors:
        return _render_deck_add_page(deck, form_state=form_state, errors=errors), 400
    if form_state["mode"] in {"manual", "mixed"}:
        draft_service = DeckAddService(current_app.config["DATABASE_PATH"])
        try:
            token = draft_service.start_add_flow(
                deck_id=deck.id,
                requested_count=form_state["requested_count"],
                mode=form_state["mode"],
                save_default_count=form_state["save_default_count"],
            )
        except (LookupError, ValueError) as exc:
            return _render_deck_add_page(
                deck,
                form_state=form_state,
                errors={"form": _deck_add_error_message(str(exc))},
            ), 400
        return redirect(url_for("main.deck_draft_selection_page", token=token))
    try:
        result = service.add_random_cards_to_deck(
            deck_id=deck.id,
            requested_count=form_state["requested_count"],
            save_default_count=form_state["save_default_count"],
        )
    except ValueError as exc:
        return _render_deck_add_page(
            deck,
            form_state=form_state,
            errors={"form": _deck_add_error_message(str(exc))},
        ), 400
    flash(_deck_added_flash(result.deck_name, result.assigned_count), "success")
    return redirect(url_for("main.home"))


@main_bp.get("/deck-drafts/<token>/select")
def deck_draft_selection_page(token: str):
    try:
        page_data, context = _load_draft_page(token)
    except LookupError:
        return "Draft not found", 404
    return _render_deck_draft_page(page_data, **context)


@main_bp.post("/deck-drafts/<token>/select")
def update_deck_draft_selection_page(token: str):
    action = request.form.get("action", "update")
    selected_ids = _selected_card_ids_from_request()
    search_in = request.form.get("search_in", "czech")
    query = request.form.get("q", "")
    try:
        service, context, success_message = _draft_controller(token)
    except LookupError:
        return "Draft not found", 404
    try:
        if action == "confirm":
            confirm_method = getattr(service, "confirm_create_flow", None) or getattr(
                service,
                "confirm_add_flow",
            )
            result = confirm_method(
                token=token,
                selected_card_ids=selected_ids,
                search_in=search_in,
                query=query,
            )
            flash(success_message(result.deck_name, result.assigned_count), "success")
            return redirect(url_for("main.home"))
        page_data = service.update_draft_page(
            token=token,
            selected_card_ids=selected_ids,
            search_in=search_in,
            query=query,
        )
    except ValueError as exc:
        try:
            page_data = service.update_draft_page(
                token=token,
                selected_card_ids=selected_ids[:0] if "exceed" in str(exc) else selected_ids,
                search_in=search_in,
                query=query,
            )
        except LookupError:
            return "Draft not found", 404
        return _render_deck_draft_page(
            page_data,
            error=_draft_error_message(str(exc)),
            **context,
        ), 400
    return _render_deck_draft_page(page_data, **context)


@main_bp.post("/import/preview")
def preview_import() -> str:
    file = request.files.get("csv_file")
    if file is None or file.filename == "":
        return _render_import_page(
            error_title="Файл не выбран.",
            error_message="Выберите CSV-файл и попробуйте снова.",
        )
    service = ImportService(current_app.config["DATABASE_PATH"])
    preview = service.create_preview_from_bytes(file.read())
    if preview.error_message:
        error_title, error_message = _preview_error_context(preview.error_message)
        return _render_import_page(
            preview=preview,
            error_title=error_title,
            error_message=error_message,
            error_details=[preview.error_message],
        )
    return _render_import_page(preview=preview)


@main_bp.post("/import/confirm")
def confirm_import() -> str:
    preview_token = request.form.get("preview_token", "")
    service = ImportService(current_app.config["DATABASE_PATH"])
    try:
        result = service.confirm_preview(preview_token)
    except LookupError:
        return _render_import_page(
            error_title="Предпросмотр недоступен.",
            error_message="Загрузите CSV-файл заново, чтобы подтвердить импорт.",
        )
    return _render_import_page(result=result)


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
        undo_available=_session_undo_snapshot(selected_deck.id) is not None,
    )


@main_bp.post("/review/<int:card_id>/grade")
def submit_review(card_id: int):
    service = StudyService(current_app.config["DATABASE_PATH"])
    rating = request.form.get("rating", "")
    deck_id = request.form.get("deck", "")
    try:
        result = service.submit_review(
            card_id=card_id,
            rating=rating,
            review_at=datetime.now(UTC),
        )
    except ValueError as exc:
        return str(exc), 400
    except LookupError as exc:
        return str(exc), 404
    session["review_undo"] = _serialize_undo_snapshot(result.undo_snapshot)
    flash("Последний ответ сохранён.", "success")
    if deck_id:
        return redirect(url_for("main.review_page", deck=deck_id))
    return redirect(url_for("main.review_page"))


@main_bp.post("/review/undo")
def undo_review():
    service = StudyService(current_app.config["DATABASE_PATH"])
    deck_id = request.form.get("deck", "")
    snapshot = _session_undo_snapshot(_parse_page(deck_id) if deck_id else None)
    session.pop("review_undo", None)
    if snapshot is None:
        flash("Последний ответ уже нельзя отменить.", "warning")
        return _redirect_to_review(deck_id)
    try:
        service.undo_review(snapshot=snapshot, undone_at=datetime.now(UTC))
    except (LookupError, ValueError):
        flash("Последний ответ уже нельзя отменить.", "warning")
        return _redirect_to_review(deck_id or str(snapshot.deck_id))
    flash("Последний ответ отменён.", "success")
    return _redirect_to_review(str(snapshot.deck_id))


@main_bp.get("/cards")
def cards_page() -> str:
    service = CardCatalogService(current_app.config["DATABASE_PATH"])
    catalog_page = service.get_page(
        now=datetime.now(UTC),
        deck=request.args.get("deck", "all"),
        status=request.args.get("status", "all"),
        search_in=request.args.get("search_in", "all"),
        query=request.args.get("q", ""),
        page=_parse_page(request.args.get("page", "1")),
    )
    return render_template("cards.html", catalog_page=catalog_page)


@main_bp.get("/cards/<int:card_id>/edit")
def edit_card_page(card_id: int) -> str:
    service = CardEditService(current_app.config["DATABASE_PATH"])
    try:
        form = service.get_form(card_id)
    except LookupError as exc:
        return str(exc), 404
    return render_template("card_edit.html", card_form=form, decks=service.list_decks(), error=None)


@main_bp.post("/cards/<int:card_id>/edit")
def update_card_page(card_id: int):
    service = CardEditService(current_app.config["DATABASE_PATH"])
    form = _edit_form_from_request(card_id)
    try:
        updated = service.update_card(
            card_id=card_id,
            deck_id=form.deck_id,
            lemma=form.lemma,
            translation=form.translation,
            notes=form.notes,
            metadata_rows=[(item.key, item.value) for item in form.metadata_rows],
        )
    except ValueError as exc:
        return render_template(
            "card_edit.html",
            card_form=form,
            decks=service.list_decks(),
            error=str(exc),
        )
    except LookupError as exc:
        return str(exc), 404
    return redirect(url_for("main.cards_page", deck=updated.deck_id))


@main_bp.get("/stats")
def stats_page() -> str:
    service = StatsService(current_app.config["DATABASE_PATH"])
    stats = service.get_stats(now=datetime.now(UTC), deck=request.args.get("deck", "all"))
    return render_template("stats.html", stats=stats)


@main_bp.get("/settings")
def settings_page() -> str:
    return _render_settings_page()


@main_bp.post("/settings")
def update_settings_page():
    service = SettingsPageService(current_app.config["DATABASE_PATH"])
    try:
        service.update_settings(**_settings_form_payload(service))
    except SettingsValidationError as exc:
        return render_template("settings.html", settings_page=exc.page_data), 400
    flash("Настройки сохранены.", "success")
    return redirect(url_for("main.settings_page"))


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


def _render_import_page(
    *,
    preview=None,
    result=None,
    error_title: str | None = None,
    error_message: str | None = None,
    error_details: list[str] | None = None,
) -> str:
    return render_template(
        "import.html",
        preview=preview,
        result=result,
        error_title=error_title,
        error_message=error_message,
        error_details=error_details or [],
    )


def _render_settings_page() -> str:
    service = SettingsPageService(current_app.config["DATABASE_PATH"])
    return render_template("settings.html", settings_page=service.get_page_data())


def _render_new_deck_page(
    *,
    form_state: dict[str, object] | None = None,
    errors: dict[str, str] | None = None,
) -> str:
    service = DeckPopulationService(current_app.config["DATABASE_PATH"])
    default_count = service.get_default_target_count()
    state = form_state or {
        "deck_name": "",
        "requested_count": default_count,
        "mode": "random",
        "save_default_count": False,
    }
    return render_template(
        "deck_create.html",
        form_state=state,
        available_count=service.count_available_cards(),
        errors=errors or {},
    )


def _render_deck_add_page(
    deck,
    *,
    form_state: dict[str, object] | None = None,
    errors: dict[str, str] | None = None,
) -> str:
    service = DeckPopulationService(current_app.config["DATABASE_PATH"])
    default_count = service.get_default_target_count()
    state = form_state or {
        "requested_count_raw": "",
        "requested_count": default_count,
        "mode": "random",
        "save_default_count": False,
    }
    return render_template(
        "deck_add.html",
        deck=deck,
        form_state=state,
        available_count=service.count_available_cards(),
        errors=errors or {},
    )


def _render_deck_draft_page(
    page_data,
    *,
    error: str | None = None,
    selection_intro: str,
    submit_label: str,
    availability_note: str,
) -> str:
    return render_template(
        "deck_select.html",
        draft_page=page_data,
        error=error,
        selection_intro=selection_intro,
        submit_label=submit_label,
        availability_note=availability_note,
    )


def _settings_form_payload(service: SettingsPageService) -> dict[str, object]:
    page_data = service.get_page_data()
    return {
        "default_desired_retention": request.form.get("default_desired_retention", ""),
        "default_daily_new_limit": request.form.get("default_daily_new_limit", ""),
        "default_target_deck_card_count": request.form.get(
            "default_target_deck_card_count",
            "",
        ),
        "deck_updates": {
            deck.deck_id: {
                "desired_retention": request.form.get(
                    f"deck_{deck.deck_id}_desired_retention",
                    "",
                ),
                "daily_new_limit": request.form.get(
                    f"deck_{deck.deck_id}_daily_new_limit",
                    "",
                ),
            }
            for deck in page_data.decks
        },
    }


def _new_deck_form_state(service: DeckPopulationService) -> dict[str, object]:
    requested_raw = request.form.get("requested_count", "").strip()
    default_count = service.get_default_target_count()
    return {
        "deck_name": request.form.get("deck_name", "").strip(),
        "requested_count_raw": requested_raw,
        "requested_count": _parse_positive_int(requested_raw, default_count),
        "mode": request.form.get("mode", "random"),
        "save_default_count": request.form.get("save_default_count") == "on",
    }


def _deck_add_form_state(service: DeckPopulationService) -> dict[str, object]:
    requested_raw = request.form.get("requested_count", "").strip()
    default_count = service.get_default_target_count()
    return {
        "requested_count_raw": requested_raw,
        "requested_count": _parse_positive_int(requested_raw, default_count),
        "mode": request.form.get("mode", "random"),
        "save_default_count": request.form.get("save_default_count") == "on",
    }


def _validate_new_deck_form(form_state: dict[str, object]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not form_state["deck_name"]:
        errors["deck_name"] = "Введите название колоды."
    if form_state["mode"] not in {"random", "manual", "mixed"}:
        errors["form"] = "Выберите режим заполнения колоды."
    if not _is_positive_int(form_state["requested_count_raw"]):
        errors["requested_count"] = "Количество карточек должно быть целым числом 1 или больше."
    return errors


def _validate_deck_add_form(form_state: dict[str, object]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if form_state["mode"] not in {"random", "manual", "mixed"}:
        errors["form"] = "Выберите режим добавления карточек."
    if not _is_positive_int(form_state["requested_count_raw"]):
        errors["requested_count"] = "Количество карточек должно быть целым числом 1 или больше."
    return errors


def _parse_positive_int(raw_value: str, default_value: int) -> int:
    if not raw_value:
        return default_value
    try:
        parsed = int(raw_value)
    except ValueError:
        return default_value
    return parsed


def _is_positive_int(raw_value: str) -> bool:
    try:
        return int(raw_value) >= 1
    except ValueError:
        return False


def _new_deck_error_message(message: str) -> str:
    if message == "Deck already exists.":
        return "Колода с таким названием уже существует."
    if message == "No available cards.":
        return "Свободных карточек пока нет. Сначала импортируйте слова в глобальную базу."
    return "Не удалось создать колоду. Проверьте данные и попробуйте снова."


def _draft_error_message(message: str) -> str:
    if "cannot exceed" in message:
        return "Нельзя выбрать больше карточек, чем запрошено."
    if "empty" in message:
        return "Выберите хотя бы одну карточку."
    if "available" in message:
        return "Выбранные карточки больше недоступны."
    if "already exists" in message:
        return "Колода с таким названием уже существует."
    return "Не удалось применить выбор карточек."


def _deck_created_flash(deck_name: str, assigned_count: int) -> str:
    return f"Колода «{deck_name}» создана. Добавлено {assigned_count} карточек."


def _deck_add_error_message(message: str) -> str:
    if message == "No available cards.":
        return "Свободных карточек пока нет. Сначала импортируйте слова в глобальную базу."
    return "Не удалось добавить карточки в колоду. Проверьте данные и попробуйте снова."


def _deck_added_flash(deck_name: str, assigned_count: int) -> str:
    return f"В колоду «{deck_name}» добавлено {assigned_count} карточек."


def _load_draft_page(token: str):
    service, context, _ = _draft_controller(token)
    return service.get_draft_page(token), context


def _draft_controller(token: str):
    service = DeckPopulationService(current_app.config["DATABASE_PATH"])
    draft = service.get_draft(token)
    if draft is None:
        raise LookupError(f"Draft not found: {token}")
    if draft.flow_type == "add":
        return (
            DeckAddService(current_app.config["DATABASE_PATH"]),
            {
                "selection_intro": (
                    "Колода: "
                    f"{draft.deck_name}. Выберите свободные карточки вручную "
                    "или подтвердите смешанное добавление."
                ),
                "submit_label": "Добавить карточки",
                "availability_note": (
                    "Доступны только свободные карточки: текущая колода "
                    "и карточки из других колод здесь не показываются."
                ),
            },
            _deck_added_flash,
        )
    return (
        DeckCreateService(current_app.config["DATABASE_PATH"]),
        {
            "selection_intro": (
                "Колода: "
                f"{draft.deck_name}. Выберите карточки вручную "
                "или подтвердите смешанное заполнение."
            ),
            "submit_label": "Создать колоду",
            "availability_note": (
                "Доступны только свободные карточки: текущая колода "
                "и карточки из других колод здесь не показываются."
            ),
        },
        _deck_created_flash,
    )


def _selected_card_ids_from_request() -> list[int]:
    selected: list[int] = []
    for raw_value in request.form.getlist("selected_card_ids"):
        try:
            selected.append(int(raw_value))
        except ValueError:
            continue
    return selected


def _get_deck(deck_id: int):
    service = DeckSettingsService(current_app.config["DATABASE_PATH"])
    for deck in service.list_decks():
        if deck.id == deck_id:
            return deck
    raise LookupError(f"Deck not found: {deck_id}")


def _preview_error_context(error_message: str) -> tuple[str, str]:
    if error_message.startswith("Missing required headers:"):
        return (
            "Не удалось распознать обязательные заголовки CSV.",
            "Проверьте названия колонок и загрузите файл снова.",
        )
    return (
        "Импорт не выполнен.",
        "Файл не удалось обработать. Проверьте кодировку и попробуйте снова.",
    )


def _redirect_to_review(deck_id: str | None):
    if deck_id:
        return redirect(url_for("main.review_page", deck=deck_id))
    return redirect(url_for("main.review_page"))


def _edit_form_from_request(card_id: int) -> CardEditForm:
    metadata_rows = [
        CardEditMetadataRow(
            request.form[key],
            request.form.get(f"metadata_value_{key.rsplit('_', 1)[-1]}", ""),
        )
        for key in sorted(request.form)
        if key.startswith("metadata_key_")
    ]
    return CardEditForm(
        card_id=card_id,
        deck_id=_parse_page(request.form.get("deck_id", "1")),
        lemma=request.form.get("lemma", ""),
        translation=request.form.get("translation", ""),
        notes=request.form.get("notes", ""),
        metadata_rows=metadata_rows or [CardEditMetadataRow("", "")],
    )


def _serialize_undo_snapshot(snapshot: UndoReviewSnapshot) -> dict[str, object]:
    return {
        "card_id": snapshot.card_id,
        "deck_id": snapshot.deck_id,
        "review_log_id": snapshot.review_log_id,
        "fsrs_state": snapshot.fsrs_state,
        "due_at": serialize_datetime(snapshot.due_at),
        "last_review_at": serialize_datetime(snapshot.last_review_at),
    }


def _session_undo_snapshot(deck_id: int | None) -> UndoReviewSnapshot | None:
    payload = session.get("review_undo")
    if not isinstance(payload, dict):
        return None
    if deck_id is not None and payload.get("deck_id") != deck_id:
        return None
    return UndoReviewSnapshot(
        card_id=payload["card_id"],
        deck_id=payload["deck_id"],
        review_log_id=payload["review_log_id"],
        fsrs_state=payload["fsrs_state"],
        due_at=parse_datetime(payload["due_at"]),
        last_review_at=parse_datetime(payload["last_review_at"]),
    )
