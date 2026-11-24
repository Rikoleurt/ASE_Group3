"""Symbol crops, authorization, title conflicts and public tablet ancestry."""
import json
from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from mysql.connector import IntegrityError
from PIL import Image

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.community_data_controller import (
    CommunityDataController, DuplicateDiscussionTitle, find_symbol, symbol_name,
)
from backend.app.image_storage import crop_symbol, image_path, store_image
from backend.app.model.analysis import Box
from backend.tests.test_community import client, summary  # noqa: F401 — shared authenticated fixture
from backend.tests.test_history import png, result


def saved_row(identifier=3, sign_id=1):
    snapshot = result().model_dump(mode='json')
    snapshot['signs'][0]['box'] = {'x': 0.25, 'y': 0.25, 'w': 0.5, 'h': 0.5}
    return dict(id=identifier, analysis_id=12, author_id=7, author_username='owner',
                title='Custom title', created_at=datetime(2026, 11, 24), sign_id=sign_id,
                tablet_filename='HT13.png', result_json=json.dumps(snapshot))


def connection_with_rows(monkeypatch, rows):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = rows
    monkeypatch.setattr('mysql.connector.connect', lambda **kwargs: connection)
    return connection, cursor


def test_crop_contains_only_the_saved_box_pixels():
    source = Image.new('RGB', (8, 8), 'blue')
    source.paste('red', (2, 2, 6, 6))
    encoded = BytesIO()
    source.save(encoded, 'PNG')
    key = store_image(encoded.getvalue(), 'PNG')
    cropped = crop_symbol(key, Box(x=0.25, y=0.25, w=0.5, h=0.5))
    with Image.open(BytesIO(cropped)) as image:
        assert image.size == (4, 4)
        assert image.getpixel((0, 0)) == (255, 0, 0)
        assert image.getpixel((3, 3)) == (255, 0, 0)
    assert image_path(key).read_bytes() == encoded.getvalue()
    assert len(list(image_path(key).parent.iterdir())) == 1


def test_crop_clips_edges_and_handles_jpeg():
    encoded = BytesIO()
    Image.new('RGB', (8, 8), 'white').save(encoded, 'JPEG')
    key = store_image(encoded.getvalue(), 'JPEG')
    with Image.open(BytesIO(crop_symbol(key, Box(x=-0.25, y=0.75, w=0.75, h=1)))) as image:
        assert image.format == 'PNG'
        assert image.size == (4, 2)


@pytest.mark.parametrize('box', [
    {'x': 2, 'y': 0, 'w': 1, 'h': 1}, {'x': 0, 'y': 0, 'w': 0, 'h': 1},
    {'x': float('nan'), 'y': 0, 'w': 1, 'h': 1},
])
def test_invalid_crops_never_return_the_whole_tablet(box):
    key = store_image(png(), 'PNG')
    with pytest.raises(ValueError):
        crop_symbol(key, Box(**box))


def test_symbol_name_uses_prediction_or_occurrence_id():
    snapshot = result().model_dump()
    sign = find_symbol(snapshot, 1)
    assert sign.crop is None
    assert symbol_name(sign) == 'ku'
    sign.sign = None
    sign.id = 0
    assert symbol_name(sign) == 'symbol-0'
    assert find_symbol(snapshot, 999) is None


def test_symbol_creation_and_duplicate_title_response(client, monkeypatch):
    create = MagicMock(return_value=(summary().model_copy(update={'sign_id': 0}), True))
    monkeypatch.setattr(CommunityDataController, 'create_discussion', create)
    payload = {'analysis_id': 12, 'sign_id': 0, 'title': '  My interpretation  '}
    assert client.post('/community/discussions', json=payload).status_code == 201
    create.assert_called_once_with(7, 12, 'My interpretation', 0)
    create.side_effect = DuplicateDiscussionTitle('Choose another title.')
    response = client.post('/community/discussions', json=payload)
    assert response.status_code == 409
    assert response.json()['detail'] == 'Choose another title.'
    create.side_effect = None
    create.return_value = None
    assert client.post('/community/discussions', json=payload).status_code == 404
    client.headers.pop('X-CSRF-Token')
    assert client.post('/community/discussions', json=payload).status_code == 403
    client.cookies.clear()
    assert client.post('/community/discussions', json=payload).status_code == 401


