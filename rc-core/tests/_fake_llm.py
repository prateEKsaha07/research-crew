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