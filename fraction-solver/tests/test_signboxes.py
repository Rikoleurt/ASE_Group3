"""Sign-box tests, on synthetic tablets whose boxes are known.

The real crops are exact cut-outs of their tracings; these tests build that
situation from scratch, so they need neither the network nor the image cache.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from la import signboxes


def stroke_sign(seed: int, size=(40, 30)) -> np.ndarray:
    """A small irregular glyph: a few random strokes, so no two signs coincide."""
    rng = np.random.default_rng(seed)
    h, w = size
    m = np.zeros((h, w), dtype=bool)
    for _ in range(4):
        if rng.random() < 0.5:
            r = rng.integers(2, h - 2)
            a, b = sorted(rng.integers(2, w - 2, size=2))
            m[r:r + 2, a:b + 1] = True
        else:
            c = rng.integers(2, w - 2)
            a, b = sorted(rng.integers(2, h - 2, size=2))
            m[a:b + 1, c:c + 2] = True
    return m


def tablet_with(signs: dict[tuple[int, int], np.ndarray], shape=(200, 160)) -> np.ndarray:
    t = np.zeros(shape, dtype=bool)
    for (x, y), s in signs.items():
        t[y:y + s.shape[0], x:x + s.shape[1]] |= s
    return t


def save_ink(mask: np.ndarray, path, rgba: bool = False) -> None:
    """Write ink as SigLA does (strokes in alpha) or as lineara.eu does (opaque)."""
    if rgba:
        a = np.zeros(mask.shape + (4,), dtype=np.uint8)
        a[..., 3] = np.where(mask, 255, 0)
        Image.fromarray(a, "RGBA").save(path)
    else:
        Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).save(path)


def test_locate_finds_exact_cutouts():
    a, b = stroke_sign(1), stroke_sign(2)
    tracing = tablet_with({(10, 20): a, (90, 120): b})
    assert signboxes.locate(tracing, a) == (10, 20, pytest.approx(1.0))
    assert signboxes.locate(tracing, b) == (90, 120, pytest.approx(1.0))


def big_sign(seed: int) -> np.ndarray:
    """A sign drawn at original resolution: large, with strokes thick enough to survive shrinking."""
    return np.kron(stroke_sign(seed), np.ones((4, 4), dtype=bool))


def test_estimate_scale_recovers_a_shrunken_tracing():
    # As on lineara.eu: crops at full size, the tracing shrunk to fit 1440 px.
    signs = {(40, 40): big_sign(1), (240, 60): big_sign(2), (60, 260): big_sign(3), (260, 300): big_sign(4)}
    full = tablet_with(signs, shape=(480, 420))
    tracing = signboxes.resize_mask(full, 0.6) > 0
    crops = list(signs.values())
    assert signboxes.estimate_scale(tracing, crops) == pytest.approx(0.6, abs=0.011)
    assert signboxes.estimate_scale(full, crops) == pytest.approx(1.0, abs=0.011)


def test_scoring_does_not_reward_shrinking_a_crop_onto_dense_ink():
    # A tiny crop lands on ink anywhere in a dense tablet; cosine must still prefer the true scale.
    signs = {(40, 40): big_sign(1), (240, 60): big_sign(2), (60, 260): big_sign(3)}
    tracing = tablet_with(signs, shape=(420, 420))
    tracing[350:410, 20:400] = True  # a heavily inked band, as on damaged or ruled tablets
    assert signboxes.estimate_scale(tracing, list(signs.values())) == pytest.approx(1.0, abs=0.011)


def test_locate_reports_a_poor_match_instead_of_inventing_one():
    tracing = tablet_with({(10, 20): stroke_sign(1)})
    unrelated = np.ones((40, 30), dtype=bool)
    assert signboxes.locate(tracing, unrelated)[2] < 0.5


def test_locate_rejects_empty_and_oversized_crops():
    tracing = tablet_with({(10, 20): stroke_sign(1)})
    assert signboxes.locate(tracing, np.zeros((5, 5), dtype=bool))[2] == 0.0
    assert signboxes.locate(tracing, np.ones((300, 10), dtype=bool))[2] == 0.0


def test_ink_bounds_is_tight_and_exclusive():
    m = np.zeros((10, 10), dtype=bool)
    m[2:5, 3:8] = True
    assert signboxes.ink_bounds(m) == (3, 2, 8, 5)


def test_yolo_line_is_normalised_centre_and_size():
    box = signboxes.SignBox("AB01", "syllabogram", 1, x0=10, y0=20, x1=30, y1=60, match=1.0)
    assert signboxes.yolo_line(0, box, width=100, height=200) == "0 0.200000 0.200000 0.200000 0.200000"


def test_split_is_deterministic_and_respects_fractions():
    ids = [f"HT {i}" for i in range(2000)]
    first = [signboxes.split_for(i, 0.15, 0.15) for i in ids]
    assert first == [signboxes.split_for(i, 0.15, 0.15) for i in ids]
    assert 0.10 < first.count("val") / len(ids) < 0.20
    assert 0.10 < first.count("test") / len(ids) < 0.20
    assert 0.60 < first.count("train") / len(ids) < 0.80


def test_adding_a_test_split_only_takes_tablets_from_train():
    ids = [f"HT {i}" for i in range(2000)]
    before = [signboxes.split_for(i, 0.15) for i in ids]
    after = [signboxes.split_for(i, 0.15, 0.15) for i in ids]
    assert all(a == "val" for b, a in zip(before, after) if b == "val")
    assert all(b == "train" for b, a in zip(before, after) if a == "test")


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Two tablets in the image cache: one opaque, one with strokes in alpha."""
    monkeypatch.setattr(signboxes, "IMAGE_DIR", tmp_path / "images")
    docs = {}
    for n, rgba in ((1, False), (2, True)):
        doc_id, sl = f"HT {n}", f"HT-{n}"
        a, b = big_sign(10 * n), big_sign(10 * n + 1)
        tracing = tablet_with({(10, 20): a, (180, 240): b}, shape=(420, 320))
        base = f"https://lineara.eu/img/tracings/{sl}"
        doc = {"id": doc_id, "url": f"https://lineara.eu/documents/{sl}/", "tracing": f"{base}.png", "signs": [
            {"position": 1, "sign": "AB01", "role": "syllabogram", "image": f"{base}_1.png"},
            {"position": 2, "sign": "A707", "role": "fraction", "image": f"{base}_2.png"},
            {"position": 3, "sign": "", "role": "erasure", "image": f"{base}_3.png"},
        ]}
        folder = tmp_path / "images" / sl
        folder.mkdir(parents=True)
        save_ink(tracing, folder / f"{sl}.png", rgba)
        save_ink(a, folder / f"{sl}_1.png", rgba)
        save_ink(b, folder / f"{sl}_2.png", rgba)
        save_ink(a, folder / f"{sl}_3.png", rgba)
        docs[doc_id] = doc
    return docs


