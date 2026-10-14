"""Full-graph integration tests — no live network."""

from uuid import uuid4

import pytest

from graph.builder import build_graph
from tests._fake_llm import CriticAwareFakeLLM


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


def _reject_json():
    import json
    return json.dumps({
        "scores": {"coverage": 5, "evidence": 5, "structure": 5, "clarity": 5},
        "critique": "Add more citations in Key Findings.",
    })


def test_reject_once_then_approve(monkeypatch, capsys):
    from agents import researcher as res_mod

    monkeypatch.setattr(res_mod, "search", _make_search())
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    # First critic call rejects, second approves
    llm = CriticAwareFakeLLM(critic_replies=[_reject_json()])
    graph = build_graph(llm)

    cfg = {"configurable": {"thread_id": str(uuid4())}}
    final = graph.invoke(_initial_state(), cfg)

    assert final["revision_count"] == 2
    assert final["critique"] == "approved"
    assert final["is_approved"] is True

    out = capsys.readouterr().out
    # Order: researcher, writer, critic, writer, critic
    assert out.count("[p2] researcher -> writer") == 1
    assert out.count("[p2] writer -> critic") == 2
    assert out.count("[p2] critic -> writer") == 1
    assert out.count("[p2] critic -> end") == 1


def test_always_reject_hits_cap(monkeypatch):
    from agents import researcher as res_mod

    monkeypatch.setattr(res_mod, "search", _make_search())
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    # Enough reject replies for every critic call
    llm = CriticAwareFakeLLM(critic_replies=[_reject_json() for _ in range(5)])
    graph = build_graph(llm)

    cfg = {"configurable": {"thread_id": str(uuid4())}}
    final = graph.invoke(_initial_state(), cfg)

    assert final["revision_count"] == 3
    assert final["is_approved"] is True
    assert final["critique"] == "approved"