"""A sign comparer: embeddings trained so that crops of one sign sit together.

The classifier picks one of 279 classes, and 126 of them have a single real
training crop. A comparer answers a different question, "how alike are these two
drawings?", so it can be checked against a sign's few reference drawings (and a
font-rendered glyph of the sign) instead of needing the sign's own output unit.
Two uses:

* **re-scoring** the classifier's answer (`blend`): each candidate sign scores by
  the similarity of the crop to that sign's references, blended like
  `la.reader.NeighbourBank`;
* **zero-shot proposals** (`propose`, `blend(zero_shot=True)`): matching the crop
  against font renders of every sign with a Unicode glyph, so signs the
  classifier never learned can still be suggested. This path is kept apart in
  every function and measured on its own (the benchmark's "unseen" bucket).

Training (`train`): a ResNet-18 (ImageNet weights, downloaded by torchvision) or
a tiny CNN (tests) maps a 128 px crop to a unit vector; an ArcFace head (additive
angular margin) teaches the embedding, with classes drawn like
`augment.resample_count` (mass ~ sqrt of the class size) and every draw varied by
`augment.vary`. Only train-split tablets are ever read (`read_train` refuses
anything else). Classes with no real train crop are never trained on, font
renders included, so they stay a fair zero-shot test.

Torch is imported lazily by everything that needs it; `RefBank` and `blend` are
numpy only, so a tuner can cache embeddings and re-blend without torch.
"""

from __future__ import annotations

import csv
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from la import augment
from la.shapes import load_mask
from la.signboxes import UNKNOWN_SIGN
from la.signcrops import identified, sign_id

EMBED_DIM = 128
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
FONT_VARY_P = 0.9          # share of font draws that are varied (the rest are the plain render)
REAL_VARY_P = 0.5          # share of real draws replaced by a varied copy of their ink


# ----------------------------------------------------------------------------- data

@dataclass
class Item:
    sign: str
    crop: np.ndarray        # 128x128 uint8, black ink on white, cut like the classifier's
    mask: np.ndarray        # the sign's own ink inside its box, for `augment.vary`


def read_train(annotations: list[dict], dataset: Path, load: Callable = load_mask) -> list[Item]:
    """Every identified train sign as an `Item`. Tablets of any other split are never opened."""
    items = []
    for tablet in annotations:
        if tablet["split"] != "train":
            continue
        named = [s for s in identified(tablet) if sign_id(s) != UNKNOWN_SIGN]
        if not named:
            continue
        ink = load(Path(dataset) / tablet["image"])
        for s in named:
            x0, y0, x1, y1 = s["xyxy"]
            items.append(Item(sign_id(s), augment.square_crop(ink, (x0, y0, x1, y1)),
                              ink[int(y0):int(y1), int(x0):int(x1)].copy()))
    return items


def font_masks(signs: Sequence[str], glyph: Callable, font_path: Path | None = None) -> dict[str, np.ndarray]:
    """Thinned ink mask of each sign's Noto Sans Linear A glyph (signs without one are left out)."""
    from PIL import ImageFont

    from la import cropsplus
    face = ImageFont.truetype(str(font_path or cropsplus.FONT), cropsplus.FONT_PX)
    out = {}
    for sign in signs:
        char = glyph(sign)
        mask = cropsplus.font_mask(char, face) if char else None
        if mask is not None:
            out[sign] = mask
    return out


def render_font(mask: np.ndarray) -> np.ndarray:
    """A font mask framed like a cut crop, as 128x128 uint8."""
    return augment.render(mask, margin=augment.CROP_MARGIN)


def vocabulary(annotations: list[dict]) -> list[str]:
    """Every sign ID the dataset names, in any split: label names only, no crops."""
    return sorted({sign_id(s) for t in annotations for s in identified(t)} - {UNKNOWN_SIGN})