def test_tablet_boxes_from_cached_images(corpus):
    for doc in corpus.values():
        tablet = signboxes.tablet_boxes(doc)
        assert (tablet.width, tablet.height) == (320, 420)
        assert tablet.scale == pytest.approx(1.0, abs=0.011)
        assert [b.sign for b in tablet.boxes] == ["AB01", "A707"]  # the erasure is left out
        first = tablet.boxes[0]
        x0, y0, x1, y1 = signboxes.ink_bounds(big_sign(10 * int(doc["id"].split()[1])))
        assert (first.x0, first.y0, first.x1, first.y1) == (10 + x0, 20 + y0, 10 + x1, 20 + y1)


def test_build_dataset_writes_ultralytics_layout_and_forces_demo_tablet_to_test(corpus, tmp_path):
    out = tmp_path / "ds"
    report = signboxes.build_dataset(corpus, out=out, labels="role", val_fraction=0.0, test_fraction=0.0,
                                     test_tablets=frozenset({"HT 2"}), workers=1)
    assert report["tablets"] == {"train": 1, "test": 1} and report["forced_test"] == ["HT 2"]
    assert report["splits"] == {"HT 1": "train", "HT 2": "test"}
    assert (out / "images" / "test" / "HT-2.png").exists()
    assert not (out / "images" / "train" / "HT-2.png").exists()
    label = (out / "labels" / "train" / "HT-1.txt").read_text().split("\n")
    assert [row.split()[0] for row in label if row] == ["0", "2"]  # syllabogram, fraction
    image = np.array(Image.open(out / "images" / "train" / "HT-1.png"))
    assert set(np.unique(image)) == {0, 255}
    yaml = (out / "data.yaml").read_text()
    assert "train: images/train" in yaml and "test: images/test" in yaml and "2: fraction" in yaml
    assert "CC BY-NC-SA" in (out / "LICENCE.txt").read_text()


def test_rebuilding_clears_tablets_from_their_old_split(corpus, tmp_path):
    out = tmp_path / "ds"
    signboxes.build_dataset(corpus, out=out, val_fraction=0.0, test_fraction=0.0,
                            test_tablets=frozenset(), workers=1)
    assert (out / "images" / "train" / "HT-2.png").exists()
    signboxes.build_dataset(corpus, out=out, val_fraction=0.0, test_fraction=0.0,
                            test_tablets=frozenset({"HT 2"}), workers=1)
    assert (out / "images" / "test" / "HT-2.png").exists()
    assert not (out / "images" / "train" / "HT-2.png").exists()
    assert not (out / "labels" / "train" / "HT-2.txt").exists()
