"""Sign bounding boxes for the tablet tracings, as a YOLO detection dataset.

The web demo runs a generic YOLO model over HT 13 and finds nothing, because no
model has ever seen a Linear A sign. Training one needs boxes around every sign
on a tablet, and drawing those by hand is the step nobody has time for.

lineara.eu already holds what the boxes are made from. Each document's data.json
(cached by `la.fetch`) links a tracing of the whole tablet and, for every sign, a
crop of that sign with its SigLA id and role. The crops are cut from the full-size
drawing, so locating each crop on its tracing *is* the box. Nothing is drawn.

One trap: tracings are served at most 1440 px wide, but the crops keep the
original resolution. HT 13 (1367 px) is never shrunk, so its crops land pixel for
pixel; most tablets are, and matching them at scale 1 fails on every sign. The
scale is one number per tablet, so it is estimated once from the largest crops
and then applied to all of them.

A second trap, in scoring: counting only how much crop ink lands on tracing ink
rewards tiny scales, because a shrunken crop dropped on dense ink always lands on
something. Position and scale are therefore chosen by cosine similarity, which
also penalises ink in the window that the crop does not have.

Every box is still checked, not assumed: a crop whose ink does not mostly land
on tracing ink at the chosen position is rejected and reported, never placed at
its best-but-wrong position.

Data licence: the tracings and crops are SigLA-derived and CC BY-NC-SA 4.0, like
the cached JSON, and are used non-commercially with attribution. The image cache
is committed with the project; the dataset under `out/` is rebuilt on demand.
"""

from __future__ import annotations

import json
import time
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import fft

from la import fetch
from la.shapes import load_mask

IMAGE_DIR = fetch.ROOT / "data" / "images"
DATASET_DIR = fetch.ROOT / "out" / "yolo_signs"

# The web demo shows HT 13. Training on it would make the demo report what the
# model memorised, so it is never written to either split.
DEMO_HOLDOUT = frozenset({"HT 13"})

# Fraction of a crop's ink that must land on tracing ink at the chosen position.
# Unscaled cut-outs score 1.0 and rescaled ones 0.9-0.97 (resampling blurs the
# strokes); a crop at the wrong position or scale typically scores 0.2-0.6.
MIN_MATCH = 0.85

# Tracings are shrunk to at most 1440 px wide, so a tablet's scale is in (0, 1].
# The search covers 0.2-1.0 at quarter resolution, then refines at full size.
SCALE_RANGE = (0.20, 1.00)
COARSE_STEP = 0.02
COARSE_RESOLUTION = 0.25
FINE_STEP = 0.005
FINE_SPAN = 0.02
# Shrunk far enough, any crop becomes a dot that matches any ink perfectly. Real
# signs are 90-300 px, so no true scale takes a crop below this.
MIN_SIGN_PX = 16

# Erasures are marks, not signs: a detector should not learn to box them.
EXCLUDED_ROLES = frozenset({"erasure"})
ROLE_CLASSES = ("syllabogram", "logogram", "fraction", "transaction")

LICENCE_NOTICE = """\
Images and labels derived from lineara.eu / SigLA tracings.
Licence: CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/).
Credit: sign drawings from SigLA: The Signs of Linear A, a palaeographical database,
by Ester Salgarella and Simon Castellan; lineara.eu by M. Navarre.
Non-commercial use only; keep this credit with any copy of the dataset or models trained on it.
"""


@dataclass
class SignBox:
    sign: str
    role: str
    position: int
    x0: int
    y0: int
    x1: int
    y1: int
    match: float


@dataclass
class TabletBoxes:
    doc_id: str
    width: int
    height: int
    tracing: np.ndarray                     # ink mask of the whole tablet
    scale: float                            # tracing size / original drawing size
    boxes: list[SignBox] = field(default_factory=list)
    rejected: list[tuple[int, str, float]] = field(default_factory=list)  # (position, sign, match)


def slug(doc: dict) -> str:
    """The lineara.eu document slug, e.g. 'HT-13' for 'HT 13'."""
    return doc["url"].rstrip("/").rsplit("/", 1)[-1]


def has_boxes(doc: dict) -> bool:
    return bool(doc.get("tracing")) and any(s.get("image") for s in doc.get("signs") or [])


def image_path(doc: dict, url: str) -> Path:
    # URL basenames carry a content hash, so they are unique and change if the image does.
    return IMAGE_DIR / slug(doc) / url.rsplit("/", 1)[-1]


def download_images(docs: dict[str, dict], delay: float = 0.4) -> fetch.FetchStats:
    """Fetch every tracing and sign crop into the image cache. Resumable, like `la.fetch`."""
    stats = fetch.FetchStats()
    usable = [d for d in docs.values() if has_boxes(d)]
    for i, doc in enumerate(usable, 1):
        urls = [doc["tracing"]] + [s["image"] for s in doc["signs"] if s.get("image")]
        for url in urls:
            path = image_path(doc, url)
            if path.exists():
                stats.cached += 1
                continue
            try:
                raw = fetch._get(url)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                stats.requested += 1
            except Exception as exc:  # noqa: BLE001 - record and continue
                stats.failed += 1
                print(f"  FAILED {doc['id']} {url}: {exc}")
            time.sleep(delay)
        if i % 50 == 0:
            print(f"  {i}/{len(usable)} tablets (new {stats.requested}, cached {stats.cached}, failed {stats.failed})")
    return stats


