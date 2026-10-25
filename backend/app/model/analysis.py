from pydantic import BaseModel


class Box(BaseModel):
    """Top-left corner and size, as fractions of the image's width and height."""
    x: float
    y: float
    w: float
    h: float


class Candidate(BaseModel):
    sign: str
    label: str
    roles: list[str]
    probability: float


class DetectedSign(BaseModel):
    id: int
    sign: str | None  # sign ID (e.g. "AB81"); None from the generic, untrained model
    label: str
    reading: str | None  # e.g. "ku", "VIN", "J"; None when the sign has no agreed reading
    role: str | None  # syllabogram, logogram, fraction, transaction or unknown
    confidence: float  # percent: detector confidence times the classifier's top probability
    detection_confidence: float  # percent: the detector's part alone
    box: Box
    candidates: list[Candidate]  # the classifier's top signs, best first
    crop: str  # PNG data URL of the box
    shape_guesses: list[dict] | None = None  # fraction signs only


class AnalysisResult(BaseModel):
    # The fields the Analysis page shows, now filled from the reader.
    symbol_interpretation: str  # the most confident sign
    confidence: int  # its confidence, percent
    time_taken: float  # seconds
    summary: str  # one sentence: what was found
    # Detail for the overlay and fraction check.
    width: int
    height: int
    trained: bool  # False: the generic yolo26n.pt ran, not the Linear A reader
    signs: list[DetectedSign]
