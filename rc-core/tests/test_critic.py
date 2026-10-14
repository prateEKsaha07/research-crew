"""Tests for agents.critic — no live network."""

import json

import pytest

from agents.critic import CriticError, _parse, critic
from tests._fake_llm import CriticAwareFakeLLM


def _state(draft="# Report", revision_count=0, findings=None):
    return {
        "topic": "t",
        "research_findings": findings or [
            {"text": "fact one", "url": "https://a.example/x"},
            {"text": "fact two", "url": "https://b.example/y"},
        ],
        "draft": draft,
        "critique": "",
        "confidence_scores": {},
        "revision_count": revision_count,
        "is_approved": False,
        "current_step": "writer",
    }


def _scores(c, e, s, cl, critique="Needs work"):
    return json.dumps({
        "scores": {"coverage": c, "evidence": e, "structure": s, "clarity": cl},
        "critique": critique,
    })


class ScriptedCriticLLM:
    """Returns queued replies in order; falls back to approve JSON."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.usage = {}

    def chat(self, messages, *, temperature=0.0, max_tokens=2000):
        self.calls += 1
        if self.replies:
            return self.replies.pop(0)
        return _scores(9, 9, 9, 9, critique="approved")


def test_approve_path_returns_approved_critique_and_bumps_count():
    llm = ScriptedCriticLLM([_scores(9, 9, 9, 9, critique="anything")])
    out = critic(_state(revision_count=0), llm)
    assert out["critique"] == "approved"
    assert out["is_approved"] is True
    assert out["revision_count"] == 1
    assert "avg" in out["confidence_scores"]
    assert out["confidence_scores"]["avg"] == 9.0


def test_reject_path_keeps_non_empty_critique():
    llm = ScriptedCriticLLM([_scores(5, 5, 5, 5, critique="Add citations in Key Findings.")])
    out = critic(_state(revision_count=0), llm)
    assert out["is_approved"] is False
    assert out["critique"] == "Add citations in Key Findings."
    assert out["critique"] != ""


def test_boundary_exactly_8_approves():
    llm = ScriptedCriticLLM([_scores(8, 8, 8, 8, critique="meh")])
    out = critic(_state(revision_count=0), llm)
    assert out["is_approved"] is True
    assert out["critique"] == "approved"


def test_boundary_7_75_rejects():
    # 7.75 avg: (8+8+8+7)/4 = 7.75 -> reject
    llm = ScriptedCriticLLM([_scores(8, 8, 8, 7, critique="Needs more evidence.")])
    out = critic(_state(revision_count=0), llm)
    assert out["is_approved"] is False
    assert out["critique"] == "Needs more evidence."


def test_fenced_json_parses():
    fenced = "```json\n" + _scores(9, 9, 9, 9, critique="approved") + "\n```"
    llm = ScriptedCriticLLM([fenced])
    out = critic(_state(revision_count=0), llm)
    assert out["is_approved"] is True


def test_malformed_then_repair_succeeds():
    llm = ScriptedCriticLLM([
        "not json at all",
        _scores(9, 9, 9, 9, critique="approved"),
    ])
    out = critic(_state(revision_count=0), llm)
    assert out["is_approved"] is True
    assert llm.calls == 2


def test_malformed_twice_raises_critic_error():
    llm = ScriptedCriticLLM(["still not json", "also not json"])
    with pytest.raises(CriticError):
        critic(_state(revision_count=0), llm)
    assert llm.calls == 2


def test_invalid_scores_count_as_malformed():
    # missing key
    missing = json.dumps({"scores": {"coverage": 5, "evidence": 5, "structure": 5}, "critique": "x"})
    # out of range
    oor = json.dumps({"scores": {"coverage": 11, "evidence": 5, "structure": 5, "clarity": 5}, "critique": "x"})
    # bool
    boolean = json.dumps({"scores": {"coverage": True, "evidence": 5, "structure": 5, "clarity": 5}, "critique": "x"})

    good = _scores(9, 9, 9, 9, critique="approved")

    for bad in (missing, oor, boolean):
        llm = ScriptedCriticLLM([bad, good])
        out = critic(_state(revision_count=0), llm)
        assert out["is_approved"] is True
        assert llm.calls == 2


def test_empty_or_approved_critique_on_reject_is_replaced():
    # avg 5 -> reject path, but LLM gives empty critique
    empty = json.dumps({
        "scores": {"coverage": 5, "evidence": 5, "structure": 5, "clarity": 5},
        "critique": "   ",
    })
    llm = ScriptedCriticLLM([empty])
    out = critic(_state(revision_count=0), llm)
    assert out["is_approved"] is False
    assert out["critique"] != ""
    assert out["critique"].lower() != "approved"

    # "approved" on a reject path also gets replaced
    wrong = json.dumps({
        "scores": {"coverage": 5, "evidence": 5, "structure": 5, "clarity": 5},
        "critique": "approved",
    })
    llm2 = ScriptedCriticLLM([wrong])
    out2 = critic(_state(revision_count=0), llm2)
    assert out2["is_approved"] is False
    assert out2["critique"] != ""
    assert out2["critique"].lower() != "approved"


def test_forced_approve_at_cap():
    # avg 5 would normally reject, but revision_count=2 -> new_count=3 -> forced approve
    llm = ScriptedCriticLLM([_scores(5, 5, 5, 5, critique="Anything")])
    out = critic(_state(revision_count=2), llm)
    assert out["is_approved"] is True
    assert out["critique"] == "approved"
    assert out["revision_count"] == 3


def test_prompt_contains_draft_urls_and_rubric_keys():
    captured = {}

    class CapturingLLM(ScriptedCriticLLM):
        def chat(self, messages, *, temperature=0.0, max_tokens=2000):
            captured["prompt"] = messages[0]["content"]
            return super().chat(messages, temperature=temperature, max_tokens=max_tokens)

    llm = CapturingLLM([_scores(9, 9, 9, 9, critique="approved")])
    critic(_state(draft="# MyDraftBody"), llm)
    p = captured["prompt"]
    assert "# MyDraftBody" in p
    assert "https://a.example/x" in p
    assert "https://b.example/y" in p
    assert "coverage" in p
    assert "evidence" in p
    assert "structure" in p
    assert "clarity" in p