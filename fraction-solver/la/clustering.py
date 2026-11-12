"""Do glyph embeddings recover the sign inventory, and which labels look wrong?

Two clusterers run on the L2-normalised glyph embeddings (`la.glyphembed`, built
by `scripts/build_glyph_embeddings.py`): spherical K-means and DBSCAN. They are
scored against the SigLA sign IDs with purity and normalised mutual information
(NMI, arithmetic normalisation). No scikit-learn: both algorithms are a few lines
of numpy/scipy and every random choice takes a seed, so the numbers repeat.

The same embeddings also give the "possible mislabel" flag shown in the glyph pane:
a glyph is an outlier when its cosine distance to its own sign's centre is far
above that sign's typical distance (robust z-score, median/MAD). Read a flag as
"look again", not as "wrong": rare variants and damaged signs flag too.

    python -m la.clustering --embeddings ../models/glyph_embeddings.npz --json out.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

SEED = 0
MIN_CLASS = 5  # signs with fewer examples have no meaningful centre or spread
OUTLIER_Z = 5.0


def normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def centres(x: np.ndarray, labels: np.ndarray) -> dict[str, np.ndarray]:
    """Unit-length mean vector per label (x must be normalised)."""
    out = {}
    for label in np.unique(labels):
        mean = x[labels == label].mean(axis=0)
        out[str(label)] = mean / max(float(np.linalg.norm(mean)), 1e-12)
    return out


def outlier_scores(x: np.ndarray, labels: np.ndarray, min_class: int = MIN_CLASS) -> tuple[np.ndarray, np.ndarray]:
    """(distance, z): cosine distance to the own-sign centre and its robust z within the sign.

    z is NaN for signs with fewer than `min_class` examples.
    """
    distance = np.full(len(x), np.nan)
    z = np.full(len(x), np.nan)
    for label in np.unique(labels):
        rows = np.flatnonzero(labels == label)
        mean = x[rows].mean(axis=0)
        mean /= max(float(np.linalg.norm(mean)), 1e-12)
        d = 1.0 - x[rows] @ mean
        distance[rows] = d
        if len(rows) >= min_class:
            median = np.median(d)
            mad = max(1.4826 * np.median(np.abs(d - median)), 1e-4)
            z[rows] = (d - median) / mad
    return distance, z


def is_outlier(z: np.ndarray, threshold: float = OUTLIER_Z) -> np.ndarray:
    return np.nan_to_num(z, nan=-np.inf) > threshold


def kmeans(x: np.ndarray, k: int, seed: int = SEED, restarts: int = 3, iterations: int = 50) -> np.ndarray:
    """Spherical K-means with k-means++ seeding; the best of `restarts` runs by inertia."""
    rng = np.random.default_rng(seed)
    best, best_cost = None, np.inf
    for _ in range(restarts):
        centre = x[[rng.integers(len(x))]]
        for _ in range(1, k):
            d = np.maximum(1.0 - (x @ centre.T).max(axis=1), 0)
            centre = np.vstack([centre, x[rng.choice(len(x), p=d / d.sum())]])
        assign = None
        for _ in range(iterations):
            new = (x @ centre.T).argmax(axis=1)
            if assign is not None and np.array_equal(new, assign):
                break
            assign = new
            for j in range(k):
                members = x[assign == j]
                if len(members):
                    mean = members.mean(axis=0)
                    centre[j] = mean / max(float(np.linalg.norm(mean)), 1e-12)
        cost = float((1.0 - (x * centre[assign]).sum(axis=1)).sum())
        if cost < best_cost:
            best, best_cost = assign, cost
    return best


def dbscan(x: np.ndarray, eps: float, min_samples: int = 5) -> np.ndarray:
    """DBSCAN on Euclidean distance between unit vectors; noise is -1."""
    neighbours = cKDTree(x).query_ball_point(x, eps)
    core = np.array([len(n) >= min_samples for n in neighbours])
    labels = np.full(len(x), -1)
    current = 0
    for start in range(len(x)):
        if labels[start] != -1 or not core[start]:
            continue
        labels[start] = current
        stack = [start]
        while stack:
            for other in neighbours[stack.pop()]:
                if labels[other] == -1:
                    labels[other] = current
                    if core[other]:
                        stack.append(other)
        current += 1
    return labels


def purity(clusters: np.ndarray, labels: np.ndarray) -> float:
    """Share of points whose cluster's most common sign is their own sign."""
    total = 0
    for cluster in np.unique(clusters):
        total += Counter(labels[clusters == cluster].tolist()).most_common(1)[0][1]
    return total / len(labels)


