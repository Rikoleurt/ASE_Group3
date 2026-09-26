"""Polite, resumable, cached crawler for DAMOS (Database of Mycenaean at Oslo).

Licence: DAMOS content is CC BY-NC-SA 4.0; the site software is GPL-3.0. Both are
stated in the site footer. Non-commercial research use with attribution. The cache
is local only and is never redistributed. Credit: Federico Aurora, University of
Oslo, https://damos.hf.uio.no.

The site is a React front end over two useful JSON endpoints, discovered from the
published bundle (`/dist/static/js/main.*.js`) rather than guessed:

    /ajaxitem/{id}/        one document: transliteration plus a `meta` block
    /ajaxgetfilter         corpus-wide facet counts (sites, writers, series)

Two traps, both of which cost time if you hit them the other way round:

* **The trailing slash is required.** `/ajaxitem/1` returns the React HTML shell;
  `/ajaxitem/1/` returns JSON. `/ajaxitemcontent/1` is the opposite — no slash.
* **A missing id returns the HTML shell with HTTP 200**, not a 404. Ids are sparse
  (5905 and 5920 are gaps below the maximum), so "not JSON" is the only reliable
  test for absence and must not be treated as a failure worth retrying.
* **An id past the end of the corpus returns HTTP 500** — and so does the server when it
  is unhappy about request volume. The two are indistinguishable from the response, so a
  transient 500 over a real document looks exactly like the end of the corpus. The first
  full crawl lost 160 real documents that way. Hence `known_ids`: ask the site which ids
  exist rather than scanning a range, and record failures so a re-run retries them.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://damos.hf.uio.no"
ITEM_URL = BASE + "/ajaxitem/{id}/"
FILTER_URL = BASE + "/ajaxgetfilter"

USER_AGENT = (
    "LinearB-accounting-audit/0.1 (Master's student project; "
    "non-commercial research; contact via project repository)"
)

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = ROOT / "data" / "damos"
MANIFEST_PATH = ROOT / "data" / "damos_manifest.json"

# The highest live id observed is in the 5930s; scan a little past it so a future
# addition is picked up rather than silently missed.
MAX_ID = 6000


@dataclass
class FetchStats:
    requested: int = 0
    cached: int = 0
    absent: int = 0
    failed: int = 0


def _get(url: str, timeout: float = 30.0, retries: int = 3) -> bytes:
    """GET with exponential backoff. Raises the last error if all attempts fail."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
            last = exc
            time.sleep(2**attempt)
    assert last is not None
    raise last


def cache_path(item_id: int) -> Path:
    return CACHE_DIR / f"{item_id:05d}.json"


def _as_item(raw: bytes) -> dict | None:
    """Parse a response, or None when the id does not exist.

    A missing id serves the React shell with status 200, so absence is detected by
    the payload failing to parse as JSON carrying an `item`, not by the status code.
    """
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(doc, dict) or not doc.get("item"):
        return None
    return doc


