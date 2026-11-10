from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from mysql.connector import Error as DatabaseError

from backend.app.auth import COOKIE_NAME, csrf_token, token_hash
from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.data_controller.community_data_controller import CommunityDataController
from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.image_storage import image_path, store_image
from backend.app.main import app
from backend.app.model.community import DiscussionSummary, DiscussionDetail
from backend.app.model.user import UserPublic
from backend.tests.test_history import png, result


def summary():
    return DiscussionSummary(id=3, analysis_id=12, author_id=7, author_username="owner",
                             title="Tablet reading", created_at=datetime.now(timezone.utc))


@pytest.fixture
def client(monkeypatch):
    token = "a" * 43
    monkeypatch.setattr(UserDataController, "get_session_user", lambda self, digest:
                        UserPublic(id=7, email="owner@ase3.com", username="owner")
                        if digest == token_hash(token) else None)
    with TestClient(app) as client:
        client.cookies.set(COOKIE_NAME, token)
        client.headers["X-CSRF-Token"] = csrf_token(token)
        yield client


def test_anonymous_visitors_can_read_but_cannot_publish(monkeypatch):
    monkeypatch.setattr(CommunityDataController, "list_discussions", lambda *a: [summary()])
    monkeypatch.setattr(CommunityDataController, "get_discussion", lambda *a:
                        DiscussionDetail(**summary().model_dump(), result=result(), image_url="/api/community/discussions/3/image"))
    monkeypatch.setattr(CommunityDataController, "list_comments", lambda *a: [])
    with TestClient(app) as client:
        assert client.get('/community/discussions').json()['items'][0]['id'] == 3
        assert client.get('/community/discussions/3').json()['result']['summary'] == 'One sign'
        assert client.get('/community/discussions/3/comments').json() == []
        assert client.post('/community/discussions', json={'analysis_id': 12, 'title': 'Tablet'}).status_code == 401
        assert client.post('/community/discussions/3/comments', json={'body': 'Hello'}).status_code == 401


def test_writes_require_csrf(client):
    client.headers.pop('X-CSRF-Token')
    assert client.post('/community/discussions', json={'analysis_id': 12, 'title': 'Tablet'}).status_code == 403
    assert client.post('/community/discussions/3/comments', json={'body': 'Hello'}).status_code == 403


def test_share_checks_owner_and_handles_duplicate_and_missing_image(client, monkeypatch):
    create = MagicMock(return_value=None)
    monkeypatch.setattr(CommunityDataController, 'create_discussion', create)
    payload = {'analysis_id': 12, 'title': ' Tablet ', 'author_id': 999}
    assert client.post('/community/discussions', json=payload).status_code == 404
    create.assert_called_once_with(7, 12, 'Tablet')
    create.side_effect = FileNotFoundError('Upload the tablet again.')
    assert client.post('/community/discussions', json=payload).status_code == 409
    create.side_effect = None
    create.return_value = (summary(), True)
    assert client.post('/community/discussions', json=payload).status_code == 201
    create.return_value = (summary(), False)
    response = client.post('/community/discussions', json=payload)
    assert response.status_code == 200 and response.json()['id'] == 3


@pytest.mark.parametrize('body', ['', '   ', 'x' * 2001])
def test_comment_validation(client, body):
    assert client.post('/community/discussions/3/comments', json={'body': body}).status_code == 422


@pytest.mark.parametrize('title', ['', '  ', 'x' * 161])
def test_title_validation(client, title):
    assert client.post('/community/discussions', json={'analysis_id': 12, 'title': title}).status_code == 422


def test_images_are_served_only_through_authorized_lookups(client, monkeypatch):
    key = store_image(png(), 'PNG')
    private = MagicMock(return_value=None)
    public = MagicMock(return_value=None)
    monkeypatch.setattr(AnalysisDataController, 'get_image', private)
    monkeypatch.setattr(CommunityDataController, 'get_image', public)
    assert client.get('/analysis/12/image').status_code == 404
    private.assert_called_once_with(7, 12)
    assert client.get('/community/discussions/12/image').status_code == 404
    public.return_value = (key, 'PNG')
    client.cookies.clear()
    response = client.get('/community/discussions/3/image')
    assert response.status_code == 200 and response.content == png()
    assert response.headers['content-type'] == 'image/png'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert client.get('/analysis/12/image').status_code == 401
    image_path(key).unlink()
    assert client.get('/community/discussions/3/image').status_code == 404


@pytest.mark.parametrize('key', ['../secret.png', '/tmp/secret.png', 'abcd.svg'])
def test_storage_rejects_paths(key):
    with pytest.raises(ValueError):
        image_path(key)


@pytest.mark.parametrize('failure', ['execute', 'commit'])
def test_failed_save_rolls_back_and_removes_the_image(monkeypatch, tmp_path, failure):
    connection = MagicMock()
    connection.cursor.return_value.lastrowid = 12
    target = connection.cursor.return_value.execute if failure == 'execute' else connection.commit
    target.side_effect = DatabaseError('storage failure')
    monkeypatch.setattr('mysql.connector.connect', lambda **kw: connection)
    with pytest.raises(DatabaseError):
        AnalysisDataController().save_analysis(7, 'tablet.png', 'PNG', len(png()), result(), image_bytes=png())
    connection.rollback.assert_called_once()
    assert list((tmp_path / 'tablets').iterdir()) == []


def test_upload_reports_disk_failure_without_saving(client, monkeypatch):
    monkeypatch.setattr(AnalysisDataController, 'analyze', lambda *a, **kw: result())
    monkeypatch.setattr('backend.app.data_controller.analysis_data_controller.store_image', MagicMock(side_effect=OSError('disk full')))
    connect = MagicMock()
    monkeypatch.setattr('mysql.connector.connect', connect)
    assert client.post('/analysis', files={'file': ('a.png', png(), 'image/png')}).status_code == 503
    connect.assert_not_called()
