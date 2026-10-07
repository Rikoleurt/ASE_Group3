from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from backend.app import reading

router = APIRouter(prefix="/tablets", tags=["tablet-reading"])


def _load(action, *args):
    try:
        return action(*args)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Unknown tablet.") from error
    except reading.DocumentUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="This tablet is not cached and lineara.eu could not be reached.",
        ) from error


@router.get("/{slug}/reading")
def tablet_reading(slug: str) -> dict:
    return _load(reading.reading, slug)


@router.get("/{slug}/fraction-signs")
def tablet_fraction_signs(slug: str) -> dict:
    return _load(reading.fraction_signs, slug)


@router.get("/{slug}/signs/{position}.png", response_class=FileResponse)
def tablet_sign_image(slug: str, position: int) -> FileResponse:
    path = _load(reading.sign_image, slug, position)
    if path is None:
        raise HTTPException(status_code=404, detail="Sign image not cached.")
    return FileResponse(path, media_type="image/png")
