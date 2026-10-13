"""Researcher node — real search + LLM summaries (Phase 3).

Flow:
    1. Generate 3-5 search queries from the topic.
    2. For each query, run a web search via tools.search.
    3. Summarize the first unseen result's snippet with the LLM.
    4. Return {text, url} findings; reducer appends to state.

Budget: RESEARCH_BUDGET_S caps wall time spent between queries.
Budget check runs between queries only; one slow call can overshoot.
"""

import re
from time import perf_counter

from prompts.templates import researcher_query_gen, researcher_summarize
from tools.llm import (
    QUERY_MAX_TOKENS,
    SUMMARY_MAX_TOKENS,
)
from tools.search import (
    DEFAULT_MAX_RESULTS,
    SearchUnavailableError,
    search,
)


RESEARCH_BUDGET_S = 18


class ResearchError(Exception):
    """Raised when the researcher cannot produce any findings."""


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


def researcher(state: dict, llm) -> dict:
    """Phase 3: search + LLM summaries. Returns only new findings."""
    t0 = perf_counter()
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
        raise ResearchError(
            f"Researcher produced zero usable queries. Raw reply: {reply!r}"
        )

    # 2. Search + summarize
    findings = []
    seen_urls = set()
    for i, q in enumerate(queries):
        if perf_counter() - t0 > RESEARCH_BUDGET_S:
            print(f"[researcher] budget exceeded after {i} queries")
            break

        try:
            results = search(q, max_results=DEFAULT_MAX_RESULTS)
        except SearchUnavailableError as e:
            print(f"[researcher] search failed for query: {q!r} ({e})")
            continue

        chosen = None
        for r in results:
            if r["url"] not in seen_urls:
                chosen = r
                break
        if chosen is None:
            continue

        s_prompt = researcher_summarize(q, chosen["snippet"])
        summary = llm.chat(
            [{"role": "user", "content": s_prompt}],
            temperature=0.3,
            max_tokens=SUMMARY_MAX_TOKENS,
        )
        text = summary.strip()
        if not text:
            continue

        findings.append({"text": text, "url": chosen["url"]})
        seen_urls.add(chosen["url"])

    if not findings:
        raise ResearchError("Researcher produced zero findings.")

    return {"research_findings": findings}