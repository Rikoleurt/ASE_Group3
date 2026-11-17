"""Sign classifiers of either kind behind one interface: Ultralytics YOLO-cls or torchvision.

`load_classifier(path)` returns an object with `names` ({index: sign ID}) and
`predict(crops, device=None, verbose=False)`, whose results carry
`probs.data` like Ultralytics results, so `la.reader` uses both alike.

The torchvision side comes from the model benchmark in PR #67 (ahmad-rafee):
ImageNet-pretrained networks fine-tuned on the sign crops, saved as
{"arch", "classes", "state"}. Two changes from that version: the checkpoint
type is recognised from its contents, not from its folder name, so a copy in
models/ still loads; and crops are resized exactly as in training
(torchvision Resize to 128 px, grayscale to 3 channels, ImageNet
normalisation), instead of PIL's default resize.
"""

from __future__ import annotations

from pathlib import Path

ARCH_HEADS = {"resnet": "fc", "efficientnet": "classifier", "mobilenet": "classifier", "convnext": "classifier"}
SIZE = 128


def is_torchvision(path: str | Path) -> bool:
    """True for a {"arch", "classes", "state"} checkpoint (torchvision), False for anything else."""
    import torch
    try:
        ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    except Exception:  # noqa: BLE001 - not a torch pickle we can read: leave it to Ultralytics
        return False
    return isinstance(ckpt, dict) and {"arch", "classes", "state"} <= set(ckpt)


def _replace_head(model, arch: str, n_classes: int):
    import torch
    kind = next(k for k in ARCH_HEADS if arch.startswith(k))
    attr = ARCH_HEADS[kind]
    layer = getattr(model, attr)
    if isinstance(layer, torch.nn.Sequential):
        layer[-1] = torch.nn.Linear(layer[-1].in_features, n_classes)
    else:
        setattr(model, attr, torch.nn.Linear(layer.in_features, n_classes))
    return model


class _Probs:
    def __init__(self, data):
        self.data = data


class _Result:
    def __init__(self, names, probs):
        self.names = names
        self.probs = _Probs(probs)


class TorchvisionClassifier:
    """A saved torchvision sign classifier with the Ultralytics `predict` interface."""

    def __init__(self, path: str | Path, device: str | None = None) -> None:
        import torch
        import torchvision
        from torchvision import transforms as T

        ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
        self.arch = ckpt["arch"]
        self.names = dict(enumerate(ckpt["classes"]))
        model = _replace_head(getattr(torchvision.models, self.arch)(weights=None), self.arch, len(self.names))
        model.load_state_dict(ckpt["state"])
        self.device = device or "cpu"
        self.model = model.to(self.device).eval()
        self.transform = T.Compose([T.Grayscale(3), T.Resize((SIZE, SIZE)), T.ToTensor(),
                                    T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    def predict(self, crops, device: str | None = None, verbose: bool = False, batch: int = 64):
        import torch
        from PIL import Image

        if device and device != self.device:
            self.model.to(device)
            self.device = device
        out = []
        with torch.no_grad():
            for i in range(0, len(crops), batch):
                x = torch.stack([self.transform(Image.fromarray(c)) for c in crops[i:i + batch]]).to(self.device)
                out.extend(self.model(x).softmax(dim=1).cpu())
        return [_Result(self.names, p) for p in out]


def load_classifier(path: str | Path, device: str | None = None):
    """An Ultralytics or a torchvision classifier, whichever `path` holds."""
    if is_torchvision(path):
        return TorchvisionClassifier(path, device)
    from ultralytics import YOLO
    return YOLO(str(path))
