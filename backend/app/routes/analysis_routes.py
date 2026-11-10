from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.model.analysis import SavedAnalysisResult, ApiError
from backend.app.auth import AuthenticatedWrite
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
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The sign reader is unavailable.",
        ) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Something went wrong with the image analysis",
        )

    try:
        saved = analysis_data_controller.save_analysis(user.id, filename, image_format, len(image_bytes), result)
    except DatabaseError as error:
        raise HTTPException(503, "The analysis could not be saved. Please try again.") from error
    return SavedAnalysisResult(**result.model_dump(), analysis_id=saved.id, created_at=saved.created_at)
