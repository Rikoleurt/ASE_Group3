"""Scholars' workbench, story L: mentioning corpus glyphs and editions, and the discussions that do."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app import glyph_index, mentions
from backend.app.data_controller.edition_data_controller import EditionDataController
from backend.app.main import app
from backend.app.routes.link_routes import LinkDataController, get_link_data_controller
from backend.tests import glyph_fixtures
from backend.tests.test_box_sets import sql_controller


@pytest.fixture(autouse=True)
def corpus(monkeypatch):
    index = glyph_fixtures.index(with_embeddings=False)
    monkeypatch.setattr(glyph_index, "get_index", lambda: index)
    releases = {
        7: {
            "id": 7,
            "number": 2,
            "title": None,
            "owner": "anouk",
            "tablet_slug": "HT-1",
            "everyone": "view",
        },
        8: {
            "id": 8,
            "number": 1,
            "title": "Private",
            "owner": "dev",
            "tablet_slug": "HT-1",
            "everyone": "none",
        },
    }
    monkeypatch.setattr(
        EditionDataController, "release", lambda self, release_id: releases.get(release_id)
    )


def test_glyph_and_edition_tokens_are_parsed():
    refs = mentions.parse_mentions(
        "see @[x](glyph:HT-1:1), @[y](edition:7) and @[z](glyph:KN-Zb-5:3)"
    )
    assert [(r.kind, r.glyph_tablet, r.glyph_position, r.release_id) for r in refs] == [
        ("glyph", "HT-1", 1, None),
        ("edition", None, None, 7),
        ("glyph", "KN-Zb-5", 3, None),
    ]
    assert mentions.parse_mentions("@[x](glyph:HT-1)") == []  # a position is needed
    assert mentions.parse_mentions("@[x](edition:abc)") == []


def test_glyphs_and_open_editions_resolve_others_do_not():
    [resolved] = mentions.resolve_mentions(
        None, ["@[a](glyph:HT-1:1) @[b](glyph:HT-1:99) @[c](edition:7) @[d](edition:8)"]
    )
    glyph, missing, edition, private = resolved
    assert (glyph.kind, glyph.label, glyph.available) == ("glyph", "HT 1 · ka", True)
    assert glyph.image_url == "/api/tablets/HT-1/thumbnail.png?position=1"
    assert missing.available is False
    assert (edition.kind, edition.label, edition.release_id) == (
        "edition",
        "anouk's edition of HT 1, release 2",
        7,
    )
    assert private.available is False  # its edition is not open to everyone
    with pytest.raises(mentions.InvalidMention, match="glyph or edition is not available"):
        mentions.validate_mentions(None, "@[d](edition:8)")


class FakeLinks:
    def __init__(self):
        self.asked = []

    def linked(self, key, limit):
        self.asked.append((key, limit))
        return [
            {
                "id": 4,
                "title": "Is this ka?",
                "author": "anouk",
                "mentioned_at": datetime(2026, 11, 25, 9),
            }
        ]


def test_discussions_that_mention_a_target_are_listed():
    links = FakeLinks()
    app.dependency_overrides[get_link_data_controller] = lambda: links
    try:
        with TestClient(app) as client:
            body = client.get("/community/linked", params={"target": "glyph:HT-13:5"}).json()
            assert body["target"] == "glyph:HT-13:5"
            assert body["items"][0] == {
                "id": 4,
                "title": "Is this ka?",
                "author": "anouk",
                "mentioned_at": "2026-11-25T09:00:00Z",
            }
            for target in ("edition:7", "sign:AB81"):
                assert client.get("/community/linked", params={"target": target}).status_code == 200
            for target in ("user:7", "glyph:HT-13", "glyph:../x:1", "edition:0", "%"):
                assert (
                    client.get("/community/linked", params={"target": target}).status_code == 422
                ), target
    finally:
        app.dependency_overrides.pop(get_link_data_controller, None)
    assert links.asked[0] == ("glyph:HT-13:5", 20)


def test_sql_finds_the_mention_destination_literally(monkeypatch):
    _c, _connection, cursor = sql_controller(monkeypatch, [[]])
    LinkDataController().linked("glyph:HT-13:5", 20)
    sql, params = cursor.execute.call_args.args
    assert "c.body LIKE %s" in sql and params == ("%](glyph:HT-13:5)%", 20)
