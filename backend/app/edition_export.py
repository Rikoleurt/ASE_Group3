"""Citing and exporting an edition release (scholars' workbench, story H).

A release never changes, so its page (/editions/<id>) is the permalink to cite, and every
export of it is the same tomorrow. Exports: SVG (the drawing embedded, boxes and signs on top),
PNG, CSV and JSON (one row per box, with its marks and source) and TEI-EpiDoc XML in a minimal
profile. Each carries the corpus licence (CC BY-NC-SA 4.0): the drawings and transcriptions are
SigLA's via lineara.eu.
"""

import base64
import csv
import io
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.app.model.edition import Release
from backend.app.reading import CREDIT

PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip(
    "/"
)  # e.g. https://linear-a.example.org; empty: relative links
LICENCE = (
    f"Drawings and transcriptions: SigLA (Salgarella & Castellan) via lineara.eu (M. Navarre), "
    f"{CREDIT['licence']} ({CREDIT['url']}). This edition is shared under the same licence."
)
TEI = "http://www.tei-c.org/ns/1.0"


def permalink(release: Release) -> str:
    return f"{PUBLIC_URL}/editions/{release.id}"


def tablet_name(release: Release) -> str:
    return release.tablet.replace("-", " ")


def title(release: Release) -> str:
    return release.title or f"{release.owner}'s edition of {tablet_name(release)}"


def citation(release: Release) -> str:
    """How to cite the release, e.g. "anouk, dev. Agreed reading: an edition of HT 13, release 2. ..."."""
    people = ", ".join(release.contributors or [release.owner])
    date = release.created_at.strftime("%d %B %Y").lstrip("0")
    return (
        f"{people}. {title(release)}: an edition of {tablet_name(release)}, release {release.number}. "
        f"ASE Group 3 Linear A workbench, {date}. {permalink(release)}. {LICENCE}"
    )


def _boxes(release: Release) -> list[dict]:
    """Each box with its place in the reading (line and order), pixel box, sign and marks."""
    order = {sign.id: sign for sign in release.reading.signs} if release.reading else {}
    rows = []
    for box in release.boxes:
        read = order.get(box.id)
        x, y = round(box.box.x * release.width), round(box.box.y * release.height)
        rows.append(
            {
                "box_id": box.id,
                "line": read.line if read else None,
                "order": read.order if read else None,
                "sign": box.sign,
                "reading": read.reading if read else None,
                "label": read.label if read else box.sign,
                "x": x,
                "y": y,
                "w": round(box.box.w * release.width),
                "h": round(box.box.h * release.height),
                "certainty": box.marks.certainty,
                "damage": box.marks.damage,
                "alternatives": list(box.marks.alternatives),
                "word_end": box.marks.word_end,
                "source": box.source.kind if box.source else "drawn",
                "source_author": box.source.author if box.source else None,
            }
        )
    return sorted(
        rows,
        key=lambda row: (row["line"] is None, row["line"] or 0, row["order"] or 0, row["box_id"]),
    )


def to_json(release: Release) -> bytes:
    document = {
        "title": title(release),
        "tablet": release.tablet,
        "release": release.number,
        "edition_id": release.edition_id,
        "permalink": permalink(release),
        "created_at": release.created_at.isoformat(),
        "owner": release.owner,
        "contributors": release.contributors,
        "merged_from": [item.model_dump() for item in release.merged_from],
        "notes": release.notes,
        "width": release.width,
        "height": release.height,
        "transliteration": release.reading.symbol_interpretation if release.reading else None,
        "boxes": _boxes(release),
        "citation": citation(release),
        "licence": LICENCE,
    }
    return json.dumps(document, ensure_ascii=False, indent=2).encode()


