from typing import TypedDict, Annotated
from operator import add

class Finding(TypedDict):
    text: str
    url: str

class ResearchState(TypedDict):
    topic: str
    research_findings: Annotated[list[Finding], add]
    draft: str
    critique: str
    confidence_scores: dict
    revision_count: int
    is_approved: bool
    current_step: str