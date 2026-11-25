"""Download the Linear A corpus data into fraction-solver/ from its GitHub release.

    python scripts/fetch_corpus.py                 # transcriptions, scholars' boxes, tablet drawings
    python scripts/fetch_corpus.py --with-crops    # also the sign crops (glyph pane, dataset tools)

The web app's Tablets page needs the transcriptions (data/cache/), the scholars' boxes
(out/yolo_signs/annotations.json) and the tablet drawings (data/images/). They are not in git;
this fetches them from the `corpus-v1` release instead of crawling lineara.eu.

The data is CC BY-NC-SA 4.0 (lineara.eu / SigLA), not MIT: see data/LICENCE-corpus.txt after
download. The repository is private, so a token is needed: GITHUB_TOKEN or GH_TOKEN, or the
GitHub login git already has saved (read from `git credential fill`, never printed). Files
already present are kept unless --force is given. Admins can also run it from the Tablets
page's download button.
"""

import argparse
import json
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_models import REPO, request, token  # noqa: E402  (the same token handling)

TAG = "corpus-v1"
TARGET = Path(__file__).resolve().parents[1] / "fraction-solver"
ARCHIVES = ("linear_a_corpus.zip", "linear_a_tracings.zip")
CROPS = "linear_a_sign_crops.zip"
ALLOWED = ("data/", "out/yolo_signs/")  # an archive may only write here


def safe(name: str) -> bool:
    """Only plain relative paths under the allowed folders (no '..', no absolute paths)."""
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and name.startswith(ALLOWED)


def unpack(archive: Path, force: bool) -> tuple[int, int]:
    """Extract into fraction-solver/; returns (written, kept as they were)."""
    written = kept = 0
    with zipfile.ZipFile(archive) as files:
        for member in files.infolist():
            if member.is_dir():
                continue
            if not safe(member.filename):
                raise ValueError(f"Unexpected path in {archive.name}: {member.filename}")
            target = TARGET / member.filename
            if target.exists() and not force:
                kept += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(files.read(member))
            written += 1
    return written, kept


class FetchError(Exception):
    """The release could not be read or a download failed; the message says why."""


def fetch(with_crops: bool = False, force: bool = False, log=print) -> None:
    """Download and unpack the release's archives into TARGET; `log` gets each progress line.
    Also used by the web app's download button (backend/app/corpus_download.py)."""
    auth = token()
    try:
        with urllib.request.urlopen(request(
                f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}", auth,
                "application/vnd.github+json")) as response:
            release = json.load(response)
    except urllib.error.HTTPError as error:
        hint = " (set GITHUB_TOKEN: the repository is private)" if error.code == 404 and not auth else ""
        raise FetchError(f"Cannot read release {TAG}: HTTP {error.code}{hint}") from error
    except urllib.error.URLError as error:
        raise FetchError(f"Cannot reach GitHub: {error.reason}") from error

    assets = {asset["name"]: asset for asset in release["assets"]}
    wanted = ARCHIVES + ((CROPS,) if with_crops else ())
    missing = [name for name in wanted if name not in assets]
    if missing:
        raise FetchError(f"Release {TAG} lacks {', '.join(missing)}")

    with tempfile.TemporaryDirectory() as scratch:
        for name in wanted:
            asset = assets[name]
            log(f"downloading {name} ({asset['size'] / 1e6:.1f} MB)…")
            archive = Path(scratch) / name
            with urllib.request.urlopen(request(asset["url"], auth, "application/octet-stream")) as response:
                archive.write_bytes(response.read())
            if archive.stat().st_size != asset["size"]:
                raise FetchError(f"Download of {name} was incomplete")
            written, kept = unpack(archive, force)
            log(f"  unpacked {written} file(s) into fraction-solver/" + (f", kept {kept} already present" if kept else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--with-crops", action="store_true", help="also download the sign crops (16 MB)")
    parser.add_argument("--force", action="store_true", help="overwrite files that are already present")
    args = parser.parse_args()
    try:
        fetch(args.with_crops, args.force, lambda line: print(line, flush=True))
    except FetchError as error:
        print(error, file=sys.stderr)
        return 1
    print("Done. The data is CC BY-NC-SA 4.0: see fraction-solver/data/LICENCE-corpus.txt.")
    print("Restart the backend (or wait a minute) and open the Tablets page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