def to_csv(release: Release) -> bytes:
    out = io.StringIO()
    out.write(f"# {citation(release)}\n")
    fields = [
        "box_id",
        "line",
        "order",
        "sign",
        "reading",
        "x",
        "y",
        "w",
        "h",
        "certainty",
        "damage",
        "alternatives",
        "word_end",
        "source",
        "source_author",
    ]
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in _boxes(release):
        writer.writerow(
            {
                **row,
                "alternatives": " ".join(row["alternatives"]),
                "line": "" if row["line"] is None else row["line"] + 1,
                "order": "" if row["order"] is None else row["order"] + 1,
            }
        )
    return out.getvalue().encode(
        "utf-8-sig"
    )  # with a BOM, so spreadsheets read the Linear A names right


def _tracing(path: Path) -> Image.Image:
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
    flat = Image.new("RGBA", rgba.size, "white")
    flat.alpha_composite(rgba)  # SigLA strokes live in the alpha channel
    return flat.convert("RGB")


def to_png(release: Release, path: Path) -> bytes:
    image = (
        _tracing(path).resize((release.width, release.height))
        if path
        else Image.new("RGB", (release.width, release.height), "white")
    )
    draw = ImageDraw.Draw(image)
    line = max(2, round(release.width / 400))
    try:
        font = ImageFont.load_default(size=max(12, round(release.width / 60)))
    except TypeError:  # an older Pillow
        font = ImageFont.load_default()
    for row in _boxes(release):
        colour = (
            (220, 38, 38)
            if row["certainty"] != "certain" or row["damage"] != "none"
            else (0, 114, 178)
        )
        draw.rectangle(
            [row["x"], row["y"], row["x"] + row["w"], row["y"] + row["h"]],
            outline=colour,
            width=line,
        )
        draw.text(
            (row["x"] + line, row["y"] + line),
            row["reading"] or row["sign"] or "?",
            fill=colour,
            font=font,
        )
    footer = Image.new("RGB", (image.width, max(28, round(release.width / 30))), "white")
    ImageDraw.Draw(footer).text(
        (8, 6),
        f"{title(release)}, release {release.number}. {CREDIT['licence']}: SigLA via lineara.eu.",
        fill=(60, 40, 20),
        font=font,
    )
    sheet = Image.new("RGB", (image.width, image.height + footer.height), "white")
    sheet.paste(image, (0, 0))
    sheet.paste(footer, (0, image.height))
    out = io.BytesIO()
    sheet.save(out, "PNG", optimize=True)
    return out.getvalue()


def to_svg(release: Release, path: Path | None) -> bytes:
    """A self-contained SVG: the drawing embedded as PNG, a box and a label per sign."""
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    svg = ET.Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width=str(release.width),
        height=str(release.height),
        viewBox=f"0 0 {release.width} {release.height}",
    )
    ET.SubElement(svg, "title").text = f"{title(release)}, release {release.number}"
    ET.SubElement(svg, "desc").text = citation(release)
    if path is not None:
        data = io.BytesIO()
        _tracing(path).save(data, "PNG", optimize=True)
        ET.SubElement(
            svg,
            "image",
            href=f"data:image/png;base64,{base64.b64encode(data.getvalue()).decode()}",
            x="0",
            y="0",
            width=str(release.width),
            height=str(release.height),
        )
    size = str(max(12, round(release.width / 60)))
    for row in _boxes(release):
        colour = (
            "#DC2626" if row["certainty"] != "certain" or row["damage"] != "none" else "#0072B2"
        )
        group = ET.SubElement(svg, "g", id=f"box-{row['box_id']}")
        ET.SubElement(
            group,
            "rect",
            x=str(row["x"]),
            y=str(row["y"]),
            width=str(row["w"]),
            height=str(row["h"]),
            fill="none",
            stroke=colour,
            **{"stroke-width": "3"},
        )
        label = ET.SubElement(
            group,
            "text",
            x=str(row["x"] + 3),
            y=str(row["y"] + int(size)),
            fill=colour,
            **{"font-size": size, "font-family": "sans-serif"},
        )
        label.text = row["reading"] or row["sign"] or "?"
    return ET.tostring(svg, encoding="utf-8", xml_declaration=True)


def _tei(tag: str) -> str:
    return f"{{{TEI}}}{tag}"


