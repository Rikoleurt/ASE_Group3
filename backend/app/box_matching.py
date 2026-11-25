"""Which boxes in different versions of a tablet are the same sign (workbench, stories C and D).

Each version (the scholars', the model's, a copy) is a list of boxes {id, box: {x, y, w, h},
sign} with coordinates as fractions of the tracing. Versions are taken in the order given; each
one's boxes are matched to the clusters found so far by optimal assignment on overlap
(intersection over union, at least MATCH_IOU), and boxes left over start new clusters. So a
cluster holds at most one box per version.

A cluster *agrees* when every version has a box there and they all name the same sign; it
*differs* when every version has a box but the signs disagree; it is *missing* from some
versions otherwise. It has *moved* when two of its boxes overlap less than SAME_PLACE_IOU.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

MATCH_IOU = 0.4
SAME_PLACE_IOU = 0.8


def iou(a: dict, b: dict) -> float:
    x0, y0 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x1, y1 = min(a["x"] + a["w"], b["x"] + b["w"]), min(a["y"] + a["h"], b["y"] + b["h"])
    inner = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = a["w"] * a["h"] + b["w"] * b["h"] - inner
    return inner / union if union > 0 else 0.0


def _mean(boxes: list[dict]) -> dict:
    return {name: float(np.mean([box[name] for box in boxes])) for name in ("x", "y", "w", "h")}


@dataclass
class Cluster:
    members: dict[str, dict] = field(default_factory=dict)  # version key -> box

    @property
    def box(self) -> dict:
        """Where the cluster is: the mean of its boxes."""
        return _mean([member["box"] for member in self.members.values()])

    def status(self, keys: list[str]) -> str:
        if len(self.members) < len(keys):
            return "missing"
        return (
            "agree"
            if len({member.get("sign") for member in self.members.values()}) == 1
            else "differs"
        )

    @property
    def moved(self) -> bool:
        boxes = [member["box"] for member in self.members.values()]
        return any(iou(a, b) < SAME_PLACE_IOU for i, a in enumerate(boxes) for b in boxes[i + 1 :])


def cluster(versions: dict[str, list[dict]], threshold: float = MATCH_IOU) -> list[Cluster]:
    """The clusters of matching boxes, in reading order (top to bottom by line, then left to right)."""
    clusters: list[Cluster] = []
    for key, boxes in versions.items():
        if not boxes:
            continue
        if clusters:
            score = np.array([[iou(box["box"], found.box) for found in clusters] for box in boxes])
            rows, columns = linear_sum_assignment(-score)
            matched = {
                row: column for row, column in zip(rows, columns) if score[row, column] >= threshold
            }
        else:
            matched = {}
        for index, box in enumerate(boxes):
            if index in matched:
                clusters[matched[index]].members[key] = box
            else:
                clusters.append(Cluster({key: box}))
    return reading_order(clusters)


def reading_order(clusters: list[Cluster]) -> list[Cluster]:
    """Lines first: a cluster starts a new line when its centre is below the current line's
    middle by more than half the typical box height."""
    if not clusters:
        return []
    height = float(np.median([found.box["h"] for found in clusters])) or 0.01
    ordered = sorted(clusters, key=lambda found: found.box["y"] + found.box["h"] / 2)
    lines: list[list[Cluster]] = []
    for found in ordered:
        centre = found.box["y"] + found.box["h"] / 2
        if lines and centre - _line_middle(lines[-1]) < height / 2:
            lines[-1].append(found)
        else:
            lines.append([found])
    return [found for line in lines for found in sorted(line, key=lambda c: c.box["x"])]


def _line_middle(line: list[Cluster]) -> float:
    return float(np.mean([found.box["y"] + found.box["h"] / 2 for found in line]))


def agreement(clusters: list[Cluster], a: str, b: str) -> tuple[int, int]:
    """(clusters where a and b both have a box with the same sign, clusters where either has a box)."""
    either = [found for found in clusters if a in found.members or b in found.members]
    same = sum(
        1
        for found in either
        if a in found.members
        and b in found.members
        and found.members[a].get("sign") == found.members[b].get("sign")
    )
    return same, len(either)
