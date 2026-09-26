"""Linear B units of measure, as declared data with provenance.

Unlike Linear A, Linear B's metrology is solved: the ratios below are standard and
the audit can treat them as given. Three things are worth stating explicitly
because they shape everything downstream.

**The commodity sign is itself the largest unit.** `OLE 3 S 2 V 2` is three whole
units of oil plus two S plus two V, not "oil, 3, S, 2, V, 2". Palaima 2005, 268:
dry commodity ideograms "equal, as units of measure, 10 of the largest pure unit of
dry measure T (= 9.6 liters), i.e., 96 liters", while "in contrast to the dry
commodities, the convention with liquid commodities is that the substance ideogram
equals only 3 of the largest pure unit of liquid measure S (= 9.6 liters), i.e.,
28.8 liters". So the same subunit signs sit under a 10-part major unit for grain
and a 3-part one for oil, and using the wrong series silently rescales a tablet.

**Only ratios are used, never absolute volumes.** Authorities disagree on the
calibration — Palaima's dry unit is 96 litres, other tables give 120 — but they
agree on the ratios, and an audit of whether a scribe's sum matches their own total
never needs litres. Nothing here depends on the disputed absolute figures.

**The weight series has a genuinely open ratio, and that is an opportunity.**
Chadwick 1976, 102-103 gives L = 30 M and M = 4 N, but says N *probably* = 12 P,
with the doubt arising "due to the fact that we find P 12 and P 20". That is a live
question in a deciphered script, and `audit.fit_ratios` can put corpus evidence
behind it instead of assuming an answer. `WEIGHT` therefore records 12 as a
*hypothesis*, and `DISPUTED_RATIOS` names it so no result quietly rests on it.

Verification levels follow `docs/sources.md`: Read means the passage was opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Series:
    """A chain of units, largest first, with the bundling factor between each pair.

    `ratios[i]` is how many of `units[i + 1]` make one `units[i]`, so the chain
    ("UNIT", "T", "V", "Z") with ratios (10, 6, 4) means 1 UNIT = 10 T = 60 V = 240 Z.

    `UNIT` is a placeholder for whichever commodity sign heads the entry.
    """

    name: str
    units: tuple[str, ...]
    ratios: tuple[int, ...]
    source: str
    level: str = "Secondary"

    def __post_init__(self) -> None:
        if len(self.ratios) != len(self.units) - 1:
            raise ValueError(f"{self.name}: {len(self.units)} units needs {len(self.units) - 1} ratios")

    def in_smallest(self, unit: str) -> int:
        """How many of the smallest unit make one `unit`."""
        i = self.units.index(unit)
        value = 1
        for r in self.ratios[i:]:
            value *= r
        return value

    @property
    def smallest(self) -> str:
        return self.units[-1]

    def bundling_cap(self, unit: str) -> int | None:
        """The count at which a scribe should carry to the next unit up.

        Writing `V 7` where 6 V make a T is a bundling violation: the canonical form
        is `T 1 V 1`. The cap is what makes a restoration hypothesis legal or not,
        so it is the single most useful constraint in the whole recovery search.
        The largest unit has no cap — you can always write more whole units.
        """
        i = self.units.index(unit)
        if i == 0:
            return None
        return self.ratios[i - 1]


# Dry capacity. Top ratio Read (Palaima 2005, 268); subunit ratios Secondary.
DRY = Series(
    name="dry",
    units=("UNIT", "T", "V", "Z"),
    ratios=(10, 6, 4),
    source="Palaima 2005, 268 (1 unit = 10 T, Read); T = 6 V and V = 4 Z (Secondary)",
)

# Liquid capacity. Same subunits under a 3-part major unit.
LIQUID = Series(
    name="liquid",
    units=("UNIT", "S", "V", "Z"),
    ratios=(3, 6, 4),
    source="Palaima 2005, 268 (1 unit = 3 S, Read); S = 6 V and V = 4 Z (Secondary)",
)

# Weight. N:P is Chadwick's open question; P:Q is not verified here at all.
WEIGHT = Series(
    name="weight",
    units=("L", "M", "N", "P", "Q"),
    ratios=(30, 4, 12, 6),
    source="Chadwick 1976, 102-103 (L = 30 M, M = 4 N, N *probably* = 12 P); P = 6 Q Unchecked",
    level="Secondary; N:P disputed, P:Q unchecked",
)

SERIES: dict[str, Series] = {s.name: s for s in (DRY, LIQUID, WEIGHT)}

# Ratios no result may quietly depend on. Reported beside any figure that uses them.
DISPUTED_RATIOS: dict[str, str] = {
    "weight:N:P": (
        "Chadwick 1976, 102-103: N *probably* = 12 P, doubted because "
        "'we find P 12 and P 20'. Assumed 12 here; see audit.fit_ratios."
    ),
    "weight:P:Q": "Not verified from any source read for this project.",
}


# ---------------------------------------------------------------------------
# Which series a commodity belongs to
# ---------------------------------------------------------------------------

# Subunit signs are ambiguous on their own: T and S share the shape *111, and V/Z
# serve both capacity series. The commodity decides, so this map is load-bearing.
#
# Conventional assignments, from the standard transliterations. Anything absent is
# treated as uncounted rather than guessed at — a wrong series is worse than none.
DRY_COMMODITIES: frozenset[str] = frozenset({
    "GRA", "HORD", "OLIV", "KAPO", "FAR", "NI", "CYP", "PYC", "SE", "KU",
    "GRA+PE", "HORD+PE", "OLIV+A", "OLIV+TI", "CYP+PE", "CYP+O", "GRA+QA",
    "FIC", "*129", "*120", "*121", "*122", "*129+PE",
})

LIQUID_COMMODITIES: frozenset[str] = frozenset({
    "OLE", "VIN", "AREPA", "ME+RI", "MERI", "OLE+A", "OLE+PA", "OLE+WE",
    "OLE+KU", "OLE+RI", "OLE+TI", "OLE+SE", "*130", "*131", "*133", "*135",
})

WEIGHT_COMMODITIES: frozenset[str] = frozenset({
    "LANA", "AES", "AUR", "CROC", "*145", "*140", "*141", "*146", "KAPA",
    "PYC+O", "MA",
})

# Counted outright: no subunits, the numeral is a headcount. Listed so a missing
# metrogram is read as "counted" rather than as a parse failure.
COUNTED_COMMODITIES: frozenset[str] = frozenset({
    "OVIS", "OVISf", "OVISm", "CAPf", "CAPm", "CAP", "SUS", "SUSf", "SUSm",
    "BOS", "BOSf", "BOSm", "EQU", "EQUf", "EQUm", "CERV", "VIR", "MUL",
    "KO", "TA", "ZE", "MO", "PA", "ARM", "CUR", "ROTA", "TELA", "PUG",
    "*100", "*102", "*106", "*107", "*104", "*105", "*109", "*23", "*22",
})


def series_for(commodity: str | None) -> Series | None:
    """The unit series a commodity is measured in, or None when it is counted.

    Ligatures are resolved on their base sign, so `OLE+A` falls to `OLE` even when
    the exact ligature is not listed.
    """
    if not commodity:
        return None
    name = commodity.strip()
    for candidate in (name, name.split("+")[0]):
        if candidate in DRY_COMMODITIES:
            return DRY
        if candidate in LIQUID_COMMODITIES:
            return LIQUID
        if candidate in WEIGHT_COMMODITIES:
            return WEIGHT
        if candidate in COUNTED_COMMODITIES:
            return None
    return None


def is_counted(commodity: str | None) -> bool:
    """True when the commodity is known to be counted rather than measured."""
    if not commodity:
        return False
    name = commodity.strip()
    return name in COUNTED_COMMODITIES or name.split("+")[0] in COUNTED_COMMODITIES


# Every subunit sign, so the tokeniser can tell a metrogram from a logogram.
# Deliberately excludes the commodity signs, which head a quantity rather than
# subdividing it.
METROGRAMS: frozenset[str] = frozenset({"T", "V", "Z", "S", "L", "M", "N", "P", "Q"})


def metrogram_series(unit: str, series: Series | None) -> Series | None:
    """Resolve which series a subunit belongs to, given the entry's commodity.

    `T` and `S` disambiguate the capacity series on their own; `V` and `Z` do not,
    so they fall back to the commodity's series. Returning None means "cannot tell",
    and the caller must treat the quantity as unparsed rather than assume.
    """
    if unit == "T":
        return DRY
    if unit == "S":
        return LIQUID
    if unit in {"L", "M", "N", "P", "Q"}:
        return WEIGHT
    if unit in {"V", "Z"}:
        if series in (DRY, LIQUID):
            return series
        return None
    return None


def value_in_smallest(terms: list[tuple[str, int]], series: Series) -> int:
    """Total value of `(unit, count)` terms, in the series' smallest unit."""
    return sum(count * series.in_smallest(unit) for unit, count in terms)


def render(value: int, series: Series) -> str:
    """Write a value in the series' smallest unit back as a canonical sequence.

    Used to state a recovered amount the way a scribe would have, which is what
    makes a restoration checkable against the clay rather than just a number.
    """
    parts: list[str] = []
    remaining = value
    for unit in series.units:
        size = series.in_smallest(unit)
        count, remaining = divmod(remaining, size)
        if count:
            parts.append(f"{unit} {count}")
    return " ".join(parts) if parts else "0"


def as_fraction_of_unit(value: int, series: Series) -> Fraction:
    """A value expressed as a fraction of the series' largest unit.

    The bridge to the Linear A side, where quantities are fractions of a unit
    rather than counts of subunits.
    """
    return Fraction(value, series.in_smallest(series.units[0]))
