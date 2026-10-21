"""Self-training: only new boxes are proposed, and unreviewed ones never reach val or test."""

from __future__ import annotations

import csv
import json

import pytest

from la import pseudo, signboxes
from test_signboxes import corpus  # noqa: F401 - fixture


def test_detections_on_labelled_signs_are_not_proposed():
    labelled = [(10, 10, 50, 50)]
    boxes = [(12, 11, 49, 52), (100, 100, 140, 150), (40, 40, 80, 80)]
    found = pseudo.unlabelled(boxes, [0.9, 0.8, 0.7], labelled)
    assert found == [((100, 100, 140, 150), 0.8), ((40, 40, 80, 80), 0.7)]  # IoU of the last is 0.03


def write_candidates(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(pseudo.CANDIDATE_COLUMNS)
        for r in rows:
            writer.writerow(r)


def test_accept_appends_only_ticked_rows_once(tmp_path):
    candidates = tmp_path / "candidates.csv"
    write_candidates(candidates, [
        [1, "HT 1", "train", 200, 20, 260, 90, 0.93, 1, "sheet_001.png"],
        [2, "HT 1", "train", 10, 300, 40, 330, 0.55, "", "sheet_001.png"],
    ])
    extra = tmp_path / "labels" / "extra.csv"
    assert pseudo.accept(candidates, extra=extra) == 1
    assert pseudo.accept(candidates, extra=extra) == 0
    rows = list(csv.DictReader(extra.open(encoding="utf-8")))
    assert rows == [{"tablet": "HT 1", "x0": "200", "y0": "20", "x1": "260", "y1": "90",
                     "source": "pseudo", "confidence": "0.93"}]
    with pytest.raises(ValueError):
        pseudo.accept(candidates, source="guess", extra=extra)


def test_extra_boxes_are_merged_in_sign_mode_and_unreviewed_ones_stay_out_of_test(corpus, tmp_path):  # noqa: F811
    extra = tmp_path / "extra.csv"
    extra.write_text("tablet,x0,y0,x1,y1,source,confidence\n"
                     "HT 1,200,20,260,90,pseudo,0.9\n"
                     "HT 2,200,20,260,90,pseudo,0.9\n"
                     "HT 2,20,300,60,360,reviewed,\n", encoding="utf-8")
    out = tmp_path / "ds"
    report = signboxes.build_dataset(corpus, out=out, labels="sign", val_fraction=0, test_fraction=0,
                                     test_tablets=frozenset({"HT 2"}), workers=1, extra_labels=extra)
    assert report["extra_boxes"] == {"train": 1, "test": 1}
    assert report["extra_skipped"] == [{"tablet": "HT 2", "reason": "unreviewed box in test"}]
    assert len((out / "labels/train/HT-1.txt").read_text().split()) == 3 * 5
    annotations = {t["tablet"]: t for t in json.loads((out / "annotations.json").read_text())}
    sources = [s["source"] for s in annotations["HT 2"]["signs"]]
    assert sources == ["matched", "matched", "reviewed"]
    assert annotations["HT 2"]["signs"][-1]["xyxy"] == [20, 300, 60, 360]


def test_extra_boxes_are_ignored_outside_sign_mode(corpus, tmp_path):  # noqa: F811
    extra = tmp_path / "extra.csv"
    extra.write_text("tablet,x0,y0,x1,y1,source,confidence\nHT 1,200,20,260,90,reviewed,\n", encoding="utf-8")
    report = signboxes.build_dataset(corpus, out=tmp_path / "ds", labels="identity", val_fraction=0,
                                     test_fraction=0, test_tablets=frozenset({"HT 2"}), workers=1,
                                     extra_labels=extra)
    assert report["extra_boxes"] == {}
    assert report["extra_skipped"] == [{"tablet": "HT 1", "reason": "label mode identity"}]


@pytest.mark.parametrize("row", ["HT 1,200,20,260,90,guess,", "HT 1,260,20,200,90,reviewed,"])
def test_malformed_extra_boxes_fail_before_the_dataset_is_cleared(corpus, tmp_path, row):  # noqa: F811
    extra = tmp_path / "extra.csv"
    extra.write_text(f"tablet,x0,y0,x1,y1,source,confidence\n{row}\n", encoding="utf-8")
    marker = tmp_path / "ds" / "images" / "train" / "keep.png"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"keep")
    with pytest.raises(ValueError):
        signboxes.build_dataset(corpus, out=tmp_path / "ds", labels="sign", workers=1, extra_labels=extra)
    assert marker.exists()
