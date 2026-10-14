"""Critic node — real LLM rubric scoring (Phase 4).

Flow:
    1. critic_score(draft, findings) -> prompt
    2. llm.chat(temp=0.0, max_tokens=CRITIC_MAX_TOKENS) -> raw JSON
    3. Parse and validate.
       On failure: critic_repair(raw) -> llm.chat -> parse again.
       On second failure: raise CriticError.
    4. avg = mean(4 dims), unrounded.
    5. Approve if avg >= 8, or if new_count >= MAX_REVISIONS (forced).
    6. critique is ALWAYS non-empty (invariant 2).

Critic owns: confidence_scores, critique, is_approved, revision_count.
Nothing else.
"""

import json
import re

from prompts.templates import critic_score, critic_repair
from tools.llm import CRITIC_MAX_TOKENS
from agents.supervisor import MAX_REVISIONS


_DIMENSIONS = ("coverage", "evidence", "structure", "clarity")
_APPROVE_THRESHOLD = 8.0

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class CriticError(Exception):
    """Raised when the Critic cannot produce valid JSON after one repair."""


def _strip_fences(text: str) -> str:
    """Remove a single leading/trailing Markdown code fence, if present."""
    t = text.strip()
    if t.startswith("```"):
        # Drop the opening fence line
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1:]
        else:
            t = t[3:]
        # Drop trailing fence
        t = t.rstrip()
        if t.endswith("```"):
            t = t[:-3].rstrip()
    return t


def _validate(obj) -> dict:
    """Validate the parsed JSON. Returns normalized {scores, critique}.

    Raises ValueError on any structural or range violation.
    """
    if not isinstance(obj, dict):
        raise ValueError(f"top-level not an object: {type(obj).__name__}")

    scores = obj.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("missing or non-object 'scores'")

    if set(scores.keys()) != set(_DIMENSIONS):
        raise ValueError(
            f"'scores' keys must be exactly {_DIMENSIONS}, got {sorted(scores.keys())}"
        )

    clean = {}
    for k in _DIMENSIONS:
        v = scores[k]
        # bool is a subclass of int; reject explicitly
        if isinstance(v, bool):
            raise ValueError(f"score {k!r} is bool, not a number")
        if not isinstance(v, (int, float)):
            raise ValueError(f"score {k!r} is not a number: {type(v).__name__}")
        # NaN / inf guard
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"score {k!r} is non-finite: {v}")
        if not (0 <= v <= 10):
            raise ValueError(f"score {k!r} out of range 0..10: {v}")
        clean[k] = float(v)

    critique = obj.get("critique")
    if not isinstance(critique, str):
        raise ValueError(f"'critique' is not a str: {type(critique).__name__}")

    return {"scores": clean, "critique": critique}


def _parse(raw: str) -> dict:
    """Strip fences, json.loads, validate. Raises ValueError on failure."""
    cleaned = _strip_fences(raw)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"json.loads failed: {e}") from e
    return _validate(obj)


def _fallback_critique(scores: dict) -> str:
    """Name the lowest-scoring dimension when the LLM critique is unusable."""
    lowest = min(scores, key=lambda k: scores[k])
    return (
        f"Improve {lowest}: current score {scores[lowest]:.1f}. "
        f"Strengthen that dimension in the next revision."
    )


def _log(dims: dict, avg: float, approved: bool) -> None:
    print(
        f"[critic] coverage={dims['coverage']:.0f} "
        f"evidence={dims['evidence']:.0f} "
        f"structure={dims['structure']:.0f} "
        f"clarity={dims['clarity']:.0f} "
        f"avg={avg:.2f} approved={approved}"
    )


def critic(state: dict, llm) -> dict:
    """Phase 4: real LLM rubric scoring. Always returns non-empty critique."""
    draft = state["draft"]
    findings = state["research_findings"]
    revision_count = state["revision_count"]

    # 1. Primary call
    prompt = critic_score(draft, findings)
    raw = llm.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=CRITIC_MAX_TOKENS,
    )

    # 2. Parse, or repair once
    try:
        parsed = _parse(raw)
    except ValueError:
        repair_prompt = critic_repair(raw)
        raw2 = llm.chat(
            [{"role": "user", "content": repair_prompt}],
            temperature=0.0,
            max_tokens=CRITIC_MAX_TOKENS,
        )
        try:
            parsed = _parse(raw2)
        except ValueError as e:
            raise CriticError(
                f"Critic failed to produce valid JSON after repair: {e}"
            ) from e

    scores = parsed["scores"]
    llm_critique = parsed["critique"]

    # 3. Compute unrounded average
    avg = sum(scores[k] for k in _DIMENSIONS) / len(_DIMENSIONS)
    new_count = revision_count + 1

    # 4. Decide approval
    if avg >= _APPROVE_THRESHOLD:
        critique = "approved"
        approved = True
    elif new_count >= MAX_REVISIONS:
        critique = "approved"
        approved = True
    else:
        critique = llm_critique.strip()
        if not critique or critique.lower() == "approved":
            critique = _fallback_critique(scores)
        approved = False

    _log(scores, avg, approved)

    confidence_scores = {
        "coverage": scores["coverage"],
        "evidence": scores["evidence"],
        "structure": scores["structure"],
        "clarity": scores["clarity"],
        "avg": avg,
    }

    return {
        "confidence_scores": confidence_scores,
        "critique": critique,
        "is_approved": approved,
        "revision_count": new_count,
    }