"""Turning sign crops into vectors, for nearest-neighbour reading and for clustering.

Three backbones:

* `yolo`: the trained sign classifier's own features (Ultralytics `embed`). They
  know Linear A, but only the 279 signs it was trained on, mostly the common ones.
* `resnet50`: torchvision's ImageNet ResNet-50 (weights only; the code ships
  with torchvision). A general image model that has never seen Linear A, so its
  features do not favour the common signs, which may suit signs with one or two
  training examples.
* `dinov2`: DINOv2 ViT-S/14, a self-supervised general model (Meta, Apache-2.0).
  `torch.hub` downloads and runs code from its GitHub repository, so it is only
  used where that is allowed.

Each `*_embedder` returns a function from a list of HxWx3 uint8 crops to an
(n x d) float32 array. Torch and Ultralytics are imported lazily.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

Embedder = Callable[[list[np.ndarray]], np.ndarray]
DINO_SIZE = 224                      # a multiple of the 14 px patch
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def yolo_embedder(classifier, batch: int = 64, device: str | None = "cpu") -> Embedder:
    def embed(crops: list[np.ndarray]) -> np.ndarray:
        out = []
        for i in range(0, len(crops), batch):
            vectors = classifier.embed(crops[i:i + batch], device=device, verbose=False)
            out.extend(v.detach().cpu().numpy().ravel() for v in vectors)
        return np.asarray(out, dtype=np.float32)
    return embed


def dinov2_embedder(variant: str = "dinov2_vits14", batch: int = 32) -> Embedder:
    import torch
    import torch.nn.functional as F

    model = torch.hub.load("facebookresearch/dinov2", variant, verbose=False).eval()
    mean = torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(1, 3, 1, 1)

    def embed(crops: list[np.ndarray]) -> np.ndarray:
        out = []
        with torch.inference_mode():
            for i in range(0, len(crops), batch):
                x = torch.from_numpy(np.stack(crops[i:i + batch])).permute(0, 3, 1, 2).float() / 255
                x = F.interpolate(x, size=(DINO_SIZE, DINO_SIZE), mode="bilinear", align_corners=False)
                out.append(model((x - mean) / std).numpy())
        return np.concatenate(out).astype(np.float32) if out else np.zeros((0, 384), np.float32)
    return embed


def resnet50_embedder(batch: int = 32) -> Embedder:
    import torch
    import torch.nn.functional as F
    from torchvision.models import ResNet50_Weights, resnet50

    model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2).eval()
    model.fc = torch.nn.Identity()          # the 2048-d pooled features
    mean = torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(1, 3, 1, 1)

    def embed(crops: list[np.ndarray]) -> np.ndarray:
        out = []
        with torch.inference_mode():
            for i in range(0, len(crops), batch):
                x = torch.from_numpy(np.stack(crops[i:i + batch])).permute(0, 3, 1, 2).float() / 255
                x = F.interpolate(x, size=(DINO_SIZE, DINO_SIZE), mode="bilinear", align_corners=False)
                out.append(model((x - mean) / std).numpy())
        return np.concatenate(out).astype(np.float32) if out else np.zeros((0, 2048), np.float32)
    return embed


def embedder(backbone: str, classifier=None, **kw) -> Embedder:
    if backbone == "yolo":
        if classifier is None:
            raise ValueError("the yolo backbone needs the classifier")
        return yolo_embedder(classifier, **kw)
    if backbone == "resnet50":
        return resnet50_embedder(**kw)
    if backbone == "dinov2":
        return dinov2_embedder(**kw)
    raise ValueError(f"unknown backbone {backbone!r} (yolo, resnet50, dinov2)")
