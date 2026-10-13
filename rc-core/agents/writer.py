"""Writer node — real LLM draft and revise.

Modes:
    - Draft: when state["critique"] is empty.
    - Revise: when state["critique"] is non-empty.

Contract: always returns {"draft": ..., "critique": ""}.
Clearing critique tells the Supervisor to route back to Critic.
"""

from prompts.templates import writer_draft, writer_revise
from tools.llm import DRAFT_MAX_TOKENS


def writer(state: dict, llm) -> dict:
    """Phase 2: real LLM writer."""
    topic = state["topic"]
    findings = state["research_findings"]
    critique = state["critique"]

    if critique:
        # Revise mode
        prompt = writer_revise(
            draft=state["draft"],
            critique=critique,
        )
    else:
        # Draft mode
        prompt = writer_draft(
            topic=topic,
            research_findings=findings,
        )

    reply = llm.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=DRAFT_MAX_TOKENS,
    )
    draft = reply.strip()
    if not draft:
        raise ValueError("Writer returned an empty draft.")

    return {"draft": draft, "critique": ""}