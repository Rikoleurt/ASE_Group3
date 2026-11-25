"""Scholars' workbench, story H: citing and exporting an edition release."""

import csv
import io
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import glyph_index
from backend.app.main import app
from backend.tests.test_corpus_tablets import corpus_index, fake, tracing  # noqa: F401  (fixtures)
from backend.tests.test_editions import an_edition, editions, person, release  # noqa: F401

TEI = "{http://www.tei-c.org/ns/1.0}"


@pytest.fixture
def released(monkeypatch, corpus_index, fake, editions, tracing):
    """A release of an edition of HT-1 whose one box (AB77, ka) is marked uncertain and restored."""
    monkeypatch.setattr(
        glyph_index, "tracing_path", lambda slug: tracing if slug == "HT-1" else None
    )
    set_id = an_edition(fake)
    fake.boxes[max(fake.boxes)]["marks"] = {
        "certainty": "uncertain",
        "damage": "restored",
        "word_end": True,
    }
    with person(monkeypatch, 7) as owner:
        return release(owner, set_id, notes="First agreed reading").json()


def get(path):
    with TestClient(app) as client:
        return client.get(path)


def test_a_release_says_how_to_cite_it(released):
    body = get(f"/editions/{released['id']}").json()
    citation = body["citation"]
    assert citation.startswith(
        "anouk, dev. Agreed: an edition of HT 1, release 1. ASE Group 3 Linear A workbench, "
    )
    assert f"/editions/{released['id']}." in citation and "CC BY-NC-SA 4.0" in citation


def test_json_and_csv_list_each_box_with_its_marks_and_source(released):
    response = get(f"/editions/{released['id']}/export.json")
    assert response.headers["content-type"] == "application/json"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="HT-1-edition-1-release-1.json"'
    )
    document = response.json()
    assert (document["title"], document["release"], document["contributors"]) == (
        "Agreed",
        1,
        ["anouk", "dev"],
    )
    (box,) = document["boxes"]
    assert (
        box["sign"],
        box["reading"],
        box["certainty"],
        box["damage"],
        box["source"],
        box["source_author"],
    ) == ("AB77", "ka", "uncertain", "restored", "copy", "anouk")
    assert (box["x"], box["y"], box["w"], box["h"]) == (
        100,
        50,
        100,
        100,
    )  # pixels of a 1000 x 500 tracing
    assert "CC BY-NC-SA 4.0" in document["licence"]

    text = get(f"/editions/{released['id']}/export.csv").content.decode("utf-8-sig")
    comment, rest = text.split("\n", 1)
    assert comment.startswith("# anouk, dev. Agreed")
    (row,) = list(csv.DictReader(io.StringIO(rest)))
    assert (row["sign"], row["certainty"], row["line"], row["order"]) == (
        "AB77",
        "uncertain",
        "1",
        "1",
    )


def test_svg_and_png_draw_the_boxes_over_the_drawing(released):
    response = get(f"/editions/{released['id']}/export.svg")
    assert response.headers["content-type"].startswith("image/svg+xml")
    svg = ET.fromstring(response.content)
    ns = "{http://www.w3.org/2000/svg}"
    assert svg.find(f"{ns}image").get("href").startswith("data:image/png;base64,")  # self-contained
    assert svg.find(f"{ns}desc").text.startswith("anouk, dev. Agreed")
    rect = svg.find(f"{ns}g/{ns}rect")
    assert (rect.get("x"), rect.get("width"), rect.get("stroke")) == (
        "100",
        "100",
        "#DC2626",
    )  # marked: red
    assert svg.find(f"{ns}g/{ns}text").text == "ka"

    png = get(f"/editions/{released['id']}/export.png")
    image = Image.open(io.BytesIO(png.content))
    assert image.width == 1000 and image.height > 500  # the tablet, then a credit line


def test_tei_follows_the_minimal_epidoc_profile(released):
    response = get(f"/editions/{released['id']}/export.xml")
    assert response.headers["content-type"] == "application/tei+xml"
    root = ET.fromstring(response.content)
    assert root.tag == f"{TEI}TEI"
    assert root.find(f".//{TEI}titleStmt/{TEI}title").text == "Agreed, release 1"
    assert [name.text for name in root.iter(f"{TEI}name")] == ["anouk", "dev"]
    assert root.find(f".//{TEI}idno[@type='URI']").text.endswith(f"/editions/{released['id']}")
    assert "CC BY-NC-SA 4.0" in root.find(f".//{TEI}licence").text
    (zone,) = root.iter(f"{TEI}zone")
    assert (
        zone.get("ulx"),
        zone.get("lry"),
        zone.get("{http://www.w3.org/XML/1998/namespace}id") or zone.get("xml:id"),
    ) == ("100", "150", f"z{released['boxes'][0]['id']}")
    # Restored and uncertain: <supplied reason="lost"><unclear><g ref="#AB77">ka</g></unclear></supplied>
    supplied = root.find(f".//{TEI}w/{TEI}supplied")
    assert supplied.get("reason") == "lost"
    glyph = supplied.find(f"{TEI}unclear/{TEI}g")
    assert (glyph.get("ref"), glyph.text, glyph.get("facs")) == (
        "#AB77",
        "ka",
        f"#z{released['boxes'][0]['id']}",
    )
    assert root.find(f".//{TEI}lb").get("n") == "1"


def test_exports_follow_the_release_visibility(released, fake):
    fake.sets[released["edition_id"]]["everyone"] = "none"  # made private again
    assert get(f"/editions/{released['id']}/export.json").status_code == 404
    assert get("/editions/999/export.csv").status_code == 404
    assert get(f"/editions/{released['id']}/export.docx").status_code in (404, 422)
