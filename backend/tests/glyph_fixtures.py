"""A tiny synthetic corpus for the glyph tests: no dataset files are needed."""
import numpy as np

from backend.app.glyph_index import GlyphIndex

DOCS = {
    "HT 1": {"url": "https://lineara.eu/documents/HT-1/", "signs": [
        {"position": 1, "sign": "AB77", "reading": "ka", "role": "syllabogram", "image": "x/1.png"},
        {"position": 2, "sign": "AB01", "reading": "da", "role": "syllabogram", "image": "x/2.png"}]},
    "HT 2": {"url": "https://lineara.eu/documents/HT-2/", "signs": [
        {"position": 1, "sign": "AB77", "reading": "ka", "role": "syllabogram", "image": "x/3.png"},
        {"position": 4, "sign": "AB77", "reading": "ka", "role": "syllabogram"}]},
    "KN Zb 5": {"url": "https://lineara.eu/documents/KN-Zb-5/", "signs": [
        {"position": 3, "sign": "AB77", "reading": "ka", "role": "syllabogram", "image": "x/4.png"},
        {"position": 9, "sign": "AB77", "reading": "ka", "role": "syllabogram", "image": "x/5.png"},
        {"position": 10, "sign": "AB77", "reading": "ka", "role": "syllabogram", "image": "x/6.png"},
        {"position": 11, "sign": "AB77", "reading": "ka", "role": "syllabogram", "image": "x/7.png"}]},
    "Odd": {"url": "https://lineara.eu/documents/a b/", "signs": [{"position": 1, "sign": "AB77"}]},
}
ANNOTATIONS = [{"tablet": "HT 1", "width": 1000, "height": 500,
                "signs": [{"position": 1, "xyxy": [100, 50, 200, 150]}]}]


def embeddings(far_from_centre: tuple[str, int] = ("KN Zb 5", 11)) -> dict:
    """AB77 glyphs lie near one direction; the chosen one points elsewhere (a possible mislabel)."""
    rng = np.random.default_rng(0)
    rows = [("HT 1", 1, "AB77"), ("HT 2", 1, "AB77"), ("KN Zb 5", 3, "AB77"), ("KN Zb 5", 9, "AB77"),
            ("KN Zb 5", 10, "AB77"), ("KN Zb 5", 11, "AB77"), ("HT 1", 2, "AB01")]
    vectors = []
    for tablet, position, sign in rows:
        if (tablet, position) == far_from_centre:
            vectors.append([0.0, 1.0, 0.0, 0.0])
        elif sign == "AB77":
            vectors.append(np.array([1.0, 0.0, 0.0, 0.0]) + rng.normal(0, 0.02, 4) + [0, 0.05 * position / 10, 0, 0])
        else:
            vectors.append([0.0, 0.0, 1.0, 0.0])
    return {"tablet": np.array([r[0] for r in rows]), "position": np.array([r[1] for r in rows]),
            "sign": np.array([r[2] for r in rows]), "vectors": np.array(vectors, dtype=np.float32),
            "model": np.array("yolo-cls"), "weights_sha256": np.array("0" * 64)}


def index(with_embeddings: bool = True) -> GlyphIndex:
    return GlyphIndex(DOCS, ANNOTATIONS, embeddings() if with_embeddings else None)
