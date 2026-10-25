"""Synthetic tablets: pasted only into blank space, only from train, labelled where the ink is."""

from __future__ import annotations

import json

import numpy as np
import pytest
import yaml
from PIL import Image

from la import signboxes, synth
from test_signboxes import big_sign, corpus, save_ink, tablet_with  # noqa: F401 - fixture


@pytest.fixture
def dataset(corpus, tmp_path):  # noqa: F811
    # A third, larger tablet gives the train split room to paste into.
    folder = signboxes.IMAGE_DIR / "HT-3"
    folder.mkdir(parents=True)
    a, b = big_sign(31), big_sign(32)
    save_ink(tablet_with({(10, 20): a, (10, 240): b}, shape=(600, 700)), folder / "HT-3.png")
    save_ink(a, folder / "HT-3_1.png")
    save_ink(b, folder / "HT-3_2.png")
    base = "https://lineara.eu/img/tracings/HT-3"
    corpus["HT 3"] = {"id": "HT 3", "url": "https://lineara.eu/documents/HT-3/", "tracing": f"{base}.png", "signs": [
        {"position": 1, "sign": "AB01", "reading": "da", "role": "syllabogram", "image": f"{base}_1.png"},
        {"position": 2, "sign": "AB08", "reading": "a", "role": "syllabogram", "image": f"{base}_2.png"},
    ]}
    out = tmp_path / "ds"
    signboxes.build_dataset(corpus, out=out, labels="sign", val_fraction=0, test_fraction=0,
                            test_tablets=frozenset({"HT 2"}), workers=1)
    return out


def read_boxes(label_path, width, height):
    boxes = []
    for row in label_path.read_text().split("\n"):
        if row:
            c, cx, cy, w, h = row.split()
            cx, cy, w, h = float(cx) * width, float(cy) * height, float(w) * width, float(h) * height
            boxes.append((int(c), round(cx - w / 2), round(cy - h / 2), round(cx + w / 2), round(cy + h / 2)))
    return boxes


def test_synthetic_tablets_keep_the_host_and_box_every_pasted_sign(dataset):
    report = synth.build_synth(dataset, count=6, seed=0, blank_ratio=0)
    assert report["pasted_boxes"] > 0
    annotations = {t["tablet"]: t for t in json.loads((dataset / "annotations.json").read_text())}
    for image_path in sorted((dataset / "images" / "synth").glob("*.png")):
        ink = np.array(Image.open(image_path)) < 128
        height, width = ink.shape
        boxes = read_boxes(dataset / "labels" / "synth" / f"{image_path.stem}.txt", width, height)
        assert all(c == 0 for c, *_ in boxes)
        for _, x0, y0, x1, y1 in boxes:
            assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
            assert ink[y0:y1, x0:x1].any()
        labelled = np.zeros_like(ink)
        for _, x0, y0, x1, y1 in boxes:
            labelled[max(0, y0 - 1):y1 + 1, max(0, x0 - 1):x1 + 1] = True
        assert not (ink & ~labelled).any()        # every stroke belongs to a box: nothing pasted unlabelled
    hosts = {annotations[t]["split"] for t in report["hosts"]}
    assert hosts == {"train"}


def test_pasted_signs_never_overlap_existing_ink():
    host = np.zeros((400, 400), dtype=bool)
    host[50:150, 50:150] = True
    rows = [(0, (50, 50, 150, 150))]
    bank = [{"mask": big_sign(1), "class_id": 0, "key": "AB01", "tablet": "HT 9"}]
    ink, out_rows, pasted = synth.compose(host, rows, bank, np.array([1.0]), np.random.default_rng(0))
    assert out_rows[0] == rows[0] and len(out_rows) == 1 + len(pasted)
    assert pasted
    for _, (x0, y0, x1, y1) in out_rows[1:]:
        assert x1 <= 50 or x0 >= 150 or y1 <= 50 or y0 >= 150
    others = [box for _, box in out_rows[1:]]
    for i, a in enumerate(others):
        for b in others[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_signs_from_val_and_test_tablets_are_never_pasted(dataset):
    annotations = json.loads((dataset / "annotations.json").read_text())
    bank = synth.sign_bank(dataset, annotations)
    assert {s["tablet"] for s in bank} == {t["tablet"] for t in annotations if t["split"] == "train"}
    assert "HT 2" not in {s["tablet"] for s in bank}


def test_rare_signs_are_drawn_more_often_than_their_share():
    bank = [{"key": "common"}] * 9 + [{"key": "rare"}]
    weights = synth.sampling_weights(bank)
    assert weights[-1] / weights.sum() > 0.1                     # its natural share
    assert weights[-1] < weights[:9].sum()                       # but common signs still dominate


def test_synthesis_is_reproducible_and_listed_for_training(dataset):
    synth.build_synth(dataset, count=3, seed=4)
    first = {p.name: p.read_bytes() for p in (dataset / "images" / "synth").glob("*.png")}
    synth.build_synth(dataset, count=3, seed=4)
    assert first == {p.name: p.read_bytes() for p in (dataset / "images" / "synth").glob("*.png")}
    listing = (dataset / "train.txt").read_text().split()
    assert sum("images/train/" in p for p in listing) == len(list((dataset / "images" / "train").glob("*.png")))
    assert sum("images/synth/" in p for p in listing) == 3
    assert yaml.safe_load((dataset / "data.yaml").read_text())["train"] == "train.txt"


def test_rebuilding_the_dataset_removes_synthetic_tablets(dataset, corpus):  # noqa: F811
    synth.build_synth(dataset, count=2)
    signboxes.build_dataset(corpus, out=dataset, labels="sign", val_fraction=0, test_fraction=0,
                            test_tablets=frozenset({"HT 2"}), workers=1)
    assert not (dataset / "images" / "synth").exists() and not (dataset / "train.txt").exists()
    assert yaml.safe_load((dataset / "data.yaml").read_text())["train"] == "images/train"
