"""The Unicode Linear A character for a sign ID (U+10600-U+1077F)."""

import re
import unicodedata
from functools import lru_cache

# Unicode names look like "LINEAR A SIGN AB081", "LINEAR A SIGN AB131A",
# "LINEAR A SIGN A709-2 L2" or "LINEAR A SIGN A400-VAS"; sign IDs like AB01,
# AB81, AB131a, A7092 and A400. Both are reduced to one key: AB1, AB131a, A7092.
CODE = re.compile(r"(AB|A)(\d+)(?:-(\d+))?([A-Za-z]?)(?:-[A-Z]+)?")


def _key(code: str) -> str | None:
    match = CODE.fullmatch(code)
    if not match:
        return None
    prefix, number, part, variant = match.groups()
    return f"{prefix}{int(number)}{part or ''}{variant.lower()}"


@lru_cache(maxsize=1)
def _index() -> dict[str, str]:
    index = {}
    for point in range(0x10600, 0x10780):
        name = unicodedata.name(chr(point), "")
        if not name.startswith("LINEAR A SIGN "):
            continue
        key = _key(name.removeprefix("LINEAR A SIGN ").split(" ")[0])
        if key:
            index[key] = chr(point)
    return index


def glyph(sign: str | None) -> str | None:
    """The character for `sign`, or None when Unicode has none (e.g. A517, N800)."""
    key = _key(sign) if sign else None
    return _index().get(key) if key else None
