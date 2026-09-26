"""Polite, resumable, cached crawler for the lineara.eu document corpus.

Data licence: lineara.eu per-document JSON is CC BY-NC-SA 4.0 (SigLA-derived).
Non-commercial research use with attribution. The cache is local only and is
never redistributed. Credit: SigLA (Salgarella & Castellan); lineara.eu (M. Navarre).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SITEMAP_URL = "https://lineara.eu/sitemap.xml"
DOC_URL = "https://lineara.eu/documents/{slug}/data.json"
USER_AGENT = (
    "LinearA-fraction-research/0.1 (Master's student project; "
    "non-commercial research; contact via project repository)"
)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
MANIFEST_PATH = ROOT / "data" / "manifest.json"


@dataclass
class FetchStats:
    requested: int = 0
    cached: int = 0
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


def document_slugs() -> list[str]:
    """Every document slug listed in the sitemap, in sitemap order."""
    xml = _get(SITEMAP_URL).decode("utf-8")
    slugs = re.findall(r"<loc>https://lineara\.eu/documents/([^/<]+)/</loc>", xml)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def cache_path(slug: str) -> Path:
    return CACHE_DIR / f"{slug}.json"


def fetch_all(slugs: list[str], delay: float = 0.4, force: bool = False) -> FetchStats:
    """Fetch each document's data.json into the cache. Resumable: existing files are kept."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stats = FetchStats()
    for i, slug in enumerate(slugs, 1):
        path = cache_path(slug)
        if path.exists() and not force:
            stats.cached += 1
            continue
        try:
            raw = _get(DOC_URL.format(slug=slug))
            json.loads(raw)  # validate before writing
            path.write_bytes(raw)
            stats.requested += 1
        except Exception as exc:  # noqa: BLE001 - record and continue
            stats.failed += 1
            print(f"  FAILED {slug}: {exc}")
        if i % 100 == 0:
            print(f"  {i}/{len(slugs)} (new {stats.requested}, cached {stats.cached}, failed {stats.failed})")
        time.sleep(delay)
    return stats


def write_manifest(slugs: list[str]) -> dict:
    """Record what we hold, with checksums, so a rebuild is reproducible."""
    entries = {}
    for slug in slugs:
        path = cache_path(slug)
        if not path.exists():
            continue
        data = path.read_bytes()
        entries[slug] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    manifest = {
        "source": "https://lineara.eu",
        "licence": "CC BY-NC-SA 4.0 (SigLA-derived); credit SigLA (Salgarella & Castellan) and lineara.eu (M. Navarre)",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "document_count": len(entries),
        "documents": entries,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_cached() -> dict[str, dict]:
    """Every cached document, keyed by its corpus id (e.g. 'HT 13')."""
    docs: dict[str, dict] = {}
    for path in sorted(CACHE_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
        docs[doc.get("id", path.stem)] = doc
    return docs


def main() -> None:
    print("Reading sitemap...")
    slugs = document_slugs()
    print(f"  {len(slugs)} documents listed")
    print("Fetching (resumable, ~0.4s between requests)...")
    stats = fetch_all(slugs)
    print(f"  new {stats.requested}, already cached {stats.cached}, failed {stats.failed}")
    manifest = write_manifest(slugs)
    print(f"Manifest written: {manifest['document_count']} documents at {manifest['fetched_at']}")


if __name__ == "__main__":
    main()
