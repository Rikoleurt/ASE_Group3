from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, status
from fastapi.responses import FileResponse

from backend.app.data_controller.analysis_data_controller import AnalysisDataController, ImageTooLargeError
from backend.app.model.analysis import SavedAnalysisResult, ApiError
from backend.app import image_store
from backend.app.auth import AuthenticatedWrite, CurrentUser
from mysql.connector import Error as DatabaseError
from PIL import Image, UnidentifiedImageError
from PIL.PngImagePlugin import PngImageFile
from PIL.JpegImagePlugin import JpegImageFile
from io import BytesIO
import re


router = APIRouter(prefix="/analysis", tags=["analysis"])
MAX_FILESIZE = 10 * 1024 * 1024 # For now

def get_analysis_data_controller() -> AnalysisDataController:
    return AnalysisDataController()

AnalysisController = Annotated[AnalysisDataController, Depends(get_analysis_data_controller)]

@router.post("", response_model=SavedAnalysisResult, status_code=status.HTTP_200_OK,
             responses={code: {"model": ApiError} for code in (401, 403, 413, 503)})
def analyze(file: UploadFile, analysis_data_controller: AnalysisController, user: AuthenticatedWrite) -> SavedAnalysisResult:
    image_bytes = file.file.read(MAX_FILESIZE + 1)
    if len(image_bytes) > MAX_FILESIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The image is larger than 10 MB.",
        )

    # Use the two supported Pillow decoders directly. Ultralytics replaces
    # Image.open with a fallback that tries installing HEIF support on bad input.
    decoder = PngImageFile if image_bytes.startswith(b"\x89PNG\r\n\x1a\n") else JpegImageFile
    if decoder is JpegImageFile and not image_bytes.startswith(b"\xff\xd8\xff"):
        raise HTTPException(422, "Only PNG or JPEG images are supported.")
    try:
        with decoder(BytesIO(image_bytes)) as image:
            image_format = image.format
            if image.width * image.height > 40_000_000:
                raise HTTPException(422, "The image exceeds the 40 megapixel limit.")
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise HTTPException(422, "Invalid image.") from error
    filename = re.sub(r"[\x00-\x1f\x7f]", "", (file.filename or "upload").replace("\\", "/").split("/")[-1])[:255] or "upload"
    try:
        result = analysis_data_controller.analyze(
            image_bytes=image_bytes,
            filename=file.filename,
        )
    except ImageTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The image dimensions are too large.",
        ) from error
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The sign reader is unavailable.",
        ) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Something went wrong with the image analysis",
        )

    # Keep the image so the analysis can be reopened and corrected later (#81). The file is
    # written first and removed again if the database refuses the record.
    try:
        stored = image_store.save(image_bytes, image_format)
    except OSError as error:
        raise HTTPException(503, "The analysis could not be saved. Please try again.") from error
    try:
        saved = analysis_data_controller.save_analysis(user.id, filename, image_format, len(image_bytes), result,
                                                       image=stored)
    except BaseException as error:
        image_store.delete(stored.key, stored.format)
        if isinstance(error, DatabaseError):
            raise HTTPException(503, "The analysis could not be saved. Please try again.") from error
        raise
    return SavedAnalysisResult(**result.model_dump(), analysis_id=saved.id, created_at=saved.created_at)


@router.get("/{analysis_id}/image", response_class=FileResponse,
            responses={200: {"content": {"image/png": {}, "image/jpeg": {}}, "description": "The uploaded image"},
                       **{code: {"model": ApiError} for code in (401, 404, 503)}})
def analysis_image(analysis_id: Annotated[int, Path(gt=0, le=2**64 - 1)], user: CurrentUser,
                   analysis_data_controller: AnalysisController) -> FileResponse:
    """The image of one of the user's own saved analyses."""
    try:
        stored = analysis_data_controller.stored_image(user.id, analysis_id)
    except DatabaseError as error:
        raise HTTPException(503, "History storage is unavailable.") from error
    path = image_store.find(*stored) if stored else None
    if path is None:
        # Someone else's analysis, one saved before images were kept, or a file removed by hand.
        raise HTTPException(404, "Image not found.")
    # Never cached: access can be revoked once sharing exists (#84).
    return FileResponse(path, media_type=image_store.MEDIA_TYPES[stored[1]],
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
