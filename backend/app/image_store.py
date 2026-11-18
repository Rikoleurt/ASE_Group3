"""Uploaded images on disk (#81), so saved analyses can be reopened, edited and shared.

Files live under UPLOAD_DIR (default `var/uploads` in the repository, which git
ignores; a deployment mounts a volume there). Each file is named by a random key,
never by the user's filename, and sits in a folder named by the key's first two
characters so no folder grows too large. The database row (`uploaded_image`) keeps
the key, hash, format, size and dimensions; this module only reads and writes bytes.
"""
import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg"}
MEDIA_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg"}
KEY = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True)
class StoredImage:
    key: str
    sha256: str
    format: str
    size_bytes: int


def upload_dir() -> Path:
    return Path(os.getenv("UPLOAD_DIR") or ROOT / "var" / "uploads")


def path_for(key: str, image_format: str) -> Path:
    # The key comes from the database, but check it anyway: it becomes a file path.
    if not KEY.fullmatch(key) or image_format not in EXTENSIONS:
        raise ValueError("Not a stored image key.")
    return upload_dir() / key[:2] / f"{key}{EXTENSIONS[image_format]}"


def save(data: bytes, image_format: str) -> StoredImage:
    """Write the image under a new random key. Raises OSError if the disk refuses."""
    key = secrets.token_hex(16)
    target = path_for(key, image_format)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the target, then rename: a reader never sees half a file.
    partial = target.with_suffix(target.suffix + ".part")
    try:
        partial.write_bytes(data)
        os.replace(partial, target)
    except OSError:
        partial.unlink(missing_ok=True)
        raise
    return StoredImage(key, hashlib.sha256(data).hexdigest(), image_format, len(data))


def find(key: str, image_format: str) -> Path | None:
    """The stored file, or None if it is gone (for example, deleted by hand)."""
    path = path_for(key, image_format)
    return path if path.is_file() else None


def delete(key: str, image_format: str) -> None:
    path_for(key, image_format).unlink(missing_ok=True)
