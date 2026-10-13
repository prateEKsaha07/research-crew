"""Researcher node — LLM-only for Phase 2.

Flow:
    1. Generate 3-5 search queries from the topic.
    2. For each query, ask the LLM for a one-sentence finding.
    3. Append a code-generated example.com URL to each finding.
    4. Return findings for the reducer to append to state.

Phase 3 will replace the URL generation with real Jiro search results.
"""

import re

from prompts.templates import researcher_query_gen, researcher_summarize
from tools.llm import (
    LLMUnavailableError,
    QUERY_MAX_TOKENS,
    SUMMARY_MAX_TOKENS,
)


# Pre-compiled regexes for query cleaning
_NUMBERING = re.compile(r"^\s*(?:\d+[\.\)\-:]|\-\s+|\*\s+|\u2022\s+)+")
_QUOTES = re.compile(r"^[\"'`]+|[\"'`]+$")


def _clean_query(line: str) -> str:
    """Strip numbering, bullets, quotes, and whitespace."""
    line = _NUMBERING.sub("", line)
    line = _QUOTES.sub("", line)
    return line.strip()


def _parse_queries(reply: str) -> list[str]:
    """Parse LLM reply into a deduped list of queries, capped at 5."""
    seen = set()
    queries = []
    for raw in reply.splitlines():
        line = _clean_query(raw)
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(line)
        if len(queries) == 5:
            break
    return queries


def _slugify(query: str) -> str:
    """Turn a query into a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    return slug or "finding"


def researcher(state: dict, llm) -> dict:
    """Phase 2: LLM-only researcher. No search, no memory."""
    topic = state["topic"]

    # 1. Generate queries
    q_prompt = researcher_query_gen(topic)
    reply = llm.chat(
        [{"role": "user", "content": q_prompt}],
        temperature=0.3,
        max_tokens=QUERY_MAX_TOKENS,
    )
    queries = _parse_queries(reply)
    if not queries:
        raise ValueError(
            f"Researcher produced zero usable queries. Raw reply: {reply!r}"
        )

    # 2. Summarize each query into a finding
    findings = []
    for query in queries:
        s_prompt = researcher_summarize(query)
        summary = llm.chat(
            [{"role": "user", "content": s_prompt}],
            temperature=0.3,
            max_tokens=SUMMARY_MAX_TOKENS,
        )
        text = summary.strip()
        if not text:
            raise ValueError(
                f"Researcher got empty summary for query: {query!r}"
            )
        slug = _slugify(query)
        findings.append(f"{text} | https://example.com/{slug}")

    # 3. Return only the new findings; reducer handles the merge
    return {"research_findings": findings}