def to_tei(release: Release) -> bytes:
    """TEI-EpiDoc in a minimal profile: header (title, contributors, permalink, licence, tablet),
    facsimile (one zone per box) and the edition text (lb, w, g; unclear, supplied, gap)."""
    ET.register_namespace("", TEI)
    root = ET.Element(_tei("TEI"))
    header = ET.SubElement(ET.SubElement(root, _tei("teiHeader")), _tei("fileDesc"))
    titles = ET.SubElement(header, _tei("titleStmt"))
    ET.SubElement(titles, _tei("title")).text = f"{title(release)}, release {release.number}"
    for person in release.contributors or [release.owner]:
        resp = ET.SubElement(titles, _tei("respStmt"))
        ET.SubElement(resp, _tei("resp")).text = "edited by"
        ET.SubElement(resp, _tei("name")).text = person
    publication = ET.SubElement(header, _tei("publicationStmt"))
    ET.SubElement(publication, _tei("authority")).text = "ASE Group 3 Linear A workbench"
    ET.SubElement(publication, _tei("idno"), type="URI").text = permalink(release)
    ET.SubElement(publication, _tei("date"), when=release.created_at.date().isoformat())
    availability = ET.SubElement(publication, _tei("availability"))
    ET.SubElement(availability, _tei("licence"), target=CREDIT["url"]).text = LICENCE
    source = ET.SubElement(
        ET.SubElement(ET.SubElement(header, _tei("sourceDesc")), _tei("msDesc")),
        _tei("msIdentifier"),
    )
    ET.SubElement(source, _tei("idno")).text = tablet_name(release)

    surface = ET.SubElement(
        ET.SubElement(root, _tei("facsimile")),
        _tei("surface"),
        ulx="0",
        uly="0",
        lrx=str(release.width),
        lry=str(release.height),
    )
    ET.SubElement(surface, _tei("graphic"), url=f"{PUBLIC_URL}/api/tablets/{release.tablet}/image")
    boxes = {row["box_id"]: row for row in _boxes(release)}
    for row in boxes.values():
        ET.SubElement(
            surface,
            _tei("zone"),
            {
                "xml:id": f"z{row['box_id']}",
                "ulx": str(row["x"]),
                "uly": str(row["y"]),
                "lrx": str(row["x"] + row["w"]),
                "lry": str(row["y"] + row["h"]),
            },
        )

    edition = ET.SubElement(
        ET.SubElement(ET.SubElement(root, _tei("text")), _tei("body")),
        _tei("div"),
        type="edition",
        subtype="transliteration",
    )
    block = ET.SubElement(edition, _tei("ab"))
    for line in release.reading.lines if release.reading else []:
        ET.SubElement(block, _tei("lb"), n=str(line.index + 1))
        index = 0
        for word_text in line.text.split():
            size = len(word_text.split("-"))
            word = ET.SubElement(block, _tei("w"))
            for sign_id in line.sign_ids[index : index + size]:
                _glyph(word, boxes.get(sign_id))
            index += size
        for sign_id in line.sign_ids[index:]:
            _glyph(ET.SubElement(block, _tei("w")), boxes.get(sign_id))
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _glyph(parent: ET.Element, row: dict | None) -> None:
    if row is None:
        return
    facs = f"#z{row['box_id']}"
    if row["certainty"] == "illegible":
        ET.SubElement(
            parent, _tei("gap"), reason="illegible", quantity="1", unit="character", facs=facs
        )
        return
    holder = parent
    if row["damage"] == "restored":
        holder = ET.SubElement(holder, _tei("supplied"), reason="lost")
    if row["certainty"] == "uncertain" or row["damage"] == "partial":
        holder = ET.SubElement(holder, _tei("unclear"))
    attributes = {"facs": facs}
    if row["sign"]:
        attributes["ref"] = f"#{row['sign']}"
    glyph = ET.SubElement(holder, _tei("g"), attributes)
    glyph.text = row["reading"] or row["sign"] or "?"
