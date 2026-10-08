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

def test_cap_reached_ends():
    """revision_count=3, not approved → cap forces end."""
    assert decide(_base_state(
        research_findings=["a", "b", "c"],
        draft="# Report...",
        critique="Needs more citations",
        is_approved=False,
        revision_count=3,
    )) == "end"


def test_rejected_at_count_2_goes_to_writer():
    """Boundary: revision_count=2, not approved → still routes to writer."""
    assert decide(_base_state(
        research_findings=["a", "b", "c"],
        draft="# Report...",
        critique="Needs more citations",
        is_approved=False,
        revision_count=2,
    )) == "writer"

def test_draft_without_critique_with_stale_approved_flag():
    """Structural check precedes content check: empty critique means
    Critic hasn't run, regardless of is_approved."""
    assert decide(_base_state(
        research_findings=["a", "b", "c"],
        draft="# Report...",
        critique="",
        is_approved=True,
        revision_count=0,
    )) == "critic"