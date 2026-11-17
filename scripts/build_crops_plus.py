"""Build fraction-solver/out/sign_crops_plus: the classifier crops plus unplaced drawings and font signs.

    python scripts/build_crops_plus.py [--no-drawings] [--no-font] [--out DIR]

See fraction-solver/la/cropsplus.py. Train it with
    python train.py classify --data fraction-solver/out/sign_crops_plus --name cls_plus
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "fraction-solver")]

from la import cropsplus

from backend.app.reading_pipeline.glyphs import glyph

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--out", type=Path, default=cropsplus.PLUS_DIR)
parser.add_argument("--no-drawings", action="store_true")
parser.add_argument("--no-font", action="store_true")
args = parser.parse_args()
report = cropsplus.build_crops_plus(glyph, out=args.out, drawings=not args.no_drawings, font=not args.no_font)
print(json.dumps(report["plus"], indent=1)[:2000])
