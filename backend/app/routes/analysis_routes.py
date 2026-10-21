from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from backend.app.data_controller.analysis_data_controller import AnalysisDataController
from backend.app.model.analysis import AnalysisResult


router = APIRouter(prefix="/analysis", tags=["analysis"])
MAX_FILESIZE = 10 * 1024 * 1024 # For now

def get_analysis_data_controller() -> AnalysisDataController:
    return AnalysisDataController()

AnalysisController = Annotated[AnalysisDataController, Depends(get_analysis_data_controller)]

@router.post("", response_model=AnalysisResult, status_code=status.HTTP_200_OK)
def analyze(file: UploadFile, analysis_data_controller: AnalysisController) -> AnalysisResult:
    image_bytes = file.file.read(MAX_FILESIZE + 1)
    if len(image_bytes) > MAX_FILESIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The image is larger than 10 MB.",
        )
 
    result = analysis_data_controller.analyze(
        image_bytes=image_bytes,
        filename=file.filename,
    )
 
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Something went wrong with the image analysis",
        )
 
    return result
