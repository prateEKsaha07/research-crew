from typing import TypedDict, Annotated
from operator import add

class Finding(TypedDict):
    text: str
    url: str

class ConfidenceScores(TypedDict, total = False):
    coverage: float
    evidance: float
    structure:float
    clarity:float
    avg:float

class ResearchState(TypedDict):
    topic: str
    research_findings: Annotated[list[Finding], add]
    draft: str
    critique: str
    confidence_scores: ConfidenceScores
    revision_count: int
    is_approved: bool
    current_step: str