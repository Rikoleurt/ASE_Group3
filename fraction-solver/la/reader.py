"""Reading a tablet drawing in two steps: a detector finds signs, a classifier names them.

Shared by the web demo, `evaluate.py` and `la.pseudo`, so all three cut crops
exactly as `la.signcrops` did for training. Models are passed in (Ultralytics
`YOLO` objects); nothing here imports Ultralytics.
"""

from __future__ import annotations

import numpy as np

from la import augment

TOP_LABELS = 5


def ink_of(image: np.ndarray) -> np.ndarray:
    """Ink mask of a drawing given as a grey or BGR/RGB uint8 array (dark strokes on light)."""
    grey = image if image.ndim == 2 else image[..., :3].mean(axis=2)
    return grey < 128


def name_boxes(classifier, ink: np.ndarray, boxes: list[tuple[float, float, float, float]],
               top: int = TOP_LABELS, device: str | None = None) -> list[list[tuple[str, float]]]:
    """For each box, the classifier's `top` (sign ID, probability) pairs, best first."""
    if not boxes:
        return []
    crops = [np.repeat(augment.square_crop(ink, box)[..., None], 3, axis=2) for box in boxes]
    results = classifier.predict(crops, device=device, verbose=False)
    named = []
    for result in results:
        probs = result.probs.data.cpu().numpy()
        order = np.argsort(-probs)[:top]
        named.append([(result.names[int(i)], float(probs[i])) for i in order])
    return named
