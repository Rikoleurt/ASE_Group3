"""Score a Linear A sign reader on the held-out tablets.

    python evaluate.py --detector runs/detect/signs/weights/best.pt \
        --classifier runs/classify/signs/weights/best.pt --name two-stage

The detector alone is scored if no classifier is given; a 361-class identity
detector then names signs itself, so it can be compared with the two-stage
reader on the same tablets. Ground truth is the dataset's `annotations.json`,
whatever label mode it was built in. Results go to `runs/eval/<name>.json`.
See `fraction-solver/la/evaluation.py` for what each rate means.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "fraction-solver"))

from la import evaluation, reader  # noqa: E402
from la.shapes import load_mask  # noqa: E402
from la.signboxes import DATASET_DIR  # noqa: E402
from la.signcrops import identified, sign_id  # noqa: E402

RATE_LABELS = {
    "precision": "Detection precision",
    "recall": "Detection recall",
    "read_top1": "Signs read correctly (top-1)",
    "read_top3": "Sign in top 3",
    "read_top1_learnable": "Read correctly, signs seen in training",
    "named_given_found": "Named correctly when found",
}


def sign_of_class(name: str) -> str | None:
    """The sign ID in an identity detector's class name, e.g. 'AB77' from 'AB77 (ka)'."""
    return None if name in ("sign", "syllabogram", "logogram", "fraction", "transaction") else name.split(" ")[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--detector", required=True, type=Path)
    parser.add_argument("--classifier", type=Path)
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--split", default="test", choices=["val", "test"])
    parser.add_argument("--conf", type=float, default=0.25, help="detection threshold (the demo uses 0.25)")
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--device", default=None)
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--name", default=None, help="output name (default: detector run name)")
    args = parser.parse_args()

    from ultralytics import YOLO

    annotations = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))
    learnable = {sign_id(s) for t in annotations if t["split"] == "train" for s in identified(t)}
    detector = YOLO(str(args.detector))
    classifier = YOLO(str(args.classifier)) if args.classifier else None

    scores, started = [], time.time()
    for tablet in (t for t in annotations if t["split"] == args.split):
        image = args.dataset / tablet["image"]
        result = detector.predict(str(image), imgsz=args.imgsz, conf=args.conf, device=args.device, verbose=False)[0]
        boxes = [tuple(b) for b in result.boxes.xyxy.tolist()]
        confidences = result.boxes.conf.tolist()
        if classifier is not None:
            labels = [[name for name, _ in top] for top in
                      reader.name_boxes(classifier, load_mask(image), boxes, device=args.device)]
        else:
            labels = [[s] if (s := sign_of_class(result.names[int(c)])) else [] for c in result.boxes.cls.tolist()]
        predictions = [evaluation.Prediction(b, c, l) for b, c, l in zip(boxes, confidences, labels)]
        truths = [evaluation.Truth(tuple(s["xyxy"]),
                                   sign_id(s) if s.get("source", "matched") == "matched" else None,
                                   sign_id(s) in learnable) for s in tablet["signs"]]
        scores.append(evaluation.score_tablet(tablet["tablet"], predictions, truths))

    result = evaluation.report(scores, resamples=args.resamples)
    result.update({"detector": str(args.detector), "classifier": str(args.classifier) if args.classifier else None,
                   "dataset": str(args.dataset), "split": args.split, "conf": args.conf, "imgsz": args.imgsz,
                   "seconds": round(time.time() - started, 1),
                   "per_tablet": [vars(s) for s in scores]})
    name = args.name or args.detector.parent.parent.name
    out = ROOT / "runs" / "eval" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    t = result["totals"]
    print(f"{name}: {result['tablets']} {args.split} tablets, {t['truths']} labelled signs, "
          f"{t['predictions']} predictions")
    for key, label in RATE_LABELS.items():
        lo, hi = result["ci95"][key]
        print(f"  {label:<40} {result['rates'][key]:6.1%}   (95% CI {lo:.1%} - {hi:.1%})")
    print(f"Written to {out}")


if __name__ == "__main__":
    main()
