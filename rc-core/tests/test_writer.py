"""Tests for agents.writer Phase 3 draft mode — no live network."""

from agents.writer import writer
from tests._fake_llm import FakeLLM


def test_prompt_contains_exact_urls_and_clears_critique():
    captured = {}

    class CapturingLLM(FakeLLM):
        def chat(self, messages, *, temperature=0.0, max_tokens=2000):
            captured["prompt"] = messages[0]["content"]
            return super().chat(
                messages, temperature=temperature, max_tokens=max_tokens
            )

    llm = CapturingLLM(["draft body"])

    state = {
        "topic": "quantum",
        "research_findings": [
            {"text": "fact one", "url": "https://a.example/x"},
            {"text": "fact two", "url": "https://b.example/y"},
        ],
        "draft": "",
        "critique": "",
    }
    out = writer(state, llm)
    assert "https://a.example/x" in captured["prompt"]
    assert "https://b.example/y" in captured["prompt"]
    assert out["critique"] == ""
    assert out["draft"] == "draft body"