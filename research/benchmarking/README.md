# Model benchmark (issue #56)

Which model reads Linear A signs best? Every candidate is trained with the same
recipe (`train.py`) on the same tablet-level split, and scored on the same 99
held-out test tablets. Reproduce with `benchmark.py` or `benchmark.ipynb`
(Colab-ready).

```bash
python benchmark.py detect      # 5 one-class detectors
python benchmark.py classify    # 10 sign classifiers
python benchmark.py end2end     # best detector x every classifier, via evaluate.py
python benchmark.py report      # results.csv + charts in runs/benchmark/
```

Raw numbers: [`results/results.csv`](results/results.csv). Charts:
[`detect`](results/detect.png), [`classify`](results/classify.png),
[`end2end`](results/end2end.png).

## Candidates

- **Detectors** (Ultralytics): yolo26n, yolo26s, yolo11n, yolo11s, yolov8n.
- **Classifiers:** the matching YOLO `-cls` models, plus ImageNet-pretrained
  torchvision networks (ResNet-18/50, EfficientNet-B0, MobileNetV3-Large,
  ConvNeXt-Tiny) fine-tuned with the same augmentation rules (no flips, gentle crops).
- RT-DETR-L was tried and dropped from the default list: it needs more GPU memory
  than an 8 GB card at 1024 px (about 2 hours per epoch). It stays in
  `OPTIONAL_DETECTORS` for a bigger GPU.

## Results

**Detectors** (test tablets)

| Model | Params (M) | mAP50-95 | mAP50 | Recall | Precision | ms/tablet |
|---|---|---|---|---|---|---|
| yolo26n | 2.5 | **0.768** | 0.923 | 0.894 | 0.900 | 50 |
| yolo11n | 2.6 | 0.755 | 0.914 | 0.876 | 0.914 | 35 |
| yolo11s | 9.4 | 0.746 | 0.910 | 0.900 | 0.891 | 30 |
| yolo26s | 10.0 | 0.744 | 0.908 | 0.866 | 0.896 | 49 |
| yolov8n | 3.1 | 0.736 | 0.912 | 0.866 | 0.894 | 33 |

**Classifiers** (test crops)

| Model | Params (M) | Top-1 | Top-5 | Train (min) |
|---|---|---|---|---|
| tv-convnext_tiny | 28.0 | **0.761** | 0.889 | 48 |
| tv-efficientnet_b0 | 4.4 | 0.755 | 0.881 | 16 |
| tv-resnet18 | 11.3 | 0.731 | 0.841 | 11 |
| tv-mobilenet_v3_large | 4.6 | 0.723 | 0.865 | 9 |
| tv-resnet50 | 24.1 | 0.720 | 0.873 | 12 |
| yolo11n-cls | 1.9 | 0.720 | 0.872 | 12 |
| yolo11s-cls | 5.8 | 0.713 | 0.856 | 9 |
| yolov8n-cls | 1.8 | 0.713 | 0.864 | 7 |
| yolo26n-cls | 1.9 | 0.712 | 0.851 | 6 |
| yolo26s-cls | 5.8 | 0.708 | 0.865 | 6 |

**End to end** (whole tablets, yolo26n as detector; signs read correctly, top-1,
95% CI over tablets)

| Classifier | Top-1 | 95% CI |
|---|---|---|
| tv-convnext_tiny | 64.7% | 58.2-70.7 |
| tv-efficientnet_b0 | 63.6% | 55.9-69.8 |
| yolo11n-cls | 63.3% | 56.0-69.6 |
| tv-resnet18 | 62.4% | 55.4-68.6 |
| tv-mobilenet_v3_large | 61.2% | 53.2-68.0 |
| yolo11s-cls | 61.2% | 54.2-67.4 |
| yolov8n-cls | 61.2% | 53.6-67.4 |
| tv-resnet50 | 60.9% | 53.7-66.5 |
| yolo26s-cls | 60.7% | 53.9-66.7 |
| yolo26n-cls | 60.6% | 53.6-67.2 |

## Conclusions

- **Detector:** yolo26n is best and also the smallest. The small variants gain
  nothing here.
- **Classifier:** ConvNeXt-Tiny and EfficientNet-B0 lead, but **end to end the 95%
  intervals of all ten classifiers overlap**, so the choice is not statistically
  significant on this test set. EfficientNet-B0 is within noise of ConvNeXt at a
  sixth of the parameters and a third of the training time.
- **Bottleneck:** detection recall is about 89% and the classifier names about 71%
  of the signs it is handed, so recognition limits the pipeline more than detection.
- **Limitations:** one seed per model, one detector used for the end-to-end stage,
  and a small test set (99 tablets, 657 signs).
