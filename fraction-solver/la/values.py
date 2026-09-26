"""Published fraction values, as versioned input with provenance.

Primary source, read and checked against the PDF:
    Corazza, Ferrara, Montecchi, Tamburini & Valerio (2021),
    "The mathematical values of fraction signs in the Linear A script:
     A computational, statistical and typological approach",
    Journal of Archaeological Science 125, 105214.
    https://doi.org/10.1016/j.jas.2020.105214  (CC BY-NC-ND)

Values below are their Table 8 ("Optimal system of mathematical values for
Linear A fractions") and Table 9 (combinations). Two of the twelve, H and A, are
printed with "(?)" in the paper and are marked tentative here.

Sign ids come from the Unicode names, which embed the conventional letter label
("LINEAR A SIGN A707 J"), so the id-to-label mapping is exact, not inferred.

Competing tables exist and disagree sharply — notably D and B (1/6 vs 1/5 are
swapped by Schrijver, Stoltenberg and Younger) and K (1/10 here vs 1/16 for
Younger, Cash & Cash and Schrijver). `ALTERNATIVE_SYSTEMS` records them so the
corpus can be asked which tablets discriminate between the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class ValueClaim:
    sign_id: str
    label: str
    value: Fraction
    source: str
    tentative: bool = False
    combination: bool = False


CORAZZA_2021 = "Corazza et al. 2021, JAS 125 105214, Table 8"
CORAZZA_2021_T9 = "Corazza et al. 2021, JAS 125 105214, Table 9 (combinations)"

CLAIMS: tuple[ValueClaim, ...] = (
    ValueClaim("A707", "J", Fraction(1, 2), CORAZZA_2021),
    ValueClaim("A704", "E", Fraction(1, 4), CORAZZA_2021),
    ValueClaim("A703", "D", Fraction(1, 6), CORAZZA_2021),
    ValueClaim("A702", "B", Fraction(1, 5), CORAZZA_2021),
    ValueClaim("A708", "K", Fraction(1, 10), CORAZZA_2021),
    ValueClaim("A7092", "L2", Fraction(1, 20), CORAZZA_2021),
    ValueClaim("A705", "F", Fraction(1, 8), CORAZZA_2021),
    ValueClaim("A706", "H", Fraction(1, 16), CORAZZA_2021, tentative=True),
    ValueClaim("A701", "A", Fraction(1, 24), CORAZZA_2021, tentative=True),
    ValueClaim("A7093", "L3", Fraction(1, 30), CORAZZA_2021),
    ValueClaim("A7094", "L4", Fraction(1, 40), CORAZZA_2021),
    ValueClaim("A7096", "L6", Fraction(1, 60), CORAZZA_2021),
    # Combination signs: one glyph standing for a sum of fractions.
    ValueClaim("A732", "JE", Fraction(3, 4), CORAZZA_2021_T9, combination=True),
    ValueClaim("A717", "DD", Fraction(1, 3), CORAZZA_2021_T9, combination=True),
    ValueClaim("A715", "BB", Fraction(2, 5), CORAZZA_2021_T9, combination=True),
)

BY_SIGN_ID: dict[str, ValueClaim] = {c.sign_id: c for c in CLAIMS}
LABELS: dict[str, str] = {c.sign_id: c.label for c in CLAIMS}

# Signs the paper leaves open: W and X (no constraints; probably BB and AA),
# Y and Omega (rare, MM II only), and L (argued not to be an independent sign).
OPEN_SIGNS: dict[str, str] = {
    "A710": "W",
    "A711": "X",
    "A712": "Y",
    "A713": "OMEGA",
    "A709": "L",
}

# Compound signs, and the parts they are written as.
#
# The corpus records these two ways. The transcription layer sometimes uses a
# single compound token (A717 = DD, 6 times) and sometimes two adjacent tokens
# (D D, 11 times) for the same thing. SigLA's tracing settles it: on HT 100 the
# transcription reads JE, while the tracing records two separate marks, J then E.
#
# Decomposing is therefore the canonical form. It also matters for the ordering
# evidence: 24 JE tokens are 24 J-before-E sequences, which stay invisible while
# the compound is treated as one sign. Corazza et al. count the JE sequence 24
# times for exactly this reason.
DECOMPOSITION: dict[str, tuple[str, ...]] = {
    "A732": ("A707", "A704"),           # JE -> J E
    "A717": ("A703", "A703"),           # DD -> D D
    "A715": ("A702", "A702"),           # BB -> B B
    "A714": ("A701", "A702", "A702"),   # ABB -> A B B
}


def decompose(sign_id: str) -> tuple[str, ...]:
    """The parts a sign is written as; itself when it is not a compound."""
    return DECOMPOSITION.get(sign_id, (sign_id,))


def decompose_all(sign_ids: list[str]) -> list[str]:
    return [part for sid in sign_ids for part in decompose(sid)]


KNOWN_VALUES: dict[str, Fraction] = {c.sign_id: c.value for c in CLAIMS}
FIRM_VALUES: dict[str, Fraction] = {c.sign_id: c.value for c in CLAIMS if not c.tentative}

# Competing published systems, for discrimination tests. Only the signs where
# they differ from Corazza et al. are listed; the rest are assumed to agree.
ALTERNATIVE_SYSTEMS: dict[str, dict[str, Fraction]] = {
    "Schrijver 2014": {
        "A703": Fraction(1, 5),   # D
        "A702": Fraction(1, 6),   # B
        "A708": Fraction(1, 16),  # K
        "A706": Fraction(1, 3),   # H
        "A701": Fraction(1, 12),  # A
    },
    "Younger 2000-2020": {
        "A708": Fraction(1, 16),  # K
        "A703": Fraction(1, 5),   # D
        "A706": Fraction(1, 6),   # H, derived from HT 123 a.7-9
        "A701": Fraction(7, 12),  # A, derived from HT 123 a.3-4 (he also floats ?1/6)
    },
    "Stoltenberg 1955": {
        "A702": Fraction(1, 6),   # B
        "A703": Fraction(1, 5),   # D
        "A706": Fraction(1, 3),   # H
        "A701": Fraction(1, 12),  # A
    },
}


def bind_to_sign_ids(id_to_reading: dict[str, str] | None = None) -> dict[str, Fraction]:
    """Kept for the earlier call sites; ids are now the key, so this is a no-op."""
    return KNOWN_VALUES


def tentative_signs() -> list[str]:
    return [c.sign_id for c in CLAIMS if c.tentative]


def describe(sign_id: str) -> str:
    claim = BY_SIGN_ID.get(sign_id)
    if claim:
        suffix = " (?)" if claim.tentative else ""
        kind = " [combination]" if claim.combination else ""
        return f"{claim.label} = {claim.value}{suffix}{kind}"
    if sign_id in OPEN_SIGNS:
        return f"{OPEN_SIGNS[sign_id]} = open (not valued in the literature)"
    return "unmapped"
