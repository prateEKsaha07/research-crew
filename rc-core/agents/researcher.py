"""Researcher node — real search + LLM summaries + vector recall (Phase 5).

Flow:
    1. Recall similar findings from pgvector (best-effort; failure
       degrades to no recall).
    2. Generate 3-5 search queries from the topic.
    3. For each query, run a web search via tools.search.
    4. Summarize the first unseen result's snippet with the LLM.
    5. Return recalled + new findings as {text, url} dicts.

Budget: RESEARCH_BUDGET_S caps wall time spent between queries AND
includes the recall call. Budget check runs between queries only;
one slow call can overshoot.
"""

import re
from time import perf_counter

from prompts.templates import researcher_query_gen, researcher_summarize
from tools.llm import (
    QUERY_MAX_TOKENS,
    SUMMARY_MAX_TOKENS,
)
from tools.memory import MemoryUnavailableError, find_similar
from tools.search import (
    DEFAULT_MAX_RESULTS,
    SearchUnavailableError,
    search,
)
from tools.tracing import span


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
    """Phase 5: recall + search + LLM summaries. Returns only new findings."""
    t0 = perf_counter()
    topic = state["topic"]

    # 1. Recall from vector memory (best-effort)
    recalled = []
    try:
        with span("memory.find_similar", topic=topic):
            recalled = find_similar(topic)
    except MemoryUnavailableError as e:
        print(f"[researcher] memory unavailable: {e}")

    # Recalled URLs must not collide with live-search picks
    seen_urls = {r["url"] for r in recalled}

    # 2. Generate queries
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

    # 3. Search + summarize
    new_findings = []
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

        new_findings.append({"text": text, "url": chosen["url"]})
        seen_urls.add(chosen["url"])

    # 4. Merge recalled + new; strip distance from recalled
    out = [{"text": r["text"], "url": r["url"]} for r in recalled] + new_findings

    if not out:
        raise ResearchError("Researcher produced zero findings.")

    return {"research_findings": out}