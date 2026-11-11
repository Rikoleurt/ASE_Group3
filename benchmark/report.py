"""Turn a benchmark run into a table and charts for a presentation.

    python -m benchmark.report runs/benchmark/<stamp>-val

Writes `report.md` (tables, best first) and PNG charts next to `results.json`:

* `top1.png`: signs read correctly end to end, and named correctly on true boxes,
  per model with 95% intervals (two charts, not two axes).
* `coverage.png`: accuracy when the reader only answers for its most confident signs.
* `frequency.png`: accuracy by how many training examples a sign had.
* `detection.png`: precision and recall as the detection threshold changes.

Colours follow the model (order of `models.yaml`), never its rank, and every
series is labelled directly, so the charts read in greyscale too.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# Validated categorical palette (dataviz reference instance, light surface), fixed order.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

TABLE_E2E = [("read_top1", "Read correctly (top-1)"), ("read_top3", "In top 3"),
             ("precision", "Detection precision"), ("recall", "Detection recall"), ("ap50", "AP50")]
TABLE_ID = [("id_top1", "Top-1"), ("id_top5", "Top-5"), ("id_macro_top1", "Per-sign (macro) top-1"),
            ("id_top1_bucket_1", "Signs with 1 train example"), ("id_top1_bucket_5+", "Signs with 5+"),
            ("id_ece", "Calibration error (lower is better)")]
BUCKET_LABELS = {"unseen": "unseen in training", "1": "1 example", "2-4": "2-4", "5+": "5 or more"}


def pct(x) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}%"


def cell(r: dict, key: str) -> str:
    v = r["metrics"].get(key)
    if v is None:
        return "—"
    lo, hi = r["ci95"].get(key, (None, None))
    text = pct(v) if key != "id_ece" else f"{v:.3f}"
    if lo is not None and key != "id_ece":
        text += f" ({pct(lo)}–{pct(hi)})"
    d = r.get("vs_reference", {}).get(key)
    if d:
        sign = "+" if d["diff"] >= 0 else "−"
        amount = f"{100 * abs(d['diff']):.1f}" if key != "id_ece" else f"{abs(d['diff']):.3f}"
        text += f" [{sign}{amount}, {d['verdict']}]"
    return text


def table(results: dict, rows: list[tuple[str, str]], sort_key: str, stage: str) -> list[str]:
    models = [(n, r) for n, r in results["models"].items() if "metrics" in r and r["stages"][stage]]
    models.sort(key=lambda nr: -(nr[1]["metrics"].get(sort_key) or -1))
    head = "| Model | " + " | ".join(label for _, label in rows) + " |"
    lines = [head, "|" + "---|" * (len(rows) + 1)]
    for n, r in models:
        lines.append(f"| {n} | " + " | ".join(cell(r, k) for k, _ in rows) + " |")
    return lines


def write_markdown(results: dict, out: Path) -> Path:
    ms = results["models"]
    lines = [f"# Reader benchmark — {results['split']} split, {results['tablets']} tablets",
             "",
             (f"Run `{results['stamp']}`; reference model `{results['reference']}`. Values are rates with 95% "
             f"bootstrap intervals over whole tablets ({results['resamples']} resamples). "
             "Square brackets: difference from the reference on the same resampled tablets (points), and whether "
             "its interval excludes zero (`better` / `worse`) or not (`tie`)."),
             "",
             f"## End to end (what the app shows, detection threshold {results['operating_conf']})", ""]
    lines += table(results, TABLE_E2E, "read_top1", "detection")
    lines += ["", "## Naming signs on the true boxes (identification only)", ""]
    lines += table(results, TABLE_ID, "id_top1", "identification")
    lines += ["", "## Cost", "", "| Model | Median s / tablet (CPU, 2 threads) | Weights MB | Training time |",
              "|---|---|---|---|"]
    for n, r in ms.items():
        if "metrics" not in r:
            continue
        t = r.get("train_seconds")
        lat = r.get("latency_s_median")
        lines.append(f"| {n} | {lat:.2f} | {r['weights_mb']} | {f'{t / 60:.0f} min' if t else '—'} |"
                     if lat is not None else f"| {n} | — | {r['weights_mb']} | — |")
    skipped = [f"`{n}` ({r['skipped']})" for n, r in ms.items() if "skipped" in r]
    if skipped:
        lines += ["", "Skipped: " + ", ".join(skipped)]
    first = next((r for r in ms.values() if "counts" in r), None)
    if first:
        c = first["counts"]
        lines += ["", (f"Signs on the true boxes: {c['identified_truths']} "
                  f"(unseen in training {c['bucket_unseen']}, one example {c['bucket_1']}, "
                  f"2–4 {c['bucket_2-4']}, 5+ {c['bucket_5+']}).")]
    path = out / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=12, pad=10)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def charts(results: dict, out: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ms = {n: r for n, r in results["models"].items() if "metrics" in r}
    colour = {n: SERIES[i % len(SERIES)] for i, n in enumerate(results["models"])}
    written = []

    # 1. Top-1 with intervals: two separate panels, one measure each.
    panels = [("read_top1", "detection", "Signs read correctly, end to end"),
              ("id_top1", "identification", "Signs named correctly on the true boxes")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.55 * max(3, len(ms)) + 1.6), facecolor=SURFACE)
    for ax, (key, stage, title) in zip(axes, panels):
        rows = sorted(((n, r) for n, r in ms.items() if r["stages"][stage]), key=lambda nr: nr[1]["metrics"][key])
        for y, (n, r) in enumerate(rows):
            v = r["metrics"][key]
            lo, hi = r["ci95"][key]
            ax.plot([lo * 100, hi * 100], [y, y], color=colour[n], linewidth=2, solid_capstyle="round")
            ax.plot(v * 100, y, "o", color=colour[n], markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
            ax.annotate(f"{100 * v:.1f}%", (hi * 100, y), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=9, color=INK)
        ax.set_yticks(range(len(rows)), [n for n, _ in rows])
        ax.set_xlim(0, 105)
        _style(ax, title, "% of labelled signs (dot) with 95% interval (line)")
    fig.tight_layout()
    written.append(out / "top1.png")
    fig.savefig(written[-1], dpi=200, facecolor=SURFACE)
    plt.close(fig)

    # 2. Accuracy vs coverage.
    ids = {n: r for n, r in ms.items() if r["coverage_curve"]}
    if ids:
        fig, ax = plt.subplots(figsize=(7.5, 4.5), facecolor=SURFACE)
        for n, r in ids.items():
            xs = [p["coverage"] * 100 for p in r["coverage_curve"]]
            ys = [p["id_top1"] * 100 for p in r["coverage_curve"]]
            ax.plot(xs, ys, color=colour[n], linewidth=2)
            ax.annotate(n, (xs[-1], ys[-1]), xytext=(6, 0), textcoords="offset points", va="center",
                        fontsize=9, color=INK)
        ax.set_xlim(0, 118)
        ax.set_ylim(0, 102)
        _style(ax, "Accuracy if the reader answers only for its most confident signs",
               "% of signs answered (most confident first)", "% of those named correctly")
        fig.tight_layout()
        written.append(out / "coverage.png")
        fig.savefig(written[-1], dpi=200, facecolor=SURFACE)
        plt.close(fig)

        # 3. By training frequency: grouped bars, 2px surface gaps.
        buckets = list(BUCKET_LABELS)
        fig, ax = plt.subplots(figsize=(8.5, 4.5), facecolor=SURFACE)
        width = 0.8 / len(ids)
        for i, (n, r) in enumerate(ids.items()):
            xs = [b + (i - (len(ids) - 1) / 2) * width for b in range(len(buckets))]
            ys = [100 * (r["metrics"].get(f"id_top1_bucket_{b}") or 0) for b in buckets]
            ax.bar(xs, ys, width=width, color=colour[n], edgecolor=SURFACE, linewidth=2, label=n)
        counts = next(iter(ids.values()))["counts"]
        ax.set_xticks(range(len(buckets)),
                      [f"{BUCKET_LABELS[b]}\n({counts[f'bucket_{b}']} signs)" for b in buckets])
        ax.set_ylim(0, 100)
        ax.legend(frameon=False, fontsize=9, labelcolor=INK)
        _style(ax, "Named correctly, by how many training examples the sign had", "", "% named correctly (top-1)")
        fig.tight_layout()
        written.append(out / "frequency.png")
        fig.savefig(written[-1], dpi=200, facecolor=SURFACE)
        plt.close(fig)

    # 4. Detection sweep: precision and recall as two panels (same 0-100 scale, still one measure each).
    dets = {n: r for n, r in ms.items() if r["sweep"]}
    if dets:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=SURFACE, sharey=True)
        for ax, key, title in zip(axes, ("precision", "recall"), ("Detection precision", "Detection recall")):
            for n, r in dets.items():
                xs = [p["conf"] for p in r["sweep"]]
                ys = [100 * p[key] if p[key] == p[key] else float("nan") for p in r["sweep"]]
                ax.plot(xs, ys, color=colour[n], linewidth=2, marker="o", markersize=4)
                ax.annotate(n, (xs[-1], ys[-1]), xytext=(6, 0), textcoords="offset points", va="center",
                            fontsize=9, color=INK)
            ax.axvline(results["operating_conf"], color=MUTED, linewidth=1, linestyle=":")
            ax.set_ylim(0, 102)
            ax.set_xlim(0, 1.05)
            _style(ax, title, "detection threshold (dotted: the app's)", "%")
        fig.tight_layout()
        written.append(out / "detection.png")
        fig.savefig(written[-1], dpi=200, facecolor=SURFACE)
        plt.close(fig)
    return written


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit(__doc__)
    out = Path(argv[0])
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    print(write_markdown(results, out))
    for path in charts(results, out):
        print(path)


if __name__ == "__main__":
    main()
