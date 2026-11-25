"""Regression coverage for combining discussion mentions and votes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.app.data_controller.community_data_controller import CommunityDataController
from backend.app.data_controller.mention_data_controller import MentionDataController
from backend.app.mentions import InvalidMention
from backend.app.model.community import DiscussionComment, DiscussionPage, VoteState
from backend.app.model.mention import MentionPage, ResolvedMention
from backend.tests.test_community import client


def mention():
    return ResolvedMention(key="user:7", kind="user", label="owner", user_id=7,
                           token="@[owner](user:7)")


def test_votes_mentions_and_author_links_coexist(client, monkeypatch):
    target = mention()
    monkeypatch.setattr(MentionDataController, "search_mentions",
                        lambda *args: MentionPage(items=[target]))
    monkeypatch.setattr(CommunityDataController, "get_vote",
                        lambda *args: VoteState(score=2, my_vote=0))
    vote = MagicMock(return_value=VoteState(score=3, my_vote=1))
    monkeypatch.setattr(CommunityDataController, "set_vote", vote)
    post = MagicMock(return_value=DiscussionComment(
        id=9, discussion_id=3, author_id=7, author_username="owner",
        created_at=datetime.now(timezone.utc), body=target.token, mentions=[target]))
    monkeypatch.setattr(CommunityDataController, "add_comment", post)
    search = MagicMock(return_value=DiscussionPage(items=[]))
    monkeypatch.setattr(CommunityDataController, "get_discussion_by_author", search)

    suggestions = client.get('/community/discussions/3/mentions?type=user')
    assert suggestions.status_code == 200
    assert suggestions.json()['items'][0]['key'] == 'user:7'
    assert client.get('/community/discussions/3/vote').json() == {'score': 2, 'my_vote': 0}
    response = client.put('/community/discussions/3/vote', json={'value': 1})
    assert response.status_code == 200
    assert response.json() == {'score': 3, 'my_vote': 1}
    vote.assert_called_once_with(3, 7, 1)
    response = client.post('/community/discussions/3/comments', json={'body': target.token})
    assert response.status_code == 201
    assert response.json()['mentions'][0]['token'] == target.token
    post.assert_called_once_with(3, 7, target.token)
    assert client.get('/community/discussions?filter_by=author&author_id=7').status_code == 200
    search.assert_called_once_with('', 30, None, 7)


def test_vote_writes_and_mentions_keep_authentication_and_validation(client, monkeypatch):
    vote = MagicMock(return_value=None)
    monkeypatch.setattr(CommunityDataController, 'set_vote', vote)
    assert client.put('/community/discussions/3/vote', json={'value': 2}).status_code == 422
    vote.assert_not_called()
    assert client.put('/community/discussions/3/vote', json={'value': 1}).status_code == 404
    monkeypatch.setattr(CommunityDataController, 'add_comment',
                        MagicMock(side_effect=InvalidMention('Invalid mention.')))
    assert client.post('/community/discussions/3/comments', json={'body': '@[owner](user:7)'}).status_code == 422
    client.headers.pop('X-CSRF-Token')
    assert client.put('/community/discussions/3/vote', json={'value': 1}).status_code == 403
    client.cookies.clear()
    assert client.get('/community/discussions/3/vote').status_code == 401
    assert client.get('/community/discussions/3/mentions?type=user').status_code == 401


@pytest.mark.parametrize('operation', ['read', 'write'])
def test_comment_storage_keeps_resolved_mentions(monkeypatch, operation):
    target = mention()
    created_at = datetime(2026, 11, 25)
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.lastrowid = 9
    cursor.fetchone.side_effect = [{'id': 3}, {'username': 'owner'}]
    cursor.fetchall.return_value = [dict(id=9, discussion_id=3, author_id=7,
                                        author_username='owner', created_at=created_at, body=target.token)]
    monkeypatch.setattr('mysql.connector.connect', lambda **kwargs: connection)
    resolve = MagicMock(return_value=[[target]])
    validate = MagicMock(return_value=[target])
    monkeypatch.setattr('backend.app.data_controller.community_data_controller.resolve_mentions', resolve)
    monkeypatch.setattr('backend.app.data_controller.community_data_controller.validate_mentions', validate)
    controller = CommunityDataController()
    if operation == 'read':
        result = controller.list_comments(3)[0]
        resolve.assert_called_once_with(cursor, [target.token])
    else:
        result = controller.add_comment(3, 7, target.token)
        validate.assert_called_once_with(cursor, target.token)
    assert result.mentions == [target]