def nmi(clusters: np.ndarray, labels: np.ndarray) -> float:
    """Normalised mutual information, I(C;L) / mean(H(C), H(L))."""
    n = len(labels)
    _, c = np.unique(clusters, return_inverse=True)
    _, y = np.unique(labels, return_inverse=True)
    table = np.zeros((c.max() + 1, y.max() + 1))
    np.add.at(table, (c, y), 1)
    p = table / n
    pc, py = p.sum(axis=1), p.sum(axis=0)
    nz = p > 0
    mutual = float((p[nz] * np.log(p[nz] / np.outer(pc, py)[nz])).sum())
    hc = float(-(pc[pc > 0] * np.log(pc[pc > 0])).sum())
    hy = float(-(py[py > 0] * np.log(py[py > 0])).sum())
    return mutual / ((hc + hy) / 2) if hc + hy > 0 else 1.0


def evaluate(tablet, position, sign, vectors, min_class: int = MIN_CLASS, seed: int = SEED,
             eps_grid: tuple[float, ...] = (0.2, 0.25, 0.3, 0.35, 0.4, 0.5)) -> dict:
    """Cluster the signs that have at least `min_class` examples and list suspected mislabels."""
    sign = np.asarray(sign)
    x_all = normalise(np.asarray(vectors, dtype=np.float64))
    counts = Counter(sign.tolist())
    keep = np.array([counts[s] >= min_class for s in sign.tolist()])
    x, labels = x_all[keep], sign[keep]
    k = len(np.unique(labels))
    report = {
        "samples": int(len(x)), "classes": k, "min_class": min_class, "seed": seed,
        "all_samples": int(len(x_all)), "all_classes": len(counts),
    }
    km = kmeans(x, k, seed)
    report["kmeans"] = {"k": k, "purity": round(purity(km, labels), 4), "nmi": round(nmi(km, labels), 4)}
    rows = []
    for eps in eps_grid:
        found = dbscan(x, eps, 5)
        clustered = found >= 0
        rows.append({
            "eps": eps, "clusters": int(found.max() + 1), "noise": round(float((~clustered).mean()), 4),
            "purity_clustered": round(purity(found[clustered], labels[clustered]), 4) if clustered.any() else None,
            "nmi_noise_as_cluster": round(nmi(found, labels), 4),
        })
    report["dbscan"] = {"min_samples": 5, "rows": rows}

    distance, z = outlier_scores(x_all, sign, min_class)
    own = centres(x_all, sign)
    names = [n for n in own if counts[n] >= min_class]
    matrix = np.stack([own[n] for n in names])
    flagged = np.flatnonzero(is_outlier(z))
    suspects = []
    for i in flagged[np.argsort(-z[flagged])]:
        nearest = names[int((matrix @ x_all[i]).argmax())]
        suspects.append({
            "tablet": str(tablet[i]), "position": int(position[i]), "labelled": str(sign[i]),
            "z": round(float(z[i]), 2), "cosine_distance": round(float(distance[i]), 4),
            "nearest_centre": nearest, "nearest_is_other_sign": nearest != str(sign[i]),
        })
    report["mislabels"] = {
        "z_threshold": OUTLIER_Z, "flagged": len(suspects), "of": int(np.isfinite(z).sum()),
        "nearest_centre_differs": sum(s["nearest_is_other_sign"] for s in suspects),
        "top": suspects[:25],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    data = np.load(args.embeddings)
    report = evaluate(data["tablet"], data["position"], data["sign"], data["vectors"], seed=args.seed)
    report["model"] = str(data["model"])
    report["weights_sha256"] = str(data["weights_sha256"])
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
