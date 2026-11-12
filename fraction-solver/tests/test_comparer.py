"""la.comparer on tiny fake data: split safety, scores, blending, proposals, save/load, a tiny training run."""

import numpy as np
import pytest
from la import comparer
from la.comparer import CropDataset, Item, RefBank

torch = pytest.importorskip("torch")


def _ink(h=60, w=60):
    ink = np.zeros((h, w), bool)
    ink[10:50, 25:35] = True
    return ink


def _annotations():
    def tablet(name, split, signs):
        return {"tablet": name, "image": f"images/{split}/{name}.png", "split": split,
                "signs": [{"sign": s, "xyxy": [5, 5, 55, 55], "position": n, "source": "matched"}
                          for n, s in enumerate(signs)]}
    return [tablet("T1", "train", ["A", "A", "B"]), tablet("T2", "val", ["C", "A"]),
            tablet("T3", "test", ["D"])]


def _items():
    ink = _ink()
    return [Item(s, comparer.augment.square_crop(ink, (5, 5, 55, 55)), ink[5:55, 5:55].copy())
            for s in ("A", "A", "B")]


def test_read_train_never_opens_val_or_test():
    opened = []

    def load(path):
        opened.append(path.name)
        return _ink()

    items = comparer.read_train(_annotations(), "ds", load=load)
    assert opened == ["T1.png"]
    assert sorted(i.sign for i in items) == ["A", "A", "B"]
    assert comparer.vocabulary(_annotations()) == ["A", "B", "C", "D"]    # names only, from every split


def test_dataset_classes_are_train_only_and_fonts_follow_them():
    fonts = {"A": _ink()[10:50, 25:35], "C": _ink()[10:50, 25:35]}
    data = CropDataset(_items(), fonts)
    assert data.classes == ["A", "B"]
    assert [s for s, _ in data.fonts] == ["A"]       # C has no real train crop: stays zero-shot
    assert len(data) == 4
    x, y = data[3]
    assert tuple(x.shape) == (1, 128, 128) and data.classes[y] == "A"
    # same item, same epoch, same pixels; another epoch varies
    assert torch.equal(data[0][0], data[0][0])
    w = data.weights()
    assert len(w) == 4 and w[2] > w[0]               # B (one crop) draws more per item than A


def _bank():
    v = np.array([[1, 0], [0.9, 0.1], [0, 1], [0.6, 0.8]], np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return RefBank(np.array(["A", "A", "B", "Z"]), v, np.array([False, False, False, True]))


def test_bank_scores_shape_order_and_missing():
    q = np.array([[1.0, 0.0], [0.0, 1.0]], np.float32)
    s = _bank().scores(q, ["B", "A", "Q"])
    assert s.shape == (2, 3)
    assert s[0, 1] > s[0, 0] and s[1, 0] > s[1, 1]    # A for the first query, B for the second
    assert (s[:, 2] == -1).all()                       # no reference
    # k=2 averages A's two references
    assert _bank().scores(q, ["A"], k=2)[0, 0] < _bank().scores(q, ["A"], k=1)[0, 0]


def test_blend_mixes_and_zero_shot_adds_font_only_signs():
    bank = _bank()
    q = np.array([[0.6, 0.8]], np.float32)             # looks like the font-only sign Z
    names, probs = ["A", "B"], np.array([[0.9, 0.1]], np.float32)
    n0, p0 = comparer.blend(names, probs, bank, q, weight=1.0, temperature=0.05)
    assert n0 == ["A", "B"] and p0.shape == (1, 2) and p0.sum() == pytest.approx(1)
    n1, p1 = comparer.blend(names, probs, bank, q, weight=0.5, temperature=0.05, zero_shot=True)
    assert n1 == ["A", "B", "Z"] and p1.shape == (1, 3)
    assert p1.sum() == pytest.approx(1) and p1[0, 2] > 0.4    # Z wins half the mass
    assert comparer.blend(names, probs, bank, q, weight=0.0)[1] is probs        # off means untouched


def test_propose_returns_font_only_classes():
    bank = _bank()
    q = np.array([[0.6, 0.8]], np.float32)
    assert bank.propose(q, 1)[0][0][0] == "Z"
    only = bank.propose(q, 5, font_only=True)[0]
    assert [s for s, _ in only] == ["Z"]
    assert {"A", "B", "Z"} == set(bank.all_signs) and bank.font_signs == ["Z"]


def test_train_save_load_roundtrip(tmp_path):
    items = _items() * 4
    fonts = {"A": _ink()[10:50, 25:35], "C": _ink()[10:50, 25:35]}
    c = comparer.train(items, fonts, tmp_path / "run", epochs=2, batch=4, dim=8, use_font=True,
                       backbone="tiny", pretrained=False, device="cpu", log=lambda *_: None)
    assert (tmp_path / "run" / "log.csv").read_text().count("\n") == 3
    crops = [i.crop for i in items[:3]]
    assert c.scores(crops, ["A", "B", "C"]).shape == (3, 3)
    assert "C" in {s for s, _ in c.propose(crops, 5, font_only=True)[0]}
    c.save(tmp_path / "w.pt")
    d = comparer.Comparer.load(tmp_path / "w.pt")
    assert np.allclose(c.scores(crops, ["A", "B", "C"]), d.scores(crops, ["A", "B", "C"]), atol=1e-5)
    assert d.bank.font_signs == ["A", "C"] and d.meta["classes"] == ["A", "B"]
    # resuming a finished run trains nothing more and keeps the log
    comparer.train(items, fonts, tmp_path / "run", epochs=2, batch=4, dim=8, use_font=True,
                   backbone="tiny", pretrained=False, device="cpu", log=lambda *_: None)
    assert (tmp_path / "run" / "log.csv").read_text().count("\n") == 3


def test_reader_applies_comparer_after_the_classifier():
    from types import MappingProxyType, SimpleNamespace

    from la import reader

    class Classifier:
        names = MappingProxyType({0: "A", 1: "B"})

        def predict(self, crops, device=None, verbose=False):
            probs = SimpleNamespace(data=SimpleNamespace(cpu=lambda: SimpleNamespace(numpy=lambda: np.array([.9, .1], np.float32))))
            return [SimpleNamespace(probs=probs) for _ in crops]

    class FakeComparer:
        def blend(self, names, probs, crops):
            assert len(crops) == len(probs) == 1
            return [*names, "Z"], np.concatenate([probs * 0.5, [[0.5]]], axis=1)

    ink = _ink()
    top = reader.name_boxes(Classifier(), ink, [(5, 5, 55, 55)], comparer=FakeComparer())
    assert {s for s, _ in top[0]} == {"A", "B", "Z"}