def resize_mask(mask: np.ndarray, scale: float, density: bool = False) -> np.ndarray:
    """A mask resampled by `scale`, as float32.

    `density=True` keeps the averaged ink fraction instead of re-thresholding;
    at quarter resolution, thresholding would erase strokes thinner than 4 px.
    """
    h, w = mask.shape
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    image = Image.fromarray(mask.astype(np.uint8) * 255)
    out = np.asarray(image.resize(size, Image.BOX if density else Image.LANCZOS), dtype=np.float32) / 255
    return out if density else (out >= 0.5).astype(np.float32)


class Correlator:
    """Matches many crops against one tracing, transforming the tracing once."""

    def __init__(self, tracing: np.ndarray) -> None:
        self.tracing = tracing.astype(np.float32)
        self.fft_shape = [fft.next_fast_len(n, real=True) for n in self.tracing.shape]
        self.spectrum = fft.rfft2(self.tracing, self.fft_shape)
        # Summed-area table of tracing ink, for the ink inside every window.
        self.integral = np.pad((self.tracing ** 2).cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    def locate(self, crop: np.ndarray) -> tuple[int, int, float, float]:
        """Where a crop sits on the tracing: (x, y, match, cosine).

        The position maximises cosine similarity between crop and window. `match`
        is the fraction of crop ink landing on tracing ink there, so 1.0 means
        every stroke lines up.
        """
        crop = crop.astype(np.float32)
        h, w = crop.shape
        height, width = self.tracing.shape
        energy = float((crop ** 2).sum())
        if energy == 0 or h > height or w > width:
            return 0, 0, 0.0, 0.0
        overlap = fft.irfft2(self.spectrum * np.conj(fft.rfft2(crop, self.fft_shape)), self.fft_shape)
        overlap = overlap[:height - h + 1, :width - w + 1]
        s = self.integral
        window = s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]
        cosine = overlap / np.sqrt(np.maximum(window, 1e-6) * energy)
        y, x = np.unravel_index(int(np.argmax(cosine)), cosine.shape)
        return int(x), int(y), float(overlap[y, x]) / float(crop.sum()), float(cosine[y, x])


def locate(tracing: np.ndarray, crop: np.ndarray) -> tuple[int, int, float]:
    """Where one crop's ink sits on the tracing at the same scale: (x, y, match)."""
    x, y, match, _ = Correlator(tracing).locate(crop)
    return x, y, match


def estimate_scale(tracing: np.ndarray, crops: list[np.ndarray], n: int = 3) -> float:
    """The factor by which the tracing was shrunk relative to its crops.

    Large crops carry the most shape, so only the `n` largest are used: a coarse
    pass over the whole range at quarter resolution, then a fine pass at full size.
    """
    sample = sorted(crops, key=lambda c: -int(c.sum()))[:n]
    if not sample:
        return 1.0

    def mean_cosine(correlator: Correlator, masks: list[np.ndarray]) -> float:
        return float(np.mean([correlator.locate(m)[3] for m in masks]))

    q = COARSE_RESOLUTION
    coarse = Correlator(resize_mask(tracing, q, density=True))
    lo, hi = SCALE_RANGE
    lo = max(lo, MIN_SIGN_PX / min(min(c.shape) for c in sample))
    if lo > hi:
        return 1.0
    candidates = np.arange(lo, hi + COARSE_STEP / 2, COARSE_STEP)
    best = max(candidates, key=lambda s: mean_cosine(coarse, [resize_mask(c, s * q, density=True) for c in sample]))

    full = Correlator(tracing)
    fine = np.arange(max(lo, best - FINE_SPAN), min(hi, best + FINE_SPAN) + FINE_STEP / 2, FINE_STEP)
    best = max(fine, key=lambda s: mean_cosine(full, [resize_mask(c, s) for c in sample[:2]]))
    return round(float(best), 3)


def ink_bounds(mask: np.ndarray) -> tuple[int, int, int, int]:
    """Tight (x0, y0, x1, y1) around the ink, exclusive of x1 and y1."""
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def tablet_boxes(doc: dict, min_match: float = MIN_MATCH) -> TabletBoxes | None:
    """Every sign box on one tablet, from the cached tracing and crops."""
    tracing_path = image_path(doc, doc["tracing"])
    if not tracing_path.exists():
        return None
    tracing = load_mask(tracing_path)
    signs = [s for s in doc.get("signs") or []
             if s.get("image") and s.get("role") not in EXCLUDED_ROLES and image_path(doc, s["image"]).exists()]
    crops = [load_mask(image_path(doc, s["image"])) for s in signs]
    scale = estimate_scale(tracing, crops)
    result = TabletBoxes(doc_id=doc["id"], width=tracing.shape[1], height=tracing.shape[0],
                         tracing=tracing, scale=scale)

    correlator = Correlator(tracing)
    for s, crop in zip(signs, crops):
        if scale != 1.0:
            crop = resize_mask(crop, scale) > 0
        x, y, match, _ = correlator.locate(crop)
        if match < min_match or not crop.any():
            result.rejected.append((s["position"], s.get("sign", ""), match))
            continue
        cx0, cy0, cx1, cy1 = ink_bounds(crop)
        result.boxes.append(SignBox(
            sign=s.get("sign", ""), role=s.get("role", ""), position=s["position"],
            x0=x + cx0, y0=y + cy0, x1=x + cx1, y1=y + cy1, match=match,
        ))
    return result


