from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from la import clustering, glyphembed


def blobs(seed=0, per=20, classes=4, dim=8, noise=0.05):
    rng = np.random.default_rng(seed)
    centres = np.eye(dim)[:classes]
    x = np.vstack([c + rng.normal(0, noise, (per, dim)) for c in centres])
    labels = np.repeat([f"S{i}" for i in range(classes)], per)
    return clustering.normalise(x), labels


def test_nmi_and_purity_bounds():
    labels = np.array(list("aabbcc"))
    assert clustering.nmi(np.array([0, 0, 1, 1, 2, 2]), labels) == pytest.approx(1.0)
    assert clustering.purity(np.array([0, 0, 1, 1, 2, 2]), labels) == 1.0
    assert clustering.nmi(np.zeros(6, int), labels) == pytest.approx(0.0)
    assert clustering.purity(np.zeros(6, int), labels) == 2 / 6


def test_kmeans_recovers_separated_classes_and_is_seeded():
    x, labels = blobs()
    first = clustering.kmeans(x, 4, seed=3)
    assert clustering.purity(first, labels) == 1.0
    assert clustering.nmi(first, labels) > 0.99
    assert np.array_equal(first, clustering.kmeans(x, 4, seed=3))


def test_dbscan_finds_clusters_and_noise():
    x, labels = blobs()
    found = clustering.dbscan(np.vstack([x, clustering.normalise(np.ones((1, 8)))]), eps=0.3, min_samples=5)
    assert found[-1] == -1
    assert found[:-1].max() + 1 == 4
    assert clustering.purity(found[:-1], labels) == 1.0


def test_outlier_flags_the_mislabelled_glyph_only_in_big_enough_classes():
    x, labels = blobs()
    x = np.vstack([x, np.eye(8)[[5]]])  # looks like nothing in S0, but is labelled S0
    labels = np.append(labels, "S0")
    _d, z = clustering.outlier_scores(x, labels)
    assert np.nanargmax(z) == len(x) - 1 and clustering.is_outlier(z)[-1]
    assert z[-1] > 2 * np.nanmax(z[:-1])  # far beyond the natural spread of the genuine S0 glyphs
    _d, z = clustering.outlier_scores(np.vstack([x, x[:2]]), np.append(labels, ["RARE", "RARE"]))
    assert np.isnan(z[-2:]).all() and not clustering.is_outlier(z)[-2:].any()


def test_evaluate_report_is_reproducible():
    x, labels = blobs()
    tablet = np.array([f"T{i}" for i in range(len(x))])
    position = np.arange(len(x))
    one = clustering.evaluate(tablet, position, labels, x, seed=1)
    assert one == clustering.evaluate(tablet, position, labels, x, seed=1)
    assert one["kmeans"]["purity"] == 1.0 and one["classes"] == 4


def png(fill="white", box=None) -> bytes:
    stream = BytesIO()
    image = Image.new("RGB", (30, 40), fill)
    if box:
        image.paste((0, 0, 0), box)
    image.save(stream, "PNG")
    return stream.getvalue()


def test_uploaded_crop_validation():
    ink = glyphembed.ink_from_png_bytes(png(box=(5, 5, 25, 20)))
    assert ink.shape == (40, 30) and ink[10, 10] and not ink[35, 2]
    assert glyphembed.prepared(ink).shape[2] == 3
    for bad in (b"not an image", b"\x89PNG\r\n\x1a\n" + b"0" * 10, b"x" * (glyphembed.MAX_CROP_BYTES + 1)):
        with pytest.raises(glyphembed.BadCrop):
            glyphembed.ink_from_png_bytes(bad)
    with pytest.raises(glyphembed.BadCrop):
        glyphembed.prepared(glyphembed.ink_from_png_bytes(png()))
