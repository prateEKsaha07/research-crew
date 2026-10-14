"""Supervisor router — pure rule-based function, no LLM, no side effects.

Invoked as a LangGraph conditional edge from START and every node.
Never a node itself.
"""

from typing import Literal

from graph.state import ResearchState


MAX_REVISIONS = 3


def decide(state: ResearchState) -> Literal["researcher", "writer", "critic", "end"]:
    """Pick the next node. First matching branch wins:

    1. no research_findings                          -> "researcher"
    2. no draft                                      -> "writer"
    3. no critique (Critic has not run)              -> "critic"
    4. not is_approved and revision_count < MAX_REVISIONS -> "writer"
    5. otherwise                                     -> "end"
    """
    if not state["research_findings"]:
        return "researcher"
    if not state["draft"]:
        return "writer"
    if not state["critique"]:
        return "critic"
    if not state["is_approved"] and state["revision_count"] < MAX_REVISIONS:
        return "writer"
    return "end"