"""Phase 1: verify MemorySaver writes a checkpoint per run."""

from uuid import uuid4

from graph.builder import build_graph
from tests._fake_llm import _fake_llm


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


def _make_search():
    q = iter([
        [{"title": "t", "url": "https://x/1", "snippet": "s1"}],
        [{"title": "t", "url": "https://x/2", "snippet": "s2"}],
        [{"title": "t", "url": "https://x/3", "snippet": "s3"}],
    ])
    return lambda q_, *, max_results=3: next(q)


def test_checkpoint_saved_after_run(monkeypatch):
    from agents import researcher as res_mod

    monkeypatch.setattr(res_mod, "search", _make_search())
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    graph = build_graph(_fake_llm())
    config = {"configurable": {"thread_id": str(uuid4())}}

    result = graph.invoke(_initial_state(), config)
    snap = graph.get_state(config)

    assert snap.values["revision_count"] == result["revision_count"]
    assert not snap.next, f"graph did not terminate: next={snap.next}"


def test_two_threads_are_isolated(monkeypatch):
    from agents import researcher as res_mod

    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    graph_a = build_graph(_fake_llm())
    monkeypatch.setattr(res_mod, "search", _make_search())
    cfg_a = {"configurable": {"thread_id": str(uuid4())}}
    graph_a.invoke(_initial_state(), cfg_a)
    snap_a = graph_a.get_state(cfg_a)

    graph_b = build_graph(_fake_llm())
    monkeypatch.setattr(res_mod, "search", _make_search())
    cfg_b = {"configurable": {"thread_id": str(uuid4())}}
    graph_b.invoke(_initial_state(), cfg_b)
    snap_b = graph_b.get_state(cfg_b)

    assert snap_a.values["topic"] == "test topic"
    assert snap_b.values["topic"] == "test topic"
    assert snap_a.config["configurable"]["thread_id"] != \
           snap_b.config["configurable"]["thread_id"]