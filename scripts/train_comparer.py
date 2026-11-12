"""Train the sign comparer (la/comparer.py) on the train split of the sign dataset.

    python scripts/train_comparer.py --name comparer [--epochs 30] [--batch 128] [--lr 1e-3]
                                     [--dim 128] [--font] [--out runs/comparer/<name>]

Writes `<out>/log.csv` (one row per epoch), `<out>/last.pt` (resumable: rerun the
same command to continue) and `<out>/comparer.pt` (weights plus the reference bank:
real train crops and font renders of every sign with a Unicode glyph).
`--font` also trains on varied font renders of train classes. workers=0 always:
dataloader workers have crashed this 16 GB laptop. Val and test tablets are never read.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "fraction-solver")]

from la import comparer
from la.signboxes import DATASET_DIR

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--name", default="comparer")
parser.add_argument("--out", type=Path, help="default runs/comparer/<name>")
parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
parser.add_argument("--epochs", type=int, default=30)
parser.add_argument("--batch", type=int, default=128)
parser.add_argument("--lr", type=float, default=1e-3)
parser.add_argument("--dim", type=int, default=comparer.EMBED_DIM)
parser.add_argument("--font", action="store_true", help="also train on font renders of train classes")
parser.add_argument("--backbone", choices=["resnet18", "tiny"], default="resnet18")
parser.add_argument("--no-pretrained", action="store_true", help="random init instead of ImageNet weights")
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--device", default=None, help="cuda or cpu (default: cuda if available)")
parser.add_argument("--max-items", type=int, default=0, help="smoke runs: use only this many train crops")
parser.add_argument("--no-resume", action="store_true")
args = parser.parse_args()

if __name__ == "__main__":
    from backend.app.reading_pipeline.glyphs import glyph

    out = args.out or ROOT / "runs" / "comparer" / args.name
    annotations = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))
    items = comparer.read_train(annotations, args.dataset)
    if args.max_items:
        items = items[::max(1, len(items) // args.max_items)]
    fonts = comparer.font_masks(comparer.vocabulary(annotations), glyph)
    print(f"{len(items)} train crops, {len({i.sign for i in items})} classes, {len(fonts)} font glyphs "
          f"(font training {'on' if args.font else 'off'}); writing {out}", flush=True)
    comparer.train(items, fonts, out, epochs=args.epochs, batch=args.batch, lr=args.lr, dim=args.dim,
                   use_font=args.font, backbone=args.backbone, pretrained=not args.no_pretrained,
                   seed=args.seed, device=args.device, resume=not args.no_resume)