class CropDataset:
    """Real train crops plus (optionally) font masks of train classes, varied on the fly.

    Item `i` and epoch `e` always give the same pixels (a generator seeded by
    `(seed, e, i)`), so a resumed run repeats an uninterrupted one.
    """

    def __init__(self, items: list[Item], fonts: dict[str, np.ndarray] | None = None, seed: int = 0):
        self.items = items
        self.classes = sorted({i.sign for i in items})
        self.index = {c: n for n, c in enumerate(self.classes)}
        # Font masks only for classes that have a real crop: others stay zero-shot.
        self.fonts = [(s, m) for s, m in sorted((fonts or {}).items()) if s in self.index]
        self.seed, self.epoch = seed, 0

    def __len__(self) -> int:
        return len(self.items) + len(self.fonts)

    def label(self, i: int) -> int:
        sign = self.items[i].sign if i < len(self.items) else self.fonts[i - len(self.items)][0]
        return self.index[sign]

    def weights(self) -> np.ndarray:
        """Draw weight per item: class mass ~ sqrt(class size), as `augment.resample_count` lifts rare classes."""
        labels = np.array([self.label(i) for i in range(len(self))])
        size = np.bincount(labels, minlength=len(self.classes))
        return (size[labels] ** -0.5).astype(np.float64)

    def __getitem__(self, i: int):
        import torch
        rng = np.random.default_rng([self.seed, self.epoch, i])
        if i < len(self.items):
            item = self.items[i]
            crop = (augment.render(augment.vary(item.mask, rng), margin=augment.CROP_MARGIN)
                    if rng.random() < REAL_VARY_P and item.mask.any() else item.crop)
        else:
            mask = self.fonts[i - len(self.items)][1]
            crop = render_font(augment.vary(mask, rng) if rng.random() < FONT_VARY_P else mask)
        return torch.from_numpy(np.array(crop))[None], self.label(i)


# ----------------------------------------------------------------------------- reference bank

@dataclass
class RefBank:
    """Unit embeddings of reference drawings, by sign; numpy only.

    A sign's score for a query is the mean of its `k` best cosine similarities to
    its real references (k=1 is the max), fused by max with its font render's
    similarity when it has one. -1 where a sign has no reference at all.
    """
    signs: np.ndarray            # sign ID of each reference
    vectors: np.ndarray          # unit-normalised, (n x d)
    is_font: np.ndarray          # True for font renders

    def __post_init__(self):
        self.signs = np.asarray(self.signs)
        self.is_font = np.asarray(self.is_font, dtype=bool)
        real: dict[str, list[int]] = defaultdict(list)
        font: dict[str, list[int]] = defaultdict(list)
        for n, (sign, f) in enumerate(zip(self.signs, self.is_font)):
            (font if f else real)[str(sign)].append(n)
        self._real = {k: np.array(v) for k, v in real.items()}
        self._font = {k: np.array(v) for k, v in font.items()}

    @property
    def real_signs(self) -> list[str]:
        return sorted(k for k, v in self._real.items() if len(v))

    @property
    def font_signs(self) -> list[str]:
        return sorted(k for k, v in self._font.items() if len(v))

    @property
    def all_signs(self) -> list[str]:
        return sorted(set(self.real_signs) | set(self.font_signs))

    def _score(self, sims: np.ndarray, sign: str, k: int, use_real: bool, use_font: bool) -> np.ndarray | None:
        parts = []
        real = self._real.get(sign, np.zeros(0, int)) if use_real else np.zeros(0, int)
        if len(real):
            part = np.sort(sims[:, real], axis=1)[:, ::-1][:, :k]
            parts.append(part.mean(axis=1))
        font = self._font.get(sign, np.zeros(0, int)) if use_font else np.zeros(0, int)
        if len(font):
            parts.append(sims[:, font].max(axis=1))
        return np.max(parts, axis=0) if parts else None

    def scores(self, queries: np.ndarray, candidates: Sequence[str], k: int = 1,
               use_real: bool = True, use_font: bool = True) -> np.ndarray:
        """(n queries x n candidates), in candidate order; -1 for a candidate without references."""
        sims = queries @ self.vectors.T
        out = np.full((len(queries), len(candidates)), -1.0, dtype=np.float32)
        for j, sign in enumerate(candidates):
            s = self._score(sims, sign, k, use_real, use_font)
            if s is not None:
                out[:, j] = s
        return out

    def propose(self, queries: np.ndarray, top: int = 5, k: int = 1,
                font_only: bool = False) -> list[list[tuple[str, float]]]:
        """Best `top` signs per query over the whole bank. `font_only` uses font renders alone: the zero-shot path."""
        signs = self.font_signs if font_only else self.all_signs
        s = self.scores(queries, signs, k, use_real=not font_only)
        out = []
        for row in s:
            order = np.argsort(-row, kind="stable")[:top]
            out.append([(signs[int(i)], float(row[i])) for i in order])
        return out


