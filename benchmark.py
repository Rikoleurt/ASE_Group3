"""Benchmark candidate models for reading Linear A signs on the same data.

Two jobs are benchmarked, each over the same dataset split and the same training
recipe (`train.py`), so only the model changes:

    python benchmark.py detect      # one-class "sign" detectors, scored on the test tablets
    python benchmark.py classify    # sign classifiers, scored on the test crops
    python benchmark.py end2end     # best detector x every classifier, via evaluate.py
    python benchmark.py report      # results.csv and charts from the saved results

Data first, from the repository root (see fraction-solver/README.md):

    la.cli dataset --labels sign && la.cli synth     # detector data
    la.cli crops                                      # classifier data

Every result is written to `runs/benchmark/<stage>/<model>.json`; `report` reads
those, so runs can be spread over several sessions (e.g. on Colab) and merged.
`--quick` trains for a few epochs to check the pipeline; its numbers mean nothing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "runs" / "benchmark"

# Same family sizes where they exist, so size and generation are not confounded.
DETECTORS = ["yolo26n.pt", "yolo26s.pt", "yolo11n.pt", "yolo11s.pt", "yolov8n.pt"]
OPTIONAL_DETECTORS = ["rtdetr-l.pt"]  # needs >16 GB of GPU memory at 1024 px; run it on a bigger GPU (Colab)
# YOLO classifiers (Ultralytics) and ImageNet-pretrained torchvision networks ("tv-" prefix).
CLASSIFIERS = ["yolo26n-cls.pt", "yolo26s-cls.pt", "yolo11n-cls.pt", "yolo11s-cls.pt", "yolov8n-cls.pt",
               "tv-resnet18", "tv-resnet50", "tv-efficientnet_b0", "tv-mobilenet_v3_large", "tv-convnext_tiny"]

QUICK_EPOCHS = 3


def stem(weights: str) -> str:
    return Path(weights).stem


def save(stage: str, name: str, result: dict) -> Path:
    path = OUT / stage / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def load(stage: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT / stage).glob("*.json"))]


def train_args(args: argparse.Namespace, weights: str) -> argparse.Namespace:
    """The arguments `train.py` expects, with one run per model under runs/benchmark."""
    return argparse.Namespace(
        data=args.data, model=weights, epochs=QUICK_EPOCHS if args.quick else args.epochs,
        batch=args.batch, seed=args.seed, workers=args.workers, name=f"bench_{stem(weights)}",
    )


def detect(args: argparse.Namespace) -> None:
    import train
    from ultralytics import RTDETR, YOLO

    for weights in args.models or DETECTORS:
        name = stem(weights)
        if (OUT / "detect" / f"{name}.json").exists() and not args.force:
            print(f"skip {name}: already benchmarked (use --force)")
            continue
        started = time.time()
        train.detect(train_args(args, weights))
        train_seconds = time.time() - started
        run = ROOT / "runs" / "detect" / f"bench_{name}"
        best = (RTDETR if "rtdetr" in name else YOLO)(str(run / "weights" / "best.pt"))
        data = args.data or train.DATA / "yolo_signs" / "data.yaml"
        metrics = best.val(data=str(data), split="test", imgsz=1024, conf=0.001, plots=False, verbose=False)
        # Latency at the demo's operating point, one tablet at a time.
        images = sorted((Path(data).parent / "images" / "test").glob("*"))[:20]
        best.predict(str(images[0]), imgsz=1024, verbose=False)  # warm-up
        t = time.time()
        for image in images:
            best.predict(str(image), imgsz=1024, conf=0.25, verbose=False)
        ms = (time.time() - t) / max(len(images), 1) * 1000
        path = save("detect", name, {
            "model": name, "params_m": round(sum(p.numel() for p in best.model.parameters()) / 1e6, 2),
            "precision": float(metrics.box.mp), "recall": float(metrics.box.mr),
            "map50": float(metrics.box.map50), "map50_95": float(metrics.box.map),
            "train_minutes": round(train_seconds / 60, 1), "ms_per_tablet": round(ms, 1),
            "epochs": QUICK_EPOCHS if args.quick else args.epochs or 150, "seed": args.seed,
            "weights": str(run / "weights" / "best.pt"), "quick": args.quick,
        })
        print(f"{name}: mAP50 {metrics.box.map50:.3f}, mAP50-95 {metrics.box.map:.3f} -> {path}")


def train_torchvision(args: argparse.Namespace, arch: str, data: Path) -> dict:
    """Fine-tune an ImageNet-pretrained torchvision classifier on the crop folders.

    Mirrors the Ultralytics recipe in train.classify: 128 px, no flips (orientation is
    part of a sign's identity), gentle 90-100% crops, patience 25 on validation top-1.
    """
    import torch
    import torchvision
    from torchvision import transforms as T

    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    norm = T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    base = [T.Grayscale(3), T.Resize((128, 128)), T.ToTensor(), norm]
    train_tf = T.Compose([T.Grayscale(3), T.RandomResizedCrop(128, scale=(0.9, 1.0), ratio=(0.95, 1.05)),
                          T.ColorJitter(brightness=0.2), T.ToTensor(), norm, T.RandomErasing(p=0.1)])
    sets = {s: torchvision.datasets.ImageFolder(data / s, train_tf if s == "train" else T.Compose(base))
            for s in ("train", "val", "test")}
    classes = sets["train"].classes

    def loader(split, shuffle):
        ds = sets[split]
        if split != "train":  # val/test hold a subset of the classes: index by the train classes
            ds.samples = [(p, classes.index(ds.classes[c])) for p, c in ds.samples]
        return torch.utils.data.DataLoader(ds, batch_size=args.batch or 64, shuffle=shuffle,
                                           num_workers=args.workers, drop_last=shuffle)

    loaders = {"train": loader("train", True), "val": loader("val", False), "test": loader("test", False)}
    model = getattr(torchvision.models, arch)(weights="DEFAULT")
    head = {"resnet": "fc", "efficientnet": "classifier", "mobilenet": "classifier", "convnext": "classifier"}
    kind = next(k for k in head if arch.startswith(k))
    layer = getattr(model, head[kind])
    if isinstance(layer, torch.nn.Sequential):
        layer[-1] = torch.nn.Linear(layer[-1].in_features, len(classes))
    else:
        setattr(model, head[kind], torch.nn.Linear(layer.in_features, len(classes)))
    model.to(device)

    epochs = QUICK_EPOCHS if args.quick else args.epochs or 100
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)

    def evaluate(split):
        model.eval()
        top1 = top5 = n = 0
        with torch.no_grad():
            for x, y in loaders[split]:
                top = model(x.to(device)).topk(min(5, len(classes)), dim=1).indices.cpu()
                top1 += (top[:, 0] == y).sum().item()
                top5 += (top == y[:, None]).any(dim=1).sum().item()
                n += len(y)
        return top1 / max(n, 1), top5 / max(n, 1)

    run = ROOT / "runs" / "classify" / f"bench_tv-{arch}" / "weights"
    run.mkdir(parents=True, exist_ok=True)
    best, stale = -1.0, 0
    for epoch in range(epochs):
        model.train()
        for x, y in loaders["train"]:
            optimizer.zero_grad()
            torch.nn.functional.cross_entropy(model(x.to(device)), y.to(device)).backward()
            optimizer.step()
        schedule.step()
        val = evaluate("val")[0]
        if val > best:
            best, stale = val, 0
            torch.save({"arch": arch, "classes": classes, "state": model.state_dict()}, run / "best.pt")
        else:
            stale += 1
            if stale >= 25:
                break
    model.load_state_dict(torch.load(run / "best.pt")["state"])
    top1, top5 = evaluate("test")
    model.eval()
    sample = next(iter(loaders["test"]))[0][:1].to(device)
    with torch.no_grad():
        model(sample)
        if device == "cuda":
            torch.cuda.synchronize()
        t = time.time()
        for _ in range(100):
            model(sample)
        if device == "cuda":
            torch.cuda.synchronize()
    return {"top1": top1, "top5": top5, "ms_per_crop": round((time.time() - t) * 10, 2),
            "params_m": round(sum(p.numel() for p in model.parameters()) / 1e6, 2),
            "weights": str(run / "best.pt"), "epochs_run": epoch + 1}


class TorchvisionClassifier:
    """A saved torchvision classifier behind the `predict(crops)` interface la.reader expects."""

    def __init__(self, path: str, device: str | None = None) -> None:
        import torch
        import torchvision

        ckpt = torch.load(path, map_location="cpu")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.names = dict(enumerate(ckpt["classes"]))
        model = getattr(torchvision.models, ckpt["arch"])(weights=None)
        kind = next(k for k in ("resnet", "efficientnet", "mobilenet", "convnext") if ckpt["arch"].startswith(k))
        attr = "fc" if kind == "resnet" else "classifier"
        layer = getattr(model, attr)
        if isinstance(layer, torch.nn.Sequential):
            layer[-1] = torch.nn.Linear(layer[-1].in_features, len(self.names))
        else:
            setattr(model, attr, torch.nn.Linear(layer.in_features, len(self.names)))
        model.load_state_dict(ckpt["state"])
        self.model = model.to(self.device).eval()

    def predict(self, crops, device=None, verbose=False):
        import numpy as np
        import torch
        from PIL import Image

        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        x = torch.stack([torch.from_numpy(np.asarray(Image.fromarray(c).resize((128, 128)))).permute(2, 0, 1)
                         for c in crops]).float() / 255
        with torch.no_grad():
            probs = self.model(((x - mean) / std).to(self.device)).softmax(dim=1).cpu()
        return [type("Result", (), {"names": self.names, "probs": type("Probs", (), {"data": p})})() for p in probs]


def load_classifier(path: Path):
    """An Ultralytics or torchvision classifier, whichever `path` holds."""
    if path.parent.parent.name.startswith("bench_tv-"):
        return TorchvisionClassifier(str(path))
    from ultralytics import YOLO

    return YOLO(str(path))


def classify(args: argparse.Namespace) -> None:
    import train
    from ultralytics import YOLO

    for weights in args.models or CLASSIFIERS:
        name = stem(weights)
        if (OUT / "classify" / f"{name}.json").exists() and not args.force:
            print(f"skip {name}: already benchmarked (use --force)")
            continue
        if name.startswith("tv-"):
            started = time.time()
            r = train_torchvision(args, name[3:], args.data or train.DATA / "sign_crops")
            path = save("classify", name, {"model": name, "train_minutes": round((time.time() - started) / 60, 1),
                                           "epochs": QUICK_EPOCHS if args.quick else args.epochs or 100,
                                           "seed": args.seed, "quick": args.quick, **r})
            print(f"{name}: top-1 {r['top1']:.3f}, top-5 {r['top5']:.3f} -> {path}")
            continue
        started = time.time()
        train.classify(train_args(args, weights))
        train_seconds = time.time() - started
        run = ROOT / "runs" / "classify" / f"bench_{name}"
        best = YOLO(str(run / "weights" / "best.pt"))
        data = args.data or train.DATA / "sign_crops"
        metrics = best.val(data=str(data), split="test", imgsz=128, plots=False, verbose=False)
        crops = sorted((Path(data) / "test").rglob("*.png"))[:200]
        best.predict(str(crops[0]), imgsz=128, verbose=False)  # warm-up
        t = time.time()
        for crop in crops:
            best.predict(str(crop), imgsz=128, verbose=False)
        ms = (time.time() - t) / max(len(crops), 1) * 1000
        path = save("classify", name, {
            "model": name, "params_m": round(sum(p.numel() for p in best.model.parameters()) / 1e6, 2),
            "top1": float(metrics.top1), "top5": float(metrics.top5),
            "train_minutes": round(train_seconds / 60, 1), "ms_per_crop": round(ms, 1),
            "epochs": QUICK_EPOCHS if args.quick else args.epochs or 100, "seed": args.seed,
            "weights": str(run / "weights" / "best.pt"), "quick": args.quick,
        })
        print(f"{name}: top-1 {metrics.top1:.3f}, top-5 {metrics.top5:.3f} -> {path}")


def end2end(args: argparse.Namespace) -> None:
    """Whole-tablet reading: the best detector with each classifier, scored by evaluate.py."""
    detectors = load("detect")
    if not detectors:
        sys.exit("Run `benchmark.py detect` first.")
    best = max(detectors, key=lambda r: r["map50_95"])
    print(f"Detector held fixed: {best['model']} (best mAP50-95 {best['map50_95']:.3f})")
    for entry in load("classify"):
        name = f"{best['model']}+{entry['model']}"
        subprocess.run([sys.executable, str(ROOT / "evaluate.py"), "--detector", best["weights"],
                        "--classifier", entry["weights"], "--name", f"bench_{name}"], check=True)
        result = json.loads((ROOT / "runs" / "eval" / f"bench_{name}.json").read_text(encoding="utf-8"))
        save("end2end", name, {"pipeline": name, "detector": best["model"], "classifier": entry["model"],
                               "rates": result["rates"], "ci95": result["ci95"], "seconds": result["seconds"]})


def report(args: argparse.Namespace) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OUT.mkdir(parents=True, exist_ok=True)
    stages = {
        "detect": ("Detectors (test tablets)", [("map50_95", "mAP50-95"), ("map50", "mAP50"),
                                                ("recall", "Recall"), ("precision", "Precision")], "ms_per_tablet"),
        "classify": ("Classifiers (test crops)", [("top1", "Top-1"), ("top5", "Top-5")], "ms_per_crop"),
    }
    lines = []
    for stage, (title, metrics, latency) in stages.items():
        rows = load(stage)
        if not rows:
            continue
        key = metrics[0][0]
        rows.sort(key=lambda r: -r[key])
        keys = ["model", "params_m", *[m for m, _ in metrics], latency, "train_minutes"]
        lines += [f"# {title}", ",".join(keys), *[",".join(str(r[k]) for k in keys) for r in rows], ""]
        fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [3, 2]})
        width = 0.8 / len(metrics)
        for i, (m, label) in enumerate(metrics):
            ax.bar([x + i * width for x in range(len(rows))], [r[m] for r in rows], width, label=label)
        ax.set_xticks([x + width * (len(metrics) - 1) / 2 for x in range(len(rows))])
        ax.set_xticklabels([r["model"] for r in rows], rotation=25, ha="right")
        ax.set_ylim(0, 1)
        ax.set_title(title)
        ax.legend()
        ax2.scatter([r[latency] for r in rows], [r[key] for r in rows], s=[40 + r["params_m"] * 12 for r in rows])
        for r in rows:
            ax2.annotate(r["model"], (r[latency], r[key]), textcoords="offset points", xytext=(5, 5), fontsize=8)
        ax2.set_xlabel(latency.replace("_", " "))
        ax2.set_ylabel(metrics[0][1])
        ax2.set_title("Accuracy vs speed (bubble = parameters)")
        fig.tight_layout()
        fig.savefig(OUT / f"{stage}.png", dpi=150)
        plt.close(fig)
    rows = load("end2end")
    if rows:
        rows.sort(key=lambda r: -r["rates"]["read_top1"])
        lines += ["# End to end (whole tablets, detector held fixed)", "pipeline,read_top1,read_top3,recall,precision",
                  *[f"{r['pipeline']},{r['rates']['read_top1']:.4f},{r['rates']['read_top3']:.4f},"
                    f"{r['rates']['recall']:.4f},{r['rates']['precision']:.4f}" for r in rows], ""]
        fig, ax = plt.subplots(figsize=(8, 4.5))
        lo = [r["ci95"]["read_top1"][0] for r in rows]
        hi = [r["ci95"]["read_top1"][1] for r in rows]
        vals = [r["rates"]["read_top1"] for r in rows]
        ax.barh([r["classifier"] for r in rows], vals,
                xerr=[[v - l for v, l in zip(vals, lo)], [h - v for v, h in zip(vals, hi)]], capsize=3)
        ax.invert_yaxis()
        ax.set_xlabel("Signs read correctly (top-1), 95% CI over tablets")
        ax.set_title(f"End to end with {rows[0]['detector']}")
        fig.tight_layout()
        fig.savefig(OUT / "end2end.png", dpi=150)
        plt.close(fig)
    if not lines:
        sys.exit("No results yet; run detect / classify first.")
    (OUT / "results.csv").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"Charts and results.csv in {OUT}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["detect", "classify", "end2end", "report"])
    parser.add_argument("--models", nargs="+", help="weights to benchmark (default: the lists at the top of this file)")
    parser.add_argument("--data", type=Path, help="data.yaml (detect) or crop folder (classify)")
    parser.add_argument("--epochs", type=int, help="override the train.py default")
    parser.add_argument("--batch", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--quick", action="store_true", help=f"{QUICK_EPOCHS} epochs per model, to test the pipeline")
    parser.add_argument("--force", action="store_true", help="retrain models that already have results")
    args = parser.parse_args()
    {"detect": detect, "classify": classify, "end2end": end2end, "report": report}[args.stage](args)


if __name__ == "__main__":
    main()
