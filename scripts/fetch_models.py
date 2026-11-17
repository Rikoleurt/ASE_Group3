"""Download the trained sign reader into models/ from its GitHub release.

    python scripts/fetch_models.py                  # release reader-v2
    python scripts/fetch_models.py --tag signs-v1   # the first release (detector + classifier only)

The repository is private, so a token is needed: GITHUB_TOKEN or GH_TOKEN, or
the GitHub login git already has saved (read from `git credential fill`, never
printed). Files already in models/ are kept unless --force is given.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "Rikoleurt/ASE_Group3"
ASSETS = ("linear_a_signs.pt", "linear_a_classifier.pt", "linear_a_classifier.json")
# Downloaded when the release has them: the reader refinements the app uses when present
# (scripts/build_reader.py) and the glyph pane's similarity embeddings (scripts/build_glyph_embeddings.py).
OPTIONAL = ("linear_a_reader.json", "linear_a_bank.npz", "linear_a_comparer.pt", "glyph_embeddings.npz")
MODELS = Path(__file__).resolve().parents[1] / "models"


def token() -> str | None:
    found = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if found:
        return found
    try:
        filled = subprocess.run(
            ["git", "-c", "credential.interactive=never", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n", capture_output=True, text=True, timeout=20,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return next((line.split("=", 1)[1] for line in filled.splitlines() if line.startswith("password=")), None)


def request(url: str, auth: str | None, accept: str) -> urllib.request.Request:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "ase-fetch-models"})
    if auth:
        req.add_header("Authorization", f"token {auth}")
    return req


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", default="reader-v2", help="release tag (default: reader-v2)")
    parser.add_argument("--force", action="store_true", help="download files that are already present")
    args = parser.parse_args()

    auth = token()
    try:
        with urllib.request.urlopen(request(
                f"https://api.github.com/repos/{REPO}/releases/tags/{args.tag}", auth,
                "application/vnd.github+json")) as response:
            release = json.load(response)
    except urllib.error.HTTPError as error:
        hint = " (set GITHUB_TOKEN: the repository is private)" if error.code == 404 and not auth else ""
        print(f"Cannot read release {args.tag}: HTTP {error.code}{hint}", file=sys.stderr)
        return 1

    assets = {asset["name"]: asset for asset in release["assets"]}
    missing = [name for name in ASSETS if name not in assets]
    if missing:
        print(f"Release {args.tag} lacks {', '.join(missing)}", file=sys.stderr)
        return 1

    MODELS.mkdir(exist_ok=True)
    for name in ASSETS + tuple(name for name in OPTIONAL if name in assets):
        target = MODELS / name
        if target.is_file() and not args.force:
            print(f"kept       {target.relative_to(MODELS.parent)}")
            continue
        partial = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(request(assets[name]["url"], auth, "application/octet-stream")) as response:
            partial.write_bytes(response.read())
        if partial.stat().st_size != assets[name]["size"]:
            partial.unlink()
            print(f"Download of {name} was incomplete", file=sys.stderr)
            return 1
        partial.replace(target)
        print(f"downloaded {target.relative_to(MODELS.parent)} ({assets[name]['size']:,} bytes)")
    print("Restart the backend to load the models.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
