"""Hand-trace tests for the Supervisor router.

Each test corresponds to one branch of decide(). Together they cover
the full router logic.
"""

from agents.supervisor import decide


def _base_state(**overrides):
    """Minimal state with sensible defaults, overridable per test."""
    state = {
        "topic": "test",
        "research_findings": [],
        "draft": "",
        "critique": "",
        "confidence_scores": {},
        "revision_count": 0,
        "is_approved": False,
        "current_step": "start",
    }
    state.update(overrides)
    return state


def test_no_findings_routes_to_researcher():
    assert decide(_base_state()) == "researcher"


def test_findings_no_draft_routes_to_writer():
    assert decide(_base_state(research_findings=["a", "b", "c"])) == "writer"


def test_draft_no_critique_routes_to_critic():
    assert decide(_base_state(
        research_findings=["a", "b", "c"],
        draft="# Report...",
    )) == "critic"


def test_approved_routes_to_end():
    assert decide(_base_state(
        research_findings=["a", "b", "c"],
        draft="# Report...",
        critique="Needs more citations",
        is_approved=True,
        revision_count=1,
    )) == "end"


def test_not_approved_within_cap_routes_to_writer():
    assert decide(_base_state(
        research_findings=["a", "b", "c"],
        draft="# Report...",
        critique="Needs more citations",
        is_approved=False,
        revision_count=1,
    )) == "writer"