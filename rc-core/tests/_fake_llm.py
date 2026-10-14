"""Fake LLMs for tests.

FakeLLM: Phase 2 call-order fake. Returns canned strings by call count.
CriticAwareFakeLLM: Phase 4 marker-dispatching fake. Routes each chat()
call to a canned reply based on a substring in the prompt.

_fake_llm(critic_replies=None) returns a CriticAwareFakeLLM with
Phase 2-shaped defaults for queries/summary/draft/revise and either
a caller-supplied critic reply queue or a default approve JSON.
"""

import json


_APPROVE_JSON = json.dumps({
    "scores": {"coverage": 9, "evidence": 9, "structure": 9, "clarity": 9},
    "critique": "approved",
})

_MARKERS = [
    ("Generate 3 to 5 distinct web search queries", "queries"),
    ("Write ONE factual sentence about:",             "summary"),
    ("Write a 900-1400 word report",                  "draft"),
    ("Revise the draft below",                        "revise"),
    ("You are a strict research-report critic",       "critic"),
    ("Your previous output was not valid JSON",       "repair"),
]


class FakeLLM:
    """Minimal fake LLM for tests. Returns canned strings by call count."""

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


class CriticAwareFakeLLM:
    """Dispatches by prompt marker. Critic replies come from a queue."""

    def __init__(self, critic_replies=None):
        self.critic_replies = list(critic_replies or [])
        self.calls = 0
        self.critic_calls = 0
        self.usage = {}
        self.seen = []  # list of category strings, in order

    def _categorize(self, prompt):
        for marker, category in _MARKERS:
            if marker in prompt:
                return category
        return "unknown"

    def chat(self, messages, *, temperature=0.0, max_tokens=2000):
        prompt = messages[0]["content"]
        category = self._categorize(prompt)
        self.seen.append(category)
        self.calls += 1

        if category == "queries":
            return "query one\nquery two\nquery three"
        if category == "summary":
            return f"Finding {self.calls}."
        if category == "draft":
            return "# Report\n\n## Executive Summary\n..."
        if category == "revise":
            return "# Report (revised)\n\n## Executive Summary\n..."
        if category == "critic":
            self.critic_calls += 1
            if self.critic_replies:
                return self.critic_replies.pop(0)
            return _APPROVE_JSON
        if category == "repair":
            return _APPROVE_JSON
        raise RuntimeError(
            f"CriticAwareFakeLLM cannot categorize prompt: {prompt[:80]!r}"
        )


def _fake_llm(critic_replies=None):
    """Phase 4 graph-driver fake. Defaults to approve on the Critic path."""
    return CriticAwareFakeLLM(critic_replies=critic_replies)