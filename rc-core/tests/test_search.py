"""Tests for tools.search — no live network."""

import pytest

from tools import search as search_mod
from tools.search import (
    DEFAULT_MAX_RESULTS,
    SearchUnavailableError,
    search,
)


class FakeDDGS:
    """Configurable DDGS stand-in. Ordered queue of rows or exceptions."""
    def __init__(self, queue):
        self.queue = list(queue)
        self.calls = 0

    def text(self, query, max_results=None):
        if self.calls >= len(self.queue):
            raise RuntimeError(
                f"FakeDDGS exhausted at call {self.calls + 1}"
            )
        item = self.queue[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def patch_ddgs(monkeypatch):
    def _install(queue):
        # One FakeDDGS instance is reused across retries so self.calls
        # advances the queue. search.py calls DDGS() per attempt.
        fake = FakeDDGS(queue)
        monkeypatch.setattr(search_mod, "DDGS", lambda: fake)
        monkeypatch.setattr(search_mod, "perf_counter", lambda: 0.0)
        return fake

    return _install


def test_parse_maps_fields(patch_ddgs):
    patch_ddgs([[
        {"title": "A", "href": "https://a.example/x", "body": "snip-a"},
        {"title": "B", "href": "https://b.example/y", "body": "snip-b"},
    ]])
    out = search("q")
    assert out == [
        {"title": "A", "url": "https://a.example/x", "snippet": "snip-a"},
        {"title": "B", "url": "https://b.example/y", "snippet": "snip-b"},
    ]


def test_empty_results_returns_empty_list(patch_ddgs):
    patch_ddgs([[]])
    assert search("q") == []


def test_retry_then_success(patch_ddgs):
    patch_ddgs([
        RuntimeError("boom"),
        [{"title": "A", "href": "https://a.example/x", "body": "snip"}],
    ])
    out = search("q")
    assert len(out) == 1
    assert out[0]["url"] == "https://a.example/x"


def test_both_attempts_fail_raises(patch_ddgs):
    patch_ddgs([RuntimeError("one"), RuntimeError("two")])
    with pytest.raises(SearchUnavailableError) as ei:
        search("q")
    assert len(ei.value.errors) == 2


def test_bad_url_filtered(patch_ddgs):
    patch_ddgs([[
        {"title": "bad", "href": "ftp://x", "body": "snip"},
        {"title": "ok",  "href": "https://ok.example/z", "body": "snip"},
    ]])
    out = search("q")
    assert [r["url"] for r in out] == ["https://ok.example/z"]


def test_truncate_to_max_results(patch_ddgs):
    rows = [
        {"title": str(i), "href": f"https://x/{i}", "body": f"s{i}"}
        for i in range(10)
    ]
    patch_ddgs([rows])
    out = search("q", max_results=DEFAULT_MAX_RESULTS)
    assert len(out) == DEFAULT_MAX_RESULTS


def test_no_results_exception_returns_empty(patch_ddgs):
    class _NoResults(Exception):
        pass

    patch_ddgs([_NoResults("No results found.")])
    assert search("q") == []