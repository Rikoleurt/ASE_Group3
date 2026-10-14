from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse
from backend.app.tablet_demo import HT13_IMAGE, annotate_ht13, ht13_predictions

router = APIRouter(prefix="/tablet-demo", tags=["tablet-demo"])
Confidence = Annotated[float, Query(gt=0, le=1, description="Minimum detection confidence (0–1).")]

@router.get("/ht13", response_class=Response)
def ht13(annotated: bool = True, confidence: Confidence = 0.25) -> Response:
    if not annotated:
        return FileResponse(HT13_IMAGE, media_type="image/webp")
    try:
        return Response(content=annotate_ht13(confidence=confidence), media_type="image/png")
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="HT13 predictions are unavailable.") from error


@router.get("/ht13/predictions")
def predictions(confidence: Confidence = 0.25) -> dict:
    try:
        return ht13_predictions(confidence=confidence)
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="HT13 predictions are unavailable.") from error
