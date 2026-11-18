"""Private tablet files. Only authorized API routes expose these files."""
import os
import re
from pathlib import Path
from uuid import uuid4


def image_path(key: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}\.(png|jpg)", key):
        raise ValueError("Invalid image key")
    root = Path(os.getenv("TABLET_STORAGE_DIR", Path(__file__).resolve().parents[2] / "storage" / "tablets"))
    return root.resolve() / key


def store_image(content: bytes, image_format: str) -> str:
    extension = {"PNG": "png", "JPEG": "jpg"}[image_format]
    key = f"{uuid4().hex}.{extension}"
    path = image_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation must succeed before cleanup may remove this path.
    target = path.open("xb")
    try:
        with target:
            target.write(content)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return key


def remove_image(key: str) -> None:
    image_path(key).unlink(missing_ok=True)
