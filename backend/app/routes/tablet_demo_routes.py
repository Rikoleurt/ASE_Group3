from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from backend.app.tablet_demo import HT13_IMAGE, annotate_ht13, ht13_predictions

router = APIRouter(prefix="/tablet-demo", tags=["tablet-demo"])

@router.get("/ht13", response_class=Response)
def ht13(annotated: bool = True) -> Response:
    if not annotated:
        return FileResponse(HT13_IMAGE, media_type="image/webp")
    return Response(content=annotate_ht13(), media_type="image/png")


@router.get("/ht13/predictions")
def predictions() -> dict:
    try:
        return ht13_predictions()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="HT13 predictions are unavailable.") from error