def blend(names: list[str], probs: np.ndarray, bank: RefBank, queries: np.ndarray, weight: float = 0.5,
          temperature: float = 0.05, k: int = 1, zero_shot: bool = False,
          propose_k: int = 5) -> tuple[list[str], np.ndarray]:
    """(1 - weight) * classifier + weight * softmax(similarity / temperature), over the classifier's names.

    With `zero_shot`, each crop's `propose_k` best font matches that the classifier
    does not know join that crop's candidates (the classifier gives them 0), and the
    returned names grow by those signs. Without it, names and shape are unchanged.
    """
    if not len(probs) or weight <= 0:
        return list(names), probs
    names = list(names)
    allowed = np.ones((len(probs), len(names)), dtype=bool)
    if zero_shot:
        known = set(names)
        found = [[s for s, _ in row if s not in known]
                 for row in bank.propose(queries, propose_k + len(known & set(bank.font_signs)), font_only=True)]
        found = [row[:propose_k] for row in found]
        extra = sorted({s for row in found for s in row})
        names += extra
        probs = np.concatenate([probs, np.zeros((len(probs), len(extra)), probs.dtype)], axis=1)
        allowed = np.concatenate([allowed, np.zeros((len(probs), len(extra)), bool)], axis=1)
        col = {s: len(names) - len(extra) + n for n, s in enumerate(extra)}
        for r, row in enumerate(found):
            for s in row:
                allowed[r, col[s]] = True
    sims = bank.scores(queries, names, k) / temperature
    sims = np.where(allowed, sims, -np.inf)
    e = np.exp(sims - sims.max(axis=1, keepdims=True))
    return names, (1 - weight) * probs + weight * e / e.sum(axis=1, keepdims=True)


# ----------------------------------------------------------------------------- model

def make_net(backbone: str = "resnet18", dim: int = EMBED_DIM, pretrained: bool = True):
    """Crop (B,1,128,128 uint8) -> unit embedding (B,dim)."""
    import torch
    from torch import nn

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            if backbone == "resnet18":
                from torchvision.models import ResNet18_Weights, resnet18
                body = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
                body.fc = nn.Identity()
                width = 512
            elif backbone == "tiny":
                body = nn.Sequential(nn.Conv2d(3, 8, 3, 2, 1), nn.ReLU(), nn.Conv2d(8, 16, 3, 2, 1), nn.ReLU(),
                                     nn.AdaptiveAvgPool2d(1), nn.Flatten())
                width = 16
            else:
                raise ValueError(f"unknown backbone {backbone!r} (resnet18, tiny)")
            self.body = body
            self.proj = nn.Linear(width, dim)
            self.register_buffer("mean", torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1))
            self.register_buffer("std", torch.tensor(IMAGENET_STD).view(1, 3, 1, 1))

        def forward(self, x):
            x = x.float().div(255).expand(-1, 3, -1, -1)
            x = (x - self.mean) / self.std
            return nn.functional.normalize(self.proj(self.body(x)), dim=1)

    return Net()


def make_head(n_classes: int, dim: int):
    import torch
    from torch import nn

    class ArcFace(nn.Module):
        """Additive angular margin softmax: cos(theta + margin) for the true class, scaled."""

        def __init__(self):
            super().__init__()
            self.weight = nn.Parameter(torch.randn(n_classes, dim) * 0.01)

        def forward(self, emb, labels, margin: float = 0.3, scale: float = 30.0):
            cos = (emb @ nn.functional.normalize(self.weight, dim=1).T).clamp(-1 + 1e-6, 1 - 1e-6)
            theta = torch.acos(cos.gather(1, labels[:, None]))
            target = torch.cos(theta + margin)
            # Past theta + margin > pi the cosine rises again; keep it falling (the "easy" fix).
            target = torch.where(theta + margin < torch.pi, target, cos.gather(1, labels[:, None]) - margin * 0.5)
            logits = cos.scatter(1, labels[:, None], target) * scale
            return nn.functional.cross_entropy(logits, labels), cos

    return ArcFace()


