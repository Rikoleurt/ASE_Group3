"""Filtered keyset pages, bounded parent context and cursor validation."""
import json
from base64 import urlsafe_b64encode
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.data_controller.community_data_controller import (
    CommunityDataController, decode_discussion_cursor, encode_discussion_cursor,
)
from backend.app.model.community import DiscussionPage
from backend.tests.test_community import summary
from backend.tests.test_symbol_discussions import saved_row


def database(monkeypatch, pages):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = pages
    monkeypatch.setattr('mysql.connector.connect', lambda **kwargs: connection)
    return cursor


def test_page_bounds_matches_and_includes_only_needed_parents(monkeypatch):
    child = saved_row(4, 0)
    snapshot = json.loads(child['result_json'])
    snapshot['signs'][0]['id'] = 0
    child['result_json'] = json.dumps(snapshot)
    cursor = database(monkeypatch, [[child, saved_row(3, None)], [saved_row(3, None)]])
    page = CommunityDataController().get_discussion_by_most_recent_date(limit=1)
    assert [item.id for item in page.items] == [4]
    assert [item.id for item in page.parents] == [3]
    position = decode_discussion_cursor(page.next_cursor, 'recent', '')
    assert position.id == 4
    sql, params = cursor.execute.call_args_list[0].args
    assert 'ORDER BY d.created_at DESC, d.id DESC LIMIT %s' in sql
    assert params == (2,)
    sql, params = cursor.execute.call_args_list[1].args
    assert 'd.sign_id IS NULL' in sql and 'IN (%s)' in sql
    assert params == (12,)


def test_parent_already_in_page_is_not_fetched_twice(monkeypatch):
    cursor = database(monkeypatch, [[saved_row(4, 1), saved_row(3, None)]])
    page = CommunityDataController().get_discussion_by_most_recent_date(limit=30)
    assert len(page.items) == 2 and not page.parents and page.next_cursor is None
    assert cursor.execute.call_count == 1


def test_empty_page_stops_pagination(monkeypatch):
    cursor = database(monkeypatch, [[]])
    assert CommunityDataController().get_discussion_by_most_recent_date().model_dump() == {
        'items': [], 'parents': [], 'next_cursor': None,
    }
    assert cursor.execute.call_count == 1


@pytest.mark.parametrize('method, expected_sql', [
    ('get_discussion_by_author', 'u.username LIKE %s'),
    ('get_discussion_by_tablet_name', 'p.sign_id IS NULL AND p.title LIKE %s'),
])
def test_search_is_parameterized_and_wildcards_are_literal(monkeypatch, method, expected_sql):
    cursor = database(monkeypatch, [[]])
    term = "  %_!' OR 1=1 --  "
    getattr(CommunityDataController(), method)(term)
    sql, params = cursor.execute.call_args.args
    assert expected_sql in sql
    assert term.strip() not in sql
    assert params[0] == "%!%!_!!' OR 1=1 --%"
    assert params[-1] == 31


def test_cursor_uses_timestamp_and_id_to_handle_ties(monkeypatch):
    item = summary().model_copy(update={'id': 7, 'created_at': datetime(2026, 11, 24, 12, 30, 0, 123456, tzinfo=timezone.utc)})
    token = encode_discussion_cursor(item, 'author', 'jason')
    cursor = database(monkeypatch, [[]])
    CommunityDataController().get_discussion_by_author(' jason ', 30, token)
    sql, params = cursor.execute.call_args.args
    assert 'd.created_at < %s OR (d.created_at = %s AND d.id < %s)' in sql
    assert params == ('%jason%', item.created_at.replace(tzinfo=None), item.created_at.replace(tzinfo=None), 7, 31)


@pytest.mark.parametrize('token', ['!', 'e30', 'null', 'x' * 4097])
def test_bad_cursors_fail_before_database_access(monkeypatch, token):
    connect = MagicMock()
    monkeypatch.setattr('mysql.connector.connect', connect)
    with pytest.raises(ValueError, match='cursor'):
        CommunityDataController().get_discussion_by_most_recent_date(cursor=token)
    connect.assert_not_called()


def test_cursor_cannot_be_reused_for_different_search():
    token = encode_discussion_cursor(summary(), 'tablet', 'HT13')
    for mode, query in [('author', 'HT13'), ('tablet', 'HT14'), ('recent', '')]:
        with pytest.raises(ValueError, match='cursor'):
            decode_discussion_cursor(token, mode, query)


@pytest.mark.parametrize('timestamp', ['0900-01-01T00:00:00Z', '2026-11-24T00:00:00'])
def test_cursor_rejects_out_of_range_or_naive_dates(timestamp):
    token = urlsafe_b64encode(json.dumps({
        'created_at': timestamp, 'id': 1, 'filter_by': 'recent', 'q': '',
    }).encode()).decode()
    with pytest.raises(ValueError, match='cursor'):
        decode_discussion_cursor(token, 'recent', '')


def test_public_route_dispatches_search_and_defaults_to_thirty(monkeypatch):
    recent = MagicMock(return_value=DiscussionPage(items=[summary()]))
    author = MagicMock(return_value=DiscussionPage(items=[]))
    tablet = MagicMock(return_value=DiscussionPage(items=[]))
    monkeypatch.setattr(CommunityDataController, 'get_discussion_by_most_recent_date', recent)
    monkeypatch.setattr(CommunityDataController, 'get_discussion_by_author', author)
    monkeypatch.setattr(CommunityDataController, 'get_discussion_by_tablet_name', tablet)
    with TestClient(app) as client:
        assert client.get('/community/discussions').status_code == 200
        recent.assert_called_once_with(30, None)
        assert client.get('/community/discussions', params={'filter_by': 'author', 'q': 'jason'}).status_code == 200
        author.assert_called_once_with('jason', 30, None)
        assert client.get('/community/discussions', params={'filter_by': 'tablet', 'q': 'HT13'}).status_code == 200
        tablet.assert_called_once_with('HT13', 30, None)
        author.side_effect = ValueError('Invalid discussion cursor.')
        assert client.get('/community/discussions?filter_by=author&cursor=bad').status_code == 422


@pytest.mark.parametrize('params', [
    {'limit': 0}, {'limit': 101}, {'filter_by': 'invalid'}, {'q': 'x' * 256},
    {'cursor': ''}, {'cursor': 'x' * 4097}, {'q': 'jason', 'filter_by': 'recent'},
])
def test_route_validates_search_parameters(params):
    with TestClient(app) as client:
        assert client.get('/community/discussions', params=params).status_code == 422
