"""Tests for agents.researcher Phase 3 flow — no live network."""

import pytest

from agents import researcher as res_mod
from agents.researcher import ResearchError, researcher
from tests._fake_llm import FakeLLM
from tools.search import SearchUnavailableError


def _state(topic="q"):
    return {"topic": topic, "research_findings": []}


class SearchQueue:
    """Pops canned responses (list[dict] or Exception) per call."""
    def __init__(self, items):
        self.items = list(items)
        self.calls = 0

    def __call__(self, q, *, max_results=3):
        if self.calls >= len(self.items):
            raise RuntimeError(
                f"SearchQueue exhausted at call {self.calls + 1}"
            )
        item = self.items[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


def test_returns_dict_findings_new_only(monkeypatch):
    llm = FakeLLM(["query-a\nquery-b", "sum-a", "sum-b"])
    queue = SearchQueue([
        [{"title": "t", "url": "https://x/1", "snippet": "s"}],
        [{"title": "t", "url": "https://x/2", "snippet": "s"}],
    ])
    monkeypatch.setattr(res_mod, "search", queue)
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    out = researcher(_state(), llm)
    assert out["research_findings"] == [
        {"text": "sum-a", "url": "https://x/1"},
        {"text": "sum-b", "url": "https://x/2"},
    ]


def test_skip_failed_query_and_dedup_urls(monkeypatch):
    llm = FakeLLM(["qa\nqb\nqc", "sum-c"])
    queue = SearchQueue([
        SearchUnavailableError([RuntimeError("no")]),
        [{"title": "t", "url": "https://x/1", "snippet": "s"}],
        [{"title": "t", "url": "https://x/1", "snippet": "s"}],
    ])
    monkeypatch.setattr(res_mod, "search", queue)
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    out = researcher(_state(), llm)
    assert len(out["research_findings"]) == 1
    assert out["research_findings"][0]["url"] == "https://x/1"


def test_raise_on_zero_findings(monkeypatch):
    llm = FakeLLM(["qa"])
    monkeypatch.setattr(res_mod, "search", SearchQueue([[]]))
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)
    with pytest.raises(ResearchError):
        researcher(_state(), llm)


def test_budget_abort_partial(monkeypatch, capsys):
    llm = FakeLLM(["qa\nqb\nqc", "sum-a"])
    # t0 = 0.0, first check = 0.0, second check = 100.0 (breach)
    ticks = iter([0.0, 0.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr(res_mod, "perf_counter", lambda: next(ticks))

    queue = SearchQueue([
        [{"title": "t", "url": "https://x/1", "snippet": "s"}],
    ])
    monkeypatch.setattr(res_mod, "search", queue)

    out = researcher(_state(), llm)
    captured = capsys.readouterr().out
    assert "budget exceeded after 1 queries" in captured
    assert len(out["research_findings"]) == 1

def test_recalled_merged_and_url_deduped(monkeypatch):
    from agents import researcher as res_mod

    recalled = [
        {"text": "old fact", "url": "https://old/1", "distance": 0.10},
        {"text": "shared", "url": "https://shared/2", "distance": 0.15},
    ]
    monkeypatch.setattr(res_mod, "find_similar", lambda topic, **kw: recalled)
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    # Search returns the shared URL first, then a new one.
    queue = SearchQueue([
        [{"title": "t", "url": "https://shared/2", "snippet": "s"}],
        [{"title": "t", "url": "https://new/3", "snippet": "s"}],
    ])
    monkeypatch.setattr(res_mod, "search", queue)

    llm = FakeLLM(["qa\nqb", "sum-b"])
    out = researcher(_state(), llm)

    urls = [f["url"] for f in out["research_findings"]]
    # recalled 2 first, then only the new one (shared skipped)
    assert urls == ["https://old/1", "https://shared/2", "https://new/3"]
    # distance key stripped
    assert all("distance" not in f for f in out["research_findings"])


def test_memory_unavailable_degrades(monkeypatch):
    from agents import researcher as res_mod
    from tools.memory import MemoryUnavailableError

    def _raise(topic, **kw):
        raise MemoryUnavailableError("db down")

    monkeypatch.setattr(res_mod, "find_similar", _raise)
    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    queue = SearchQueue([
        [{"title": "t", "url": "https://x/1", "snippet": "s"}],
    ])
    monkeypatch.setattr(res_mod, "search", queue)

    llm = FakeLLM(["qa", "sum-a"])
    out = researcher(_state(), llm)
    assert [f["url"] for f in out["research_findings"]] == ["https://x/1"]