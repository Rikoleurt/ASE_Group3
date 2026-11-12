"""Reading a tablet drawing in two steps: a detector finds signs, a classifier names them.

Shared by the web demo, `evaluate.py`, the benchmark and `la.pseudo`, so all of
them cut crops exactly as `la.signcrops` did for training. Models are passed in
(Ultralytics `YOLO` objects); nothing here imports Ultralytics.

Two optional refinements of the classifier's answer:

* test-time augmentation (`tta=True`): average the classifier over a few
  slightly looser, tighter and shifted boxes, since detector boxes are a few
  pixels off and a crop cut in a slightly different place should read the same;
* frequency prior (`prior_correction`): the classifier was trained on rare
  signs copied up to `augment.resample_count`, which teaches it that rare signs
  are commoner than they are; reweighting by real / resampled count (to a power
  `alpha`) puts some of the true frequency back;
* nearest neighbours (`NeighbourBank`): compare a crop's embedding with every
  real training crop and blend that vote with the classifier's. Rare signs have
  one or two training examples, too few for a classifier's weights but enough
  to be matched against;
* a sign comparer (`la.comparer.Comparer`): an embedding trained to compare
  signs, scored against reference drawings and font renders, optionally also
  proposing signs the classifier never learned (zero-shot).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from la import augment

TOP_LABELS = 5
# Box variants for test-time augmentation: (grow, dx, dy) as fractions of the box's longer side.
TTA_VARIANTS = ((0.0, 0.0, 0.0), (0.06, 0.0, 0.0), (-0.04, 0.0, 0.0),
                (0.0, 0.04, 0.0), (0.0, -0.04, 0.0), (0.0, 0.0, 0.04), (0.0, 0.0, -0.04))


def ink_of(image: np.ndarray) -> np.ndarray:
    """Ink mask of a drawing given as a grey or BGR/RGB uint8 array (dark strokes on light)."""
    grey = image if image.ndim == 2 else image[..., :3].mean(axis=2)
    return grey < 128


def crops_of(ink: np.ndarray, boxes) -> list[np.ndarray]:
    """3-channel 128 px crops, cut exactly as the classifier was trained on."""
    return [np.repeat(augment.square_crop(ink, tuple(box))[..., None], 3, axis=2) for box in boxes]


def tta_boxes(box, variants=TTA_VARIANTS) -> list[tuple[float, float, float, float]]:
    x0, y0, x1, y1 = box
    side = max(x1 - x0, y1 - y0)
    out = []
    for grow, dx, dy in variants:
        g, ox, oy = grow * side / 2, dx * side, dy * side
        out.append((x0 - g + ox, y0 - g + oy, x1 + g + ox, y1 + g + oy))
    return out


def class_probabilities(classifier, crops: list[np.ndarray], device: str | None = None
                        ) -> tuple[list[str], np.ndarray]:
    """The classifier's class names and an (n crops x n classes) probability matrix."""
    names = [classifier.names[i] for i in range(len(classifier.names))]
    if not crops:
        return names, np.zeros((0, len(names)), dtype=np.float32)
    results = classifier.predict(crops, device=device, verbose=False)
    return names, np.stack([r.probs.data.cpu().numpy() for r in results])


def top_labels(names: list[str], probs: np.ndarray, top: int = TOP_LABELS) -> list[list[tuple[str, float]]]:
    out = []
    for row in probs:
        order = np.argsort(-row)[:top]
        out.append([(names[int(i)], float(row[i])) for i in order])
    return out


def name_boxes(classifier, ink: np.ndarray, boxes: list[tuple[float, float, float, float]],
               top: int = TOP_LABELS, device: str | None = None, tta: bool = False,
               bank: NeighbourBank | None = None, comparer=None, real_counts: dict[str, int] | None = None,
               prior: float = 0.0) -> list[list[tuple[str, float]]]:
    """For each box, the classifier's `top` (sign ID, probability) pairs, best first.

    With `prior`, the frequency prior (`prior_correction`) is applied after the other refinements.
    """
    if not boxes:
        return []
    names, probs = boxed_probabilities(classifier, ink, boxes, device=device, tta=tta, bank=bank, comparer=comparer)
    probs = prior_correction(names, probs, real_counts or {}, prior)
    return top_labels(names, probs, top)


def boxed_probabilities(classifier, ink, boxes, device=None, tta=False, bank=None, comparer=None) -> tuple[list[str], np.ndarray]:
    """Class names and per-box probabilities, with the optional refinements applied."""
    if tta:
        flat = [v for b in boxes for v in tta_boxes(b)]
        names, probs = class_probabilities(classifier, crops_of(ink, flat), device)
        probs = probs.reshape(len(boxes), len(TTA_VARIANTS), -1).mean(axis=1)
    else:
        names, probs = class_probabilities(classifier, crops_of(ink, boxes), device)
    if bank is not None:
        probs = bank.blend(names, probs, bank.embed(crops_of(ink, boxes)))
    if comparer is not None:     # may add zero-shot names, so it returns them
        names, probs = comparer.blend(names, probs, crops_of(ink, boxes))
    return names, probs


def prior_correction(names: list[str], probs: np.ndarray, real_counts: dict[str, int], alpha: float,
                     target: int = 100) -> np.ndarray:
    """Reweight each class by (real / resampled training count) ** alpha, then renormalise."""
    if not alpha or not len(probs):
        return probs
    factor = np.array([(n / augment.resample_count(n, target)) ** alpha if (n := real_counts.get(c, 0)) else 1.0
                       for c in names], dtype=np.float32)
    out = probs * factor
    return out / np.maximum(out.sum(axis=1, keepdims=True), 1e-12)


@dataclass
class NeighbourBank:
    """Embeddings of real training crops, and how to blend their vote with a classifier's.

    `embed_fn` maps a list of crops to an (n x d) array: the classifier's own
    backbone or a general pretrained one. A class's neighbour score is its best
    cosine similarity to the query, turned into probabilities by a softmax at
    `temperature`; the answer is (1 - weight) * classifier + weight * neighbours.
    """
    embed_fn: object
    signs: np.ndarray            # sign ID of each reference crop
    vectors: np.ndarray          # unit-normalised reference embeddings
    weight: float = 0.5
    temperature: float = 0.05

    @classmethod
    def build(cls, embed_fn, signs: list[str], crops: list[np.ndarray], **kw) -> NeighbourBank:
        return cls(embed_fn, np.asarray(signs), _unit(embed_fn(crops)), **kw)

    def embed(self, crops: list[np.ndarray]) -> np.ndarray:
        return _unit(self.embed_fn(crops)) if crops else np.zeros((0, self.vectors.shape[1]), np.float32)

    def scores(self, names: list[str], queries: np.ndarray) -> np.ndarray:
        """Best similarity of each query to each of `names` (-1 where a name has no reference)."""
        sims = queries @ self.vectors.T
        out = np.full((len(queries), len(names)), -1.0, dtype=np.float32)
        index = {n: i for i, n in enumerate(names)}
        for sign in np.unique(self.signs):
            if sign in index:
                out[:, index[sign]] = sims[:, self.signs == sign].max(axis=1)
        return out

    def blend(self, names: list[str], probs: np.ndarray, queries: np.ndarray) -> np.ndarray:
        if not len(probs):
            return probs
        s = self.scores(names, queries) / self.temperature
        s = np.exp(s - s.max(axis=1, keepdims=True))
        neighbour = s / s.sum(axis=1, keepdims=True)
        return (1 - self.weight) * probs + self.weight * neighbour


def _unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)
