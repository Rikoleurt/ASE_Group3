from pydantic import BaseModel
 
class AnalysisResult(BaseModel):
    symbol_interpretation: str 
    confidence: int
    time_taken: float