@pytest.mark.parametrize('sign_id', [-1, 2**63, 'not-a-sign'])
def test_invalid_symbol_ids_are_rejected(client, sign_id):
    assert client.post('/community/discussions', json={
        'analysis_id': 12, 'sign_id': sign_id, 'title': 'Symbol',
    }).status_code == 422


def test_owner_and_occurrence_are_checked_before_sharing(monkeypatch):
    controller = CommunityDataController()
    _, cursor = connection_with_rows(monkeypatch, [None])
    assert controller.create_discussion(7, 12, 'Symbol', 1) is None
    assert cursor.execute.call_args.args[1] == (12, 7)
    assert 'user_id = %s FOR UPDATE' in cursor.execute.call_args.args[0]
    _, cursor = connection_with_rows(monkeypatch, [saved_row()])
    assert controller.create_discussion(7, 12, 'Symbol', 999) is None
    assert cursor.execute.call_count == 1


def test_title_unique_constraint_is_reported_and_transaction_rolled_back(monkeypatch):
    key = store_image(png(), 'PNG')
    connection, cursor = connection_with_rows(monkeypatch, [saved_row(), None, {'storage_key': key}])
    cursor.execute.side_effect = [None, None, None, IntegrityError(
        "Duplicate entry for key 'community_discussion.uq_discussion_title'", errno=1062,
    )]
    with pytest.raises(DuplicateDiscussionTitle):
        CommunityDataController().create_discussion(7, 12, 'ku', 1)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_repeated_share_returns_same_occurrence_even_with_another_title(monkeypatch):
    _, cursor = connection_with_rows(monkeypatch, [saved_row(), saved_row()])
    discussion, created = CommunityDataController().create_discussion(7, 12, 'Another title', 1)
    assert not created and discussion.id == 3
    assert discussion.title == 'Custom title'
    assert cursor.execute.call_count == 2


def test_symbol_detail_has_ancestry_without_publishing_full_analysis(client, monkeypatch):
    _, cursor = connection_with_rows(monkeypatch, [saved_row()])
    cursor.fetchall.return_value = [saved_row(4, None), saved_row()]
    client.cookies.clear()
    response = client.get('/community/discussions/3')
    assert response.status_code == 200
    detail = response.json()
    assert detail['symbol']['id'] == 1
    assert detail['symbol_name'] == 'ku'
    assert detail['tablet_filename'] == 'HT13.png'
    assert detail['parent_discussion']['id'] == 4
    assert [item['id'] for item in detail['symbol_discussions']] == [3]
    assert 'result' not in detail
    assert 'crop' not in detail['symbol']
    assert 'PRIVATE_PIXELS' not in response.text


def test_tablet_lists_symbol_threads_and_standalone_symbol_has_no_parent(monkeypatch):
    _, cursor = connection_with_rows(monkeypatch, [saved_row(4, None)])
    cursor.fetchall.return_value = [saved_row(), saved_row(4, None)]
    detail = CommunityDataController().get_discussion(4)
    assert detail.result is not None and detail.symbol is None
    assert [item.id for item in detail.symbol_discussions] == [3]
    _, cursor = connection_with_rows(monkeypatch, [saved_row()])
    cursor.fetchall.return_value = [saved_row()]
    assert CommunityDataController().get_discussion(3).parent_discussion is None


def test_public_image_uses_saved_box_and_missing_files_return_404(client, monkeypatch):
    key = store_image(png(), 'PNG')
    _, cursor = connection_with_rows(monkeypatch, [])
    cursor.fetchone.side_effect = None
    cursor.fetchone.return_value = {**saved_row(), 'storage_key': key, 'format': 'PNG'}
    client.cookies.clear()
    response = client.get('/community/discussions/3/image')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/png'
    with Image.open(BytesIO(response.content)) as image:
        assert image.size == (4, 4)
    image_path(key).unlink()
    assert client.get('/community/discussions/3/image').status_code == 404


def test_history_discussion_link_only_targets_the_whole_tablet(monkeypatch):
    metadata = dict(id=12, filename='HT13.png', format='PNG', size_bytes=80,
                    result_schema_version=1, created_at=datetime(2026, 11, 24),
                    result_json=saved_row()['result_json'])
    _, cursor = connection_with_rows(monkeypatch, [metadata, {'storage_key': 'saved.png', 'discussion_id': 4}])
    assert AnalysisDataController().get_analysis(7, 12).discussion_id == 4
    assert 'd.sign_id IS NULL' in cursor.execute.call_args.args[0]
