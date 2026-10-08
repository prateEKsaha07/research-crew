from typing import TypedDict, Annotated
from operator import add

class ResearchState(TypedDict):
    topic: str
    research_findings: Annotated[list[str], add]
    draft: str
    critique: str
    confidance_scores: dict
    revision_count: int
    is_approved: bool
    current_step: str