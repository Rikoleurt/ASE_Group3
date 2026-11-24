"""Private tablet files. Only authorized API routes expose these files."""
import os
import re
from io import BytesIO
from math import ceil, floor, isfinite
from pathlib import Path
from uuid import uuid4

from PIL import Image

from backend.app.model.analysis import Box


def crop_symbol(key: str, box: Box) -> bytes:
    """Return only the saved detection's pixels as PNG, without storing a copy."""
    if not all(isfinite(value) for value in (box.x, box.y, box.w, box.h)) or box.w <= 0 or box.h <= 0:
        raise ValueError("Invalid symbol box.")
    # Uploads have already been decoded and validated before entering storage.
    with Image.open(image_path(key)) as source:
        width, height = source.size
        left = max(0, min(width, floor(box.x * width)))
        top = max(0, min(height, floor(box.y * height)))
        right = max(0, min(width, ceil((box.x + box.w) * width)))
        bottom = max(0, min(height, ceil((box.y + box.h) * height)))
        if right <= left or bottom <= top:
            raise ValueError("The symbol box is outside the tablet image.")
        output = BytesIO()
        source.crop((left, top, right, bottom)).convert("RGB").save(output, "PNG")
        return output.getvalue()


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
