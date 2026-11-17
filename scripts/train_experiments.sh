#!/usr/bin/env bash
# Model-improvement training runs, one at a time on the laptop GPU (6 GB).
#
#   PY=<python with CUDA torch + ultralytics> RESQ=<path to resq.py> bash scripts/train_experiments.sh [run ...]
#
# Runs: det_synth  one-class detector on real + 1000 synthetic tablets (data: la.cli synth on a copy)
#       det_s      larger yolo26s detector (batch 4 to fit 6 GB)
#       cls_s      larger yolo26s-cls classifier at 160 px
#       comparer   sign comparer (la/comparer.py, issue #66): ArcFace embedding, font renders in training;
#                  ~1.7k samples/epoch (80 s on CPU), 1 GB RSS on CPU; VRAM 2000 is an estimate (resnet18, fp16, batch 64);
#                  not in the default list, queue it with: bash scripts/train_experiments.sh comparer
# Each matches signs-v1's recipe except for the one change, including 100 detector
# epochs, so the benchmark compares like with like. workers=0: dataloader workers
# have crashed this 16 GB laptop (Windows error 1455). Without RESQ, runs start directly.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python}"
OUT="$ROOT/fraction-solver/out"
runs=("$@")
[ ${#runs[@]} -eq 0 ] && runs=(det_synth det_s cls_s)

queue() {  # queue <label> <vram MB> <ram MB> -- command...
  local label=$1 gpu=$2 ram=$3; shift 4
  if [ -n "${RESQ:-}" ]; then
    "$PY" "$RESQ" run --gpu "$gpu" --cpu 1 --ram "$ram" --label "ase: $label" --priority 2 -- "$@"
  else
    "$@"
  fi
}

for run in "${runs[@]}"; do
  case "$run" in
    det_synth)
      queue det_synth 4500 4500 -- "$PY" "$ROOT/train.py" detect --data "$OUT/yolo_signs_synth/data.yaml" \
        --epochs 100 --workers 0 --name det_synth ;;
    det_synth_resume)
      queue det_synth 4500 4500 -- "$PY" "$ROOT/train.py" detect --resume "$ROOT/runs/detect/det_synth" ;;
    det_s_resume)
      queue det_s 5200 4500 -- "$PY" "$ROOT/train.py" detect --resume "$ROOT/runs/detect/det_s" ;;
    det_s)
      queue det_s 5200 4500 -- "$PY" "$ROOT/train.py" detect --model yolo26s.pt --batch 4 \
        --epochs 100 --workers 0 --name det_s ;;
    cls_s)
      queue cls_s 3500 3500 -- "$PY" "$ROOT/train.py" classify --model yolo26s-cls.pt --imgsz 160 \
        --workers 0 --name cls_s ;;
    comparer)
      queue comparer 2000 2500 -- "$PY" "$ROOT/scripts/train_comparer.py" --name comparer --font \
        --epochs 60 --batch 64 --device cuda ;;
    *) echo "unknown run $run" >&2; exit 2 ;;
  esac
done
