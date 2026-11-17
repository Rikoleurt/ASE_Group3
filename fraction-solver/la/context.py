"""Choosing among a reader's top candidates with the signs around them.

The classifier names each sign alone. Linear A is formulaic: words and sign
pairs recur, logograms and fractions sit in typical places, lines start with
typical signs. A sign-pair model over transcriptions turns that into a score,
and each line is decoded jointly: the reading that best balances "what the
crop looks like" against "what usually follows what" (Viterbi over the top-k
candidates of every sign).

The pair model is trained on transcriptions only, so it can use every cached
document of the training groups, including the many with no drawing at all.
Documents of val and test groups (all faces and joined fragments) are never
used. Signs and fraction signs count; numbers, dividers and damage do not,
because the reader does not detect them.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

START = "<s>"
SIGN_KINDS = ("sign", "fraction")


def doc_lines(doc: dict) -> list[list[str]]:
    """A document's lines as lists of sign IDs (signs and fractions only), in reading order."""
    out = []
    for line in doc.get("lines", []):
        ids = [t.get("id") or "unidentified" for t in line if t.get("kind") in SIGN_KINDS]
        if ids:
            out.append(ids)
    return out


@dataclass
class PairModel:
    """Interpolated Kneser-Ney sign-pair model (absolute discount `discount`)."""
    discount: float = 0.75
    pairs: Counter = field(default_factory=Counter)
    after: Counter = field(default_factory=Counter)          # C(prev)
    followers: Counter = field(default_factory=Counter)      # N1+(prev, .)
    continuation: Counter = field(default_factory=Counter)   # N1+(., cur)
    total_types: int = 0
    vocabulary: set = field(default_factory=set)

    @classmethod
    def fit(cls, lines: Iterable[Sequence[str]], discount: float = 0.75) -> PairModel:
        model = cls(discount=discount)
        for line in lines:
            prev = START
            for sign in line:
                model.pairs[(prev, sign)] += 1
                model.vocabulary.add(sign)
                prev = sign
        for (prev, sign), n in model.pairs.items():
            model.after[prev] += n
            model.followers[prev] += 1
            model.continuation[sign] += 1
        model.total_types = len(model.pairs)
        return model

    def p_continuation(self, sign: str) -> float:
        # Add-one over the vocabulary plus one unseen slot, so a sign never seen still has mass.
        return (self.continuation[sign] + 1) / (self.total_types + len(self.vocabulary) + 1)

    def prob(self, sign: str, prev: str) -> float:
        base = self.p_continuation(sign)
        seen = self.after[prev]
        if not seen:
            return base
        pair = max(self.pairs[(prev, sign)] - self.discount, 0) / seen
        backoff = self.discount * self.followers[prev] / seen
        return pair + backoff * base

    def logprob(self, sign: str, prev: str) -> float:
        return math.log(self.prob(sign, prev))

    def association(self, sign: str, prev: str) -> float:
        """log P(sign | prev) - log P(sign): how much `prev` raises or lowers `sign`.

        The classifier already knows how common each sign is; adding the pair
        model's own frequency term would count it twice. This keeps only the
        effect of the neighbour.
        """
        return math.log(self.prob(sign, prev)) - math.log(self.p_continuation(sign))


def decode_line(candidates: list[list[tuple[str, float]]], model: PairModel, weight: float,
                floor: float = 1e-4, association: bool = True) -> list[list[tuple[str, float]]]:
    """Re-rank every sign's candidates using the whole line.

    `candidates[i]` is sign i's (sign ID, probability) list, best first. Returns
    the same candidates per sign, reordered by max-marginal score: the best
    joint score of any line reading that gives the sign that candidate
    (forward-backward Viterbi), so the top of each list is the Viterbi path and
    the rest stay ranked for top-3/top-5. Scores are returned as probabilities
    renormalised over each sign's candidates.
    """
    n = len(candidates)
    if not n or weight == 0:
        return candidates
    emit = [np.log(np.maximum([p for _, p in c], floor)) for c in candidates]
    names = [[s for s, _ in c] for c in candidates]
    pair = model.association if association else model.logprob
    trans = [None] + [np.array([[pair(b, a) for b in names[i]] for a in names[i - 1]]) * weight
                      for i in range(1, n)]
    start = np.array([pair(s, START) for s in names[0]]) * weight
    forward = [start + emit[0]]
    for i in range(1, n):
        forward.append((forward[-1][:, None] + trans[i]).max(axis=0) + emit[i])
    backward = [np.zeros(len(names[-1]))]
    for i in range(n - 1, 0, -1):
        backward.insert(0, (trans[i] + (emit[i] + backward[0])[None, :]).max(axis=1))
    out = []
    for i in range(n):
        score = forward[i] + backward[i]
        score = score - score.max()
        p = np.exp(score)
        p = p / p.sum()
        order = np.argsort(-score)
        out.append([(names[i][j], float(p[j])) for j in order])
    return out


def train_lines(docs: dict[str, dict], allowed: set[str] | None = None) -> list[list[str]]:
    """All lines of the documents whose ID is in `allowed` (all documents if None)."""
    lines = []
    for doc_id, doc in docs.items():
        if allowed is None or doc_id in allowed:
            lines.extend(doc_lines(doc))
    return lines


def split_of_documents(docs: dict[str, dict], annotations: list[dict], val_fraction: float = 0.15,
                       test_fraction: float = 0.15) -> dict[str, str]:
    """Split of every cached document, by group, consistent with the detection dataset."""
    from la.signboxes import split_for, tablet_groups
    groups = tablet_groups(docs)
    by_group = defaultdict(set)
    for t in annotations:
        by_group[t["group"]].add(t["split"])
    out = {}
    for doc_id in docs:
        group = groups.get(doc_id, doc_id)
        known = by_group.get(group)
        out[doc_id] = next(iter(known)) if known and len(known) == 1 else split_for(group, val_fraction, test_fraction)
    return out