def yolo_line(cls: int, box: SignBox, width: int, height: int) -> str:
    """One YOLO label row: class, then centre and size as fractions of the image."""
    cx = (box.x0 + box.x1) / 2 / width
    cy = (box.y0 + box.y1) / 2 / height
    w = (box.x1 - box.x0) / width
    h = (box.y1 - box.y0) / height
    return f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def split_for(doc_id: str, val_fraction: float) -> str:
    """Deterministic per-tablet split, so a rebuild puts every tablet where it was."""
    return "val" if zlib.crc32(doc_id.encode("utf-8")) % 1000 < val_fraction * 1000 else "train"


def class_names(labels: str) -> tuple[str, ...]:
    if labels == "sign":
        return ("sign",)
    if labels == "role":
        return ROLE_CLASSES
    raise ValueError(f"unknown label mode {labels!r}")


def class_of(box: SignBox, labels: str) -> int | None:
    if labels == "sign":
        return 0
    return ROLE_CLASSES.index(box.role) if box.role in ROLE_CLASSES else None


def _tablet_boxes_for(args: tuple[dict, float, Path]) -> TabletBoxes | None:
    # Worker processes start fresh, so the (possibly redirected) cache path travels with the job.
    global IMAGE_DIR
    doc, min_match, IMAGE_DIR = args
    return tablet_boxes(doc, min_match=min_match)


def build_dataset(
    docs: dict[str, dict],
    out: Path = DATASET_DIR,
    labels: str = "sign",
    val_fraction: float = 0.15,
    holdout: frozenset[str] = DEMO_HOLDOUT,
    min_match: float = MIN_MATCH,
    workers: int = 4,
) -> dict:
    """Write images, labels and data.yaml in the layout Ultralytics expects.

    Images are re-rendered as black ink on white from the ink mask, so tracings
    stored with strokes in the alpha channel look the same as opaque ones; OpenCV,
    which Ultralytics reads with, would otherwise drop the alpha and see black.

    Tablets are matched in parallel; `workers=1` runs in-process. Each worker holds
    a full-size tracing and its FFT, and 12 workers exhausted a 16 GB machine, so
    the default is a conservative 4 (about 10 minutes for the corpus).
    """
    names = class_names(labels)
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    report: dict = {"tablets": Counter(), "boxes": Counter(), "rejected": [], "skipped_no_boxes": [],
                    "held_out": sorted(holdout), "classes": Counter(), "scales": {}}
    jobs = [(doc, min_match, IMAGE_DIR) for doc in docs.values() if doc["id"] not in holdout and has_boxes(doc)]
    with ExitStack() as stack:
        if workers == 1:
            tablets = map(_tablet_boxes_for, jobs)
        else:
            pool = stack.enter_context(ProcessPoolExecutor(max_workers=workers))
            tablets = pool.map(_tablet_boxes_for, jobs, chunksize=4)
        _write_tablets(zip(jobs, tablets), len(jobs), out, labels, names, val_fraction, report)

    (out / "data.yaml").write_text(
        f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\n"
        f"names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(names)),
        encoding="utf-8",
    )
    (out / "LICENCE.txt").write_text(LICENCE_NOTICE, encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _write_tablets(results, total: int, out: Path, labels: str, names: tuple[str, ...],
                   val_fraction: float, report: dict) -> None:
    for done, ((doc, _, _), tablet) in enumerate(results, 1):
        if done % 50 == 0:
            print(f"  {done}/{total} tablets matched")
        if done % 50 == 0:
            print(f"  {done}/{total} tablets matched")
        if tablet is None:
            continue
        report["scales"][doc["id"]] = tablet.scale
        report["rejected"] += [(doc["id"], pos, sign, round(m, 3)) for pos, sign, m in tablet.rejected]
        rows = [(class_of(b, labels), b) for b in tablet.boxes]
        rows = [(c, b) for c, b in rows if c is not None]
        if not rows:
            report["skipped_no_boxes"].append(doc["id"])
            continue

        split = split_for(doc["id"], val_fraction)
        stem = slug(doc)
        Image.fromarray(np.where(tablet.tracing, 0, 255).astype(np.uint8)).save(out / "images" / split / f"{stem}.png")
        (out / "labels" / split / f"{stem}.txt").write_text(
            "\n".join(yolo_line(c, b, tablet.width, tablet.height) for c, b in rows) + "\n", encoding="utf-8")
        report["tablets"][split] += 1
        report["boxes"][split] += len(rows)
        report["classes"].update(names[c] for c, _ in rows)