def fetch_all(
    ids: list[int] | None = None,
    delay: float = 0.3,
    force: bool = False,
    progress_every: int = 250,
) -> FetchStats:
    """Cache each DAMOS item. Resumable: existing files are kept.

    `ids` defaults to the ids the site itself lists (`known_ids`). Failures are recorded
    in `_failed.json` rather than forgotten, so re-running retries exactly those — the
    first full crawl lost 160 real documents to a burst of transient HTTP 500s, and with
    nothing written down there was no way to tell which ids needed another attempt
    without re-requesting the whole corpus.

    `legends` is dropped before writing: it is the same multi-kilobyte museum glossary on
    every record, and keeping 5,900 copies of it triples the cache for nothing.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ids = ids if ids is not None else known_ids()
    stats = FetchStats()
    absent: set[int] = set()
    failed: set[int] = set()
    total = len(ids)

    for n, item_id in enumerate(ids, 1):
        path = cache_path(item_id)
        if path.exists() and not force:
            stats.cached += 1
            continue
        try:
            doc = _as_item(_get(ITEM_URL.format(id=item_id)))
            if doc is None:
                stats.absent += 1
                absent.add(item_id)
            else:
                doc.pop("legends", None)
                path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                stats.requested += 1
        except Exception as exc:  # noqa: BLE001 - record and continue
            stats.failed += 1
            failed.add(item_id)
            print(f"  FAILED {item_id}: {exc}", flush=True)
        if n % progress_every == 0:
            print(
                f"  {n}/{total} (new {stats.requested}, cached {stats.cached}, "
                f"absent {stats.absent}, failed {stats.failed})",
                flush=True,
            )
        time.sleep(delay)

    (CACHE_DIR / "_absent.json").write_text(json.dumps(sorted(absent)), encoding="utf-8")
    (CACHE_DIR / "_failed.json").write_text(json.dumps(sorted(failed)), encoding="utf-8")
    return stats


def missing_ids(ids: list[int] | None = None) -> list[int]:
    """Listed ids with no cached file, which is what a retry should cover."""
    ids = ids if ids is not None else known_ids()
    return [i for i in ids if not cache_path(i).exists()]


def fetch_facets(force: bool = False) -> dict:
    """Corpus-wide facet counts: sites, writers (scribal hands), series, chronology."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / "_facets.json"
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    raw = _get(FILTER_URL)
    path.write_bytes(raw)
    return json.loads(raw)


def known_ids(facets: dict | None = None) -> list[int]:
    """The exact item ids the site says exist, from the `tables` facet.

    Better than scanning a range. Scanning meant ~160 requests for ids past the end of
    the corpus, and the server answers those with **HTTP 500**, not 404 — which is also
    what it returns when it is unhappy about request volume. The two are then
    indistinguishable, and a transient 500 over a real id looks exactly like the end of
    the corpus. Asking which ids exist removes the guess.
    """
    facets = facets or fetch_facets()
    ids = {row["id"] for row in (facets.get("tables") or []) if isinstance(row.get("id"), int)}
    return sorted(ids)


def write_manifest() -> dict:
    """Record what we hold, with checksums, so a rebuild is reproducible."""
    entries: dict[str, dict] = {}
    for path in sorted(CACHE_DIR.glob("[0-9]*.json")):
        data = path.read_bytes()
        entries[path.stem] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    manifest = {
        "source": BASE,
        "endpoint": ITEM_URL,
        "licence": (
            "Content CC BY-NC-SA 4.0; software GPL-3.0. "
            "Credit: DAMOS - Database of Mycenaean at Oslo, Federico Aurora, University of Oslo."
        ),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "document_count": len(entries),
        "documents": entries,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_cached() -> dict[str, dict]:
    """Every cached document, keyed by its DAMOS siglum (e.g. 'KN Fp(1) 1').

    Keyed on `heading_short` because it is the citable siglum and is stable, while
    `heading` carries join information and the scribal hand in brackets.
    """
    docs: dict[str, dict] = {}
    for path in sorted(CACHE_DIR.glob("[0-9]*.json")):
        with path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
        item = doc.get("item") or {}
        key = item.get("heading_short") or item.get("heading") or path.stem
        # Sigla are not quite unique across joins; disambiguate rather than drop.
        if key in docs:
            key = f"{key} [{path.stem}]"
        doc["_damos_id"] = int(path.stem)
        docs[key] = doc
    return docs


def main() -> None:
    print("Fetching DAMOS facet counts...")
    facets = fetch_facets()
    sites = facets.get("collections") or []
    print(f"  {len(sites)} collections, {sum(s['count'] for s in sites)} documents listed")
    print(f"  {len(facets.get('writers') or [])} writers, {len(facets.get('series') or [])} series")
    ids = known_ids(facets)
    outstanding = missing_ids(ids)
    print(f"  {len(ids)} item ids listed; {len(outstanding)} not yet cached")
    print("Fetching (resumable, ~0.3s between requests)...")
    stats = fetch_all(ids)
    print(
        f"  new {stats.requested}, already cached {stats.cached}, "
        f"absent {stats.absent}, failed {stats.failed}"
    )
    manifest = write_manifest()
    print(f"Manifest written: {manifest['document_count']} documents at {manifest['fetched_at']}")


if __name__ == "__main__":
    main()
