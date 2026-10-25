import time
from io import BytesIO
from PIL import Image, UnidentifiedImageError

from backend.app.model.analysis import (
    AnalysisResult
)

# TODO Modify right here!
PLACEHOLDER_MEANING = "Mu"
PLACEHOLDER_CONFIDENCE = 96
PLACEHOLDER_TIME = 2.3

class AnalysisDataController:
    def analyze(self, image_bytes: bytes, filename: str | None = None) -> AnalysisResult | None:
        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
            image = image.convert("RGB")
        except (UnidentifiedImageError, OSError):
            return None
        
        # TODO: Implement analysis via a model here and return the actual response!

        return AnalysisResult(
            symbol_interpretation=PLACEHOLDER_MEANING,
            confidence=PLACEHOLDER_CONFIDENCE,
            time_taken=PLACEHOLDER_TIME
        )