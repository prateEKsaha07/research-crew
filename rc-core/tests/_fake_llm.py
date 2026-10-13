"""Minimal fake LLM for tests. Returns canned strings by call count."""

class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.usage = {}

    def chat(self, messages, *, temperature=0.0, max_tokens=2000):
        if self.calls >= len(self.responses):
            raise RuntimeError(
                f"FakeLLM exhausted at call {self.calls + 1}"
            )
        reply = self.responses[self.calls]
        self.calls += 1
        return reply

def test_two_threads_are_isolated(monkeypatch):
    from agents import researcher as res_mod

    def make_search():
        q = iter([
            [{"title": "t", "url": "https://x/1", "snippet": "s1"}],
            [{"title": "t", "url": "https://x/2", "snippet": "s2"}],
            [{"title": "t", "url": "https://x/3", "snippet": "s3"}],
        ])
        return lambda q_, *, max_results=3: next(q)

    monkeypatch.setattr(res_mod, "perf_counter", lambda: 0.0)

    graph_a = build_graph(_fake_llm())
    monkeypatch.setattr(res_mod, "search", make_search())
    cfg_a = {"configurable": {"thread_id": str(uuid4())}}
    graph_a.invoke(_initial_state(), cfg_a)
    snap_a = graph_a.get_state(cfg_a)

    graph_b = build_graph(_fake_llm())
    monkeypatch.setattr(res_mod, "search", make_search())
    cfg_b = {"configurable": {"thread_id": str(uuid4())}}
    graph_b.invoke(_initial_state(), cfg_b)
    snap_b = graph_b.get_state(cfg_b)

    assert snap_a.values["topic"] == "test topic"
    assert snap_b.values["topic"] == "test topic"
    assert snap_a.config["configurable"]["thread_id"] != \
           snap_b.config["configurable"]["thread_id"]