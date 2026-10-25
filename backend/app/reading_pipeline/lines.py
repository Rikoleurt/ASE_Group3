"""Reading order: detected signs grouped into lines, top to bottom, left to right."""

from statistics import median
from typing import Protocol, Sequence, TypeVar


class _Box(Protocol):
    x: float
    y: float
    w: float
    h: float


class _Sign(Protocol):
    box: _Box


S = TypeVar("S", bound=_Sign)

# Two signs share a line when their vertical centres are closer than this
# fraction of a typical sign's height.
SAME_LINE = 0.6


def group_lines(signs: Sequence[S]) -> list[list[S]]:
    """Signs in reading order, one list per line.

    Each sign joins the line whose average centre is nearest, if within
    SAME_LINE x the median sign height; otherwise it starts a new line. Taking
    signs top to bottom keeps slightly slanted lines together.
    """
    if not signs:
        return []
    limit = SAME_LINE * median(sign.box.h for sign in signs)
    lines: list[list[S]] = []
    centres: list[float] = []
    for sign in sorted(signs, key=_centre):
        nearest = min(range(len(lines)), key=lambda i: abs(centres[i] - _centre(sign)), default=None)
        if nearest is not None and abs(centres[nearest] - _centre(sign)) <= limit:
            lines[nearest].append(sign)
            centres[nearest] = sum(map(_centre, lines[nearest])) / len(lines[nearest])
        else:
            lines.append([sign])
            centres.append(_centre(sign))
    order = sorted(range(len(lines)), key=lambda i: centres[i])
    return [sorted(lines[i], key=lambda sign: sign.box.x) for i in order]


def _centre(sign: _Sign) -> float:
    return sign.box.y + sign.box.h / 2
