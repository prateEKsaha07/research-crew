"""Phase 1: verify MemorySaver writes a checkpoint per run."""

from uuid import uuid4

from graph.builder import build_graph


def _initial_state():
    return {
        "topic": "test topic",
        "research_findings": [],
        "draft": "",
        "critique": "",
        "confidence_scores": {},
        "revision_count": 0,
        "is_approved": False,
        "current_step": "start",
    }


def test_checkpoint_saved_after_run():
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid4())}}

    result = graph.invoke(_initial_state(), config)

    snap = graph.get_state(config)

    assert snap.values["revision_count"] == result["revision_count"]
    assert not snap.next, f"graph did not terminate: next={snap.next}"


def test_two_threads_are_isolated():
    graph = build_graph()
    cfg_a = {"configurable": {"thread_id": str(uuid4())}}
    cfg_b = {"configurable": {"thread_id": str(uuid4())}}

    graph.invoke(_initial_state(), cfg_a)
    graph.invoke(_initial_state(), cfg_b)

    snap_a = graph.get_state(cfg_a)
    snap_b = graph.get_state(cfg_b)

    assert snap_a.values["topic"] == "test topic"
    assert snap_b.values["topic"] == "test topic"
    assert snap_a.config["configurable"]["thread_id"] != \
           snap_b.config["configurable"]["thread_id"]