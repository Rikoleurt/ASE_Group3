"""Scholars' workbench, story G: searching the corpus by sign sequence."""

import pytest
from fastapi.testclient import TestClient

from backend.app import corpus_search
from backend.app.main import app
from backend.app.routes import search_routes

DOC = {
    # Line 1: ka-ro | ku-ro ; line 2: ku ro (two words across a divider), then VIN.
    "lines": [
        [
            {"kind": "sign", "id": "AB77", "reading": "ka"},
            {"kind": "sign", "id": "AB02", "reading": "ro"},
            {"kind": "divider"},
            {"kind": "sign", "id": "AB81", "reading": "ku"},
            {"kind": "sign", "id": "AB02", "reading": "ro"},
        ],
        [
            {"kind": "sign", "id": "AB81", "reading": "ku"},
            {"kind": "divider"},
            {"kind": "sign", "id": "AB02", "reading": "ro"},
            {"kind": "number", "value": 5},
            {"kind": "sign", "id": "AB131a", "reading": "VIN"},
        ],
    ],
    # The positions list has an unidentified sign (3) the lines leave out, and no VIN.
    "signs": [
        {"position": 1, "sign": "AB77"},
        {"position": 2, "sign": "AB02"},
        {"position": 3, "sign": ""},
        {"position": 4, "sign": "AB81"},
        {"position": 5, "sign": "AB02"},
        {"position": 6, "sign": "AB81"},
        {"position": 7, "sign": "AB02"},
    ],
}


@pytest.fixture
def lines():
    return corpus_search.lines_of("HT-9", "HT 9", DOC)


def test_line_signs_are_matched_to_the_scholars_positions(lines):
    assert [[(s.sign, s.position) for s in line.signs] for line in lines] == [
        [("AB77", 1), ("AB02", 2), ("AB81", 4), ("AB02", 5)],  # position 3 (unidentified) skipped
        [("AB81", 6), ("AB02", 7), ("AB131a", None)],  # no position for VIN: still searchable
    ]
    words = [[s.word for s in line.signs] for line in lines]
    assert words[0][0] == words[0][1] != words[0][2] == words[0][3]  # a divider ends a word
    assert len(set(words[1])) == 3


def test_queries_are_parsed_as_ids_readings_wildcards_and_alternatives():
    assert corpus_search.parse("KU-ro") == [{"ku"}, {"ro"}]
    assert corpus_search.parse("ab1 *") == [{"ab1", "ab01"}, None]
    assert corpus_search.parse("ku|ka-ro") == [{"ku", "ka"}, {"ro"}]
    for bad in ("", "  ", "ku-r$o", "-".join(["ka"] * 13)):
        with pytest.raises(corpus_search.BadQuery):
            corpus_search.parse(bad)


def test_matches_stay_in_one_word_unless_asked(lines):
    find = lambda q, across=False: [  # noqa: E731
        (line.number, [s.position for s in run])
        for line, run in corpus_search.search(lines, corpus_search.parse(q), across)
    ]
    assert find("ku-ro") == [(0, [4, 5])]  # line 2's ku and ro are separate words
    assert find("ku-ro", across=True) == [(0, [4, 5]), (1, [6, 7])]
    assert find("AB81-AB02") == find("ku-ro")
    assert find("*-ro") == [(0, [1, 2]), (0, [4, 5])]
    assert find("ka|ku-ro") == [(0, [1, 2]), (0, [4, 5])]
    assert find("VIN") == [(1, [None])]
    assert find("ro-ku") == [] and find("ro-ku", across=True) == [(0, [2, 4])]


def test_the_route_groups_hits_by_tablet(monkeypatch, lines):
    other = corpus_search.lines_of(
        "HT-1",
        "HT 1",
        {
            "lines": [
                [
                    {"kind": "sign", "id": "AB81", "reading": "ku"},
                    {"kind": "sign", "id": "AB02", "reading": "ro"},
                ]
            ]
        },
    )
    monkeypatch.setattr(corpus_search, "corpus_lines", lambda: other + lines)
    with TestClient(app) as client:
        body = client.get("/corpus/search", params={"q": "ku-ro", "across_words": True}).json()
        assert (body["total_tablets"], body["total_hits"], body["source"]) == (2, 3, "scholar")
        assert [
            (item["tablet"], [hit["positions"] for hit in item["hits"]]) for item in body["items"]
        ] == [("HT 1", [[None, None]]), ("HT 9", [[4, 5], [6, 7]])]
        assert body["items"][1]["hits"][0] == {"line": 0, "positions": [4, 5], "text": "ku-ro"}
        paged = client.get(
            "/corpus/search", params={"q": "ku-ro", "across_words": True, "offset": 1}
        ).json()
        assert [item["tablet"] for item in paged["items"]] == ["HT 9"] and paged[
            "total_tablets"
        ] == 2
        assert client.get("/corpus/search", params={"q": "ku-r$o"}).status_code == 422


def test_the_accepted_editions_can_be_searched(monkeypatch, lines):
    monkeypatch.setattr(search_routes, "_edition_lines", lambda editions: (lines, {"HT-9": 12}))
    with TestClient(app) as client:
        body = client.get("/corpus/search", params={"q": "ku-ro", "source": "edition"}).json()
    assert body["source"] == "edition" and body["items"][0]["release_id"] == 12


def test_edition_lines_take_words_from_the_transliteration():
    from types import SimpleNamespace as NS

    signs = {
        1: NS(sign="AB81", reading="ku"),
        2: NS(sign="AB02", reading="ro"),
        3: NS(sign="AB131a", reading="VIN"),
    }
    reading = [NS(index=0, text="ku-ro VIN", sign_ids=[1, 2, 3])]
    (line,) = corpus_search.edition_lines("HT-9", "HT 9", reading, signs)
    assert [(s.position, s.word) for s in line.signs] == [(1, 0), (2, 0), (3, 1)]
