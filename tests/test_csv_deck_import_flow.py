import sqlite3
from io import BytesIO

from czech_vocab.repositories import DeckRepository, build_identity_key


def test_home_and_import_page_link_to_csv_deck_creation(client) -> None:
    home_page = client.get('/').get_data(as_text=True)
    import_page = client.get('/import').get_data(as_text=True)

    assert 'href="/decks/import"' in home_page
    assert 'href="/decks/import"' in import_page


def test_get_csv_deck_import_page_renders_form_without_requested_count(client) -> None:
    response = client.get('/decks/import')

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'action="/decks/import/preview"' in page
    assert 'name="deck_name"' in page
    assert 'name="csv_file"' in page
    assert 'name="requested_count"' not in page


def test_preview_and_confirm_csv_deck_creation_flow(client, app) -> None:
    preview_response = client.post(
        '/decks/import/preview',
        data={
            'deck_name': 'CSV deck',
            'csv_file': (
                BytesIO(
                    (
                        'lemma_cs,translation_ru,notes\nkniha,книга,common noun\n'
                        'vlak,поезд,transport\n'
                    ).encode('utf-8')
                ),
                'words.csv',
            ),
        },
        content_type='multipart/form-data',
    )

    assert preview_response.status_code == 200
    preview_page = preview_response.get_data(as_text=True)
    assert 'Предпросмотр создания колоды' in preview_page
    assert 'Назначение: CSV deck' in preview_page
    assert 'Готово для колоды: 2' in preview_page
    assert 'Новых карточек: 2' in preview_page
    assert 'Обновится карточек: 0' in preview_page
    assert 'action="/decks/import/confirm"' in preview_page

    confirm_response = client.post(
        '/decks/import/confirm',
        data={'preview_token': extract_preview_token(preview_page)},
        follow_redirects=True,
    )

    assert confirm_response.status_code == 200
    page = confirm_response.get_data(as_text=True)
    assert 'Колода «CSV deck» создана. Добавлено 2 карточек.' in page
    assert 'CSV deck' in page

    deck = DeckRepository(app.config['DATABASE_PATH']).get_deck_by_name('CSV deck')
    assert deck is not None
    assert count_deck_links(app.config['DATABASE_PATH']) == 2
    stored_card = fetch_card(app.config['DATABASE_PATH'], 'kniha', 'книга')
    assert stored_card is not None
    assert stored_card['deck_id'] == deck.id


def test_preview_requires_deck_name(client) -> None:
    response = client.post(
        '/decks/import/preview',
        data={
            'deck_name': '   ',
            'csv_file': (
                BytesIO('lemma_cs,translation_ru\nkniha,книга\n'.encode('utf-8')),
                'words.csv',
            ),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert 'Введите название колоды.' in page


def test_preview_with_only_invalid_rows_has_no_confirm_button(client) -> None:
    response = client.post(
        '/decks/import/preview',
        data={
            'deck_name': 'CSV deck',
            'csv_file': (BytesIO('lemma_cs,translation_ru\n,книга\n'.encode('utf-8')), 'words.csv'),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'Готово для колоды: 0' in page
    assert 'Нет строк для создания колоды.' in page
    assert 'action="/decks/import/confirm"' not in page


def extract_preview_token(page: str) -> str:
    marker = 'name="preview_token" value="'
    start = page.index(marker) + len(marker)
    end = page.index('"', start)
    return page[start:end]


def count_deck_links(database_path) -> int:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute('SELECT COUNT(*) FROM deck_cards').fetchone()
    return row[0]


def fetch_card(database_path, lemma: str, translation: str):
    identity_key = build_identity_key(lemma, translation)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            """
            SELECT
                cards.identity_key,
                cards.notes,
                cards.due_at,
                cards.fsrs_state_json,
                deck_cards.deck_id AS deck_id
            FROM cards
            LEFT JOIN deck_cards ON deck_cards.card_id = cards.id
            WHERE cards.identity_key = ?
            """,
            (identity_key,),
        ).fetchone()
