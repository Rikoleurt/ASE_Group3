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
    glyph: str | None = None  # the Unicode Linear A character, when there is one
    line: int = 0  # reading order: line, then position in the line
    order: int = 0


class Line(BaseModel):
    index: int
    sign_ids: list[int]
    text: str  # transliteration, e.g. "ku-ro J"
    gloss: str  # agreed meanings only, e.g. "total 1/2"; other words stay transliterated


class FractionTerm(BaseModel):
    id: int  # the detected sign
    sign: str
    label: str  # J, E, ...
    value: str  # "1/2"; "?" for a sign without an agreed value
    tentative: bool
    line: int


class Formula(BaseModel):
    kind: str  # total (KU-RO), grand_total (PO-TO-KU-RO) or group (fractions without a total)
    lines: list[int]
    sign_ids: list[int]
    marker_ids: list[int]  # the KU-RO signs
    box: Box  # around every sign in the formula
    entries: list[FractionTerm]
    total: list[FractionTerm]
    entries_sum: str
    total_value: str | None
    verdict: str | None  # balances, mismatch, incomplete, no_fractions; None for a group
    difference: str | None  # how far off, modulo 1
    carried: int  # whole units carried, when the fractions balance
    tentative: bool
    steps: list[str]
    note: str


class AnalysisResult(BaseModel):
    # The fields the Analysis page shows, now filled from the reader.
    symbol_interpretation: str  # the transliteration, lines separated by " / "
    confidence: int  # mean sign confidence, percent
    time_taken: float  # seconds
    summary: str  # one sentence: what was found
    # Detail for the overlay and fraction check.
    width: int
    height: int
    trained: bool  # False: the generic yolo26n.pt ran, not the Linear A reader
    signs: list[DetectedSign]  # in reading order
    lines: list[Line] = []
    formulas: list[Formula] = []
