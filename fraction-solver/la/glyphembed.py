"""Glyph embeddings: one vector per sign crop, for "which other signs look like this one".

The vectors are the penultimate-layer features of the trained sign classifier
(`models/linear_a_classifier.pt`), so two crops are close when the network sees
the same strokes. Crops are prepared exactly as the reader prepares them for
classification (`la.reader`, `la.augment.square_crop`): ink only, centred on a
white square, aspect kept. That makes a corpus crop (an alpha-channel or palette
PNG from SigLA) and an uploaded crop (a BGR cut from a photo) comparable.

`embed_inks` takes a loaded Ultralytics model, nothing here imports Ultralytics.
Data licence: the corpus crops are SigLA-derived, CC BY-NC-SA 4.0; the vectors
derived from them are non-commercial too and are never committed.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from la import augment
from la.reader import ink_of

BACKBONES = ("yolo-cls",)  # a DINOv2 option can be added here later
DEFAULT_BACKBONE = "yolo-cls"
MAX_CROP_BYTES = 2 * 1024 * 1024
MAX_CROP_SIDE = 4096


class BadCrop(ValueError):
    """The uploaded crop is not a usable image."""


def weights_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def prepared(ink: np.ndarray) -> np.ndarray:
    """An ink mask as the 3-channel square image the classifier was trained on."""
    if ink.ndim != 2 or not ink.any():
        raise BadCrop("The crop has no ink.")
    height, width = ink.shape
    return np.repeat(augment.square_crop(ink, (0, 0, width, height))[..., None], 3, axis=2)


def ink_from_png_bytes(data: bytes) -> np.ndarray:
    """Ink mask of an uploaded crop (any PNG/JPEG, dark strokes on light, or alpha strokes)."""
    if len(data) > MAX_CROP_BYTES:
        raise BadCrop("The crop is larger than 2 MB.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ("PNG", "JPEG"):
                raise BadCrop("Only PNG or JPEG crops are supported.")
            if max(image.size) > MAX_CROP_SIDE:
                raise BadCrop("The crop is too large.")
            rgba = image.convert("RGBA")
    except BadCrop:
        raise
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise BadCrop("Invalid image.") from error
    pixels = np.asarray(rgba)
    alpha = pixels[..., 3]
    if alpha.min() != alpha.max():
        return alpha > 64
    return ink_of(pixels[..., :3])


def embed_inks(model, inks: list[np.ndarray], batch: int = 64, device: str = "cpu") -> np.ndarray:
    """(n, d) float32 features, one row per ink mask, processed in small batches."""
    rows = []
    for start in range(0, len(inks), batch):
        images = [prepared(ink) for ink in inks[start:start + batch]]
        rows.extend(vector.detach().cpu().numpy().astype(np.float32).ravel()
                    for vector in model.embed(images, device=device, verbose=False))
    return np.stack(rows) if rows else np.zeros((0, 0), np.float32)


def normalised(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)