def _to_gray(crops: list[np.ndarray]) -> np.ndarray:
    return np.stack([c if c.ndim == 2 else c[..., 0] for c in crops])[:, None]


def embed_crops(net, crops: list[np.ndarray], device: str = "cpu", batch: int = 128,
                dim: int = EMBED_DIM) -> np.ndarray:
    """Unit embeddings (n x dim) of HxW or HxWx3 uint8 crops."""
    import torch
    if not len(crops):
        return np.zeros((0, dim), np.float32)
    gray, out = _to_gray(crops), []
    net.eval()
    with torch.inference_mode():
        for i in range(0, len(gray), batch):
            out.append(net(torch.from_numpy(gray[i:i + batch]).to(device)).cpu().numpy())
    return np.concatenate(out).astype(np.float32)


class Comparer:
    """Network + reference bank: `scores`, `propose`, `blend`, `save`/`load`."""

    def __init__(self, net, bank: RefBank, meta: dict | None = None, device: str = "cpu",
                 weight: float = 0.5, temperature: float = 0.05, k: int = 1, zero_shot: bool = False,
                 propose_k: int = 5):
        self.net, self.bank, self.meta, self.device = net, bank, dict(meta or {}), device
        self.weight, self.temperature, self.k = weight, temperature, k
        self.zero_shot, self.propose_k = zero_shot, propose_k
        self.net.to(device).eval()

    def embed(self, crops: list[np.ndarray], batch: int = 128) -> np.ndarray:
        return embed_crops(self.net, crops, self.device, batch, self.bank.vectors.shape[1])

    def scores(self, crops: list[np.ndarray], candidate_signs: Sequence[str], k: int | None = None) -> np.ndarray:
        """Similarity of each crop to each candidate sign (n crops x n candidates, candidate order)."""
        return self.bank.scores(self.embed(crops), candidate_signs, self.k if k is None else k)

    def propose(self, crops: list[np.ndarray], k: int = 5, font_only: bool = False) -> list[list[tuple[str, float]]]:
        """Best `k` signs per crop from the whole bank (real references and font renders)."""
        return self.bank.propose(self.embed(crops), k, self.k, font_only)

    def blend(self, names: list[str], probs: np.ndarray, crops: list[np.ndarray]) -> tuple[list[str], np.ndarray]:
        return blend(names, probs, self.bank, self.embed(crops), self.weight, self.temperature, self.k,
                     self.zero_shot, self.propose_k)

    def save(self, path: Path) -> None:
        import torch
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state": self.net.state_dict(), "meta": self.meta,
                    "bank": {"signs": [str(s) for s in self.bank.signs], "vectors": self.bank.vectors,
                             "is_font": self.bank.is_font}}, path)

    @classmethod
    def load(cls, path: Path, device: str = "cpu", **kw) -> Comparer:
        import torch
        ck = torch.load(path, map_location="cpu", weights_only=False)
        meta = ck["meta"]
        net = make_net(meta["backbone"], meta["dim"], pretrained=False)
        net.load_state_dict(ck["state"])
        b = ck["bank"]
        return cls(net, RefBank(np.array(b["signs"]), b["vectors"], b["is_font"]), meta, device, **kw)


def build_bank(net, items: list[Item], fonts: dict[str, np.ndarray], device: str = "cpu") -> RefBank:
    """Embed every real train crop and the font render of every sign in `fonts` (the whole vocabulary)."""
    real = embed_crops(net, [i.crop for i in items], device)
    names = sorted(fonts)
    font = embed_crops(net, [render_font(fonts[s]) for s in names], device)
    return RefBank(np.array([i.sign for i in items] + names), np.concatenate([real, font]),
                   np.array([False] * len(items) + [True] * len(names)))


# ----------------------------------------------------------------------------- training

LOG_FIELDS = ("epoch", "loss", "train_acc", "lr", "margin", "seconds", "vram_peak_mb", "rss_mb")


