"""Classifier crops: inherited splits, resampling in train only, unlearnable signs reported."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from la import signboxes, signcrops
from test_signboxes import corpus  # noqa: F401 - fixture


@pytest.fixture
def dataset(corpus, tmp_path):  # noqa: F811
    corpus["HT 2"]["signs"][0]["sign"] = "AB99"       # a sign that only occurs in test
    out = tmp_path / "ds"
    signboxes.build_dataset(corpus, out=out, labels="sign", val_fraction=0, test_fraction=0,
                            test_tablets=frozenset({"HT 2"}), workers=1)
    return out


def test_crops_follow_the_detection_split_and_resample_only_train(dataset, tmp_path):
    out = tmp_path / "crops"
    report = signcrops.build_crops(dataset, out, target=100, seed=0)
    train = {p.parent.name: [] for p in (out / "train").glob("*/*.png")}
    for p in (out / "train").glob("*/*.png"):
        train[p.parent.name].append(p.name)
    assert sorted(train) == ["A707", "AB01"]
    assert all(len(files) == 10 for files in train.values())     # 1 real crop -> sqrt(1 * 100)
    assert sum(not f.split("_")[-1].startswith("v") for f in train["AB01"]) == 1
    test = sorted(p.relative_to(out / "test").as_posix() for p in (out / "test").glob("*/*.png"))
    assert test == ["A707/HT-2_2.png"]                           # one per real sign, unvaried
    assert report["unseen_in_train"] == {"train": 0, "val": 0, "test": 1}
    assert report["classes_without_train"] == ["AB99"]
    with Image.open(out / "test" / "A707" / "HT-2_2.png") as image:
        assert image.size == (128, 128)
    classes = json.loads((out / "classes.json").read_text(encoding="utf-8"))
    assert classes["AB01"]["name"] == "AB01 (da)" and classes["A707"]["roles"] == ["fraction"]
    assert "CC BY-NC-SA" in (out / "LICENCE.txt").read_text()


def test_crops_are_reproducible_for_a_seed(dataset, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    signcrops.build_crops(dataset, a, target=16, seed=3)
    signcrops.build_crops(dataset, b, target=16, seed=3)
    files = sorted(p.relative_to(a) for p in a.rglob("*.png"))
    assert files == sorted(p.relative_to(b) for p in b.rglob("*.png"))
    assert all((a / f).read_bytes() == (b / f).read_bytes() for f in files)


def test_boxes_added_by_review_are_not_classifier_examples(corpus, tmp_path):  # noqa: F811
    extra = tmp_path / "extra.csv"
    extra.write_text("tablet,x0,y0,x1,y1,source,confidence\nHT 1,200,20,260,90,pseudo,0.9\n", encoding="utf-8")
    out = tmp_path / "ds"
    signboxes.build_dataset(corpus, out=out, labels="sign", val_fraction=0, test_fraction=0,
                            test_tablets=frozenset({"HT 2"}), workers=1, extra_labels=extra)
    report = signcrops.build_crops(out, tmp_path / "crops", target=1)
    assert report["real"]["train"] == 2
    assert "unidentified" not in report["classes_without_train"]


def test_missing_dataset_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError, match="la.cli dataset"):
        signcrops.build_crops(tmp_path / "nothing", tmp_path / "crops")