def train(items: list[Item], vocab_fonts: dict[str, np.ndarray], out: Path, epochs: int = 30,
          batch: int = 128, lr: float = 1e-3, dim: int = EMBED_DIM, use_font: bool = False,
          backbone: str = "resnet18", pretrained: bool = True, seed: int = 0, device: str | None = None,
          margin: float = 0.3, scale: float = 30.0, resume: bool = True, log: Callable = print) -> Comparer:
    """Train on `items` (train split only), write `out/last.pt`, `out/log.csv`, `out/comparer.pt`.

    `vocab_fonts` (font masks of every sign with a glyph) feed the zero-shot bank
    always, and the training draws only when `use_font`. Resumes from `out/last.pt`.
    """
    import torch
    from torch.utils.data import DataLoader, WeightedRandomSampler

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    data = CropDataset(items, vocab_fonts if use_font else None, seed)
    net = make_net(backbone, dim, pretrained).to(device)
    head = make_head(len(data.classes), dim).to(device)
    params = [*net.parameters(), *head.parameters()]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(epochs, 1))
    amp = device.startswith("cuda")
    scaler = torch.amp.GradScaler(enabled=amp)
    meta = {"backbone": backbone, "dim": dim, "classes": data.classes, "font_train": use_font,
            "pretrained": pretrained, "seed": seed, "epochs": epochs, "batch": batch, "lr": lr,
            "margin": margin, "scale": scale, "n_real": len(items), "n_font_train": len(data.fonts)}
    start, last = 0, out / "last.pt"
    if resume and last.is_file():
        ck = torch.load(last, map_location=device, weights_only=False)
        if ck["meta"]["classes"] != data.classes or ck["meta"]["dim"] != dim:
            raise ValueError(f"{last} was trained on other classes or dimension; use a new --out or --no-resume")
        net.load_state_dict(ck["net"])
        head.load_state_dict(ck["head"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        start = ck["epoch"]
        log(f"resumed from {last} at epoch {start}")
    log_path = out / "log.csv"
    new_log = not log_path.is_file() or start == 0
    if amp:
        torch.cuda.reset_peak_memory_stats()
    with open(log_path, "w" if new_log else "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new_log:
            writer.writerow(LOG_FIELDS)
        weights = torch.from_numpy(data.weights())
        for epoch in range(start, epochs):
            started = time.time()
            data.epoch = epoch
            net.train()
            head.train()
            sampler = WeightedRandomSampler(weights, len(data), replacement=True,
                                            generator=torch.Generator().manual_seed(seed * 100003 + epoch))
            # Ramp the margin up over the first epochs: a full margin on a random head does not train.
            m = margin * min(1.0, (epoch + 1) / max(1, min(3, epochs // 4)))
            total, correct, seen = 0.0, 0, 0
            for x, y in DataLoader(data, batch_size=batch, sampler=sampler, num_workers=0):
                x, y = x.to(device), y.to(device)
                with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=amp):
                    emb = net(x)
                loss, cos = head(emb.float(), y, m, scale)
                opt.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
                total += float(loss.detach()) * len(y)
                correct += int((cos.argmax(1) == y).sum())
                seen += len(y)
            lr_now = opt.param_groups[0]["lr"]
            sched.step()
            vram = torch.cuda.max_memory_allocated() / 2**20 if amp else 0.0
            row = [epoch + 1, round(total / seen, 4), round(correct / seen, 4), f"{lr_now:.2e}", round(m, 3),
                   round(time.time() - started, 1), round(vram), round(_rss_mb())]
            writer.writerow(row)
            fh.flush()
            log(" ".join(f"{k}={v}" for k, v in zip(LOG_FIELDS, row)))
            torch.save({"net": net.state_dict(), "head": head.state_dict(), "opt": opt.state_dict(),
                        "sched": sched.state_dict(), "epoch": epoch + 1, "meta": meta}, last)
    comparer = Comparer(net, build_bank(net, items, vocab_fonts, device), meta, device)
    comparer.save(out / "comparer.pt")
    return comparer


def _rss_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 2**20
    except Exception:  # noqa: BLE001  (psutil missing or denied: the column is informational)
        return float("nan")
