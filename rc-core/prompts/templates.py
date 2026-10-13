"""Prompt templates for Research & Report Crew (Phase 2).

Pure functions: inputs in, prompt string out.
No LLM calls, no state access.
Temperature and max_tokens are chosen by the calling agent, not here.
critic_score is not defined yet (Phase 4).
"""

_QUERY_GEN = """Generate 3 to 5 distinct web search queries to research this topic: {topic}

Rules:
- One query per line.
- No numbering, bullets, or quotes.
- No preamble, no closing remarks.
- Output queries only."""

_SUMMARIZE = """Write ONE factual sentence about: {query}

Rules:
- One sentence only. Max 30 words.
- No preamble. No URL. No citations.

Example:
Query: quantum computing RSA threat
Output: Quantum computers running Shor's algorithm could break RSA-2048 encryption within the next decade."""

_DRAFT = """Write a 900-1400 word report in Markdown on this topic: {topic}

Sections (exact headings, in order):
## Executive Summary
## Background
## Key Findings
## Implications
## Conclusion

Citation rules:
- Inline citations in Key Findings ONLY.
- Use ONLY URLs from the findings below. Do not invent URLs.
- Format: [source](<url>) where <url> is the exact URL from the findings, without angle brackets.
- If a claim has no matching URL, omit the claim.

Findings (format "<text> | <url>", one per line):
{findings}

Output Markdown only. No preamble."""

_REVISE = """Revise the draft below to address ONLY this critique.

Critique:
{critique}

Rules:
- Keep all 5 section headings exactly.
- Keep everything not related to the critique.
- Do not add new sections.
- Do not shorten unrelated content.
- Do not change citation format.
- Return full revised Markdown. No commentary.

Draft:
{draft}"""


def researcher_query_gen(topic: str) -> str:
    """Build the query-generation prompt.

    Inputs: topic (str).
    Expected LLM output: 3-5 search queries, one per line, nothing else.
    """
    return _QUERY_GEN.format(topic=topic)


def researcher_summarize(query: str) -> str:
    """Build the one-sentence finding prompt.

    Inputs: query (str).
    Expected LLM output: ONE factual sentence, max 30 words, no URL.
    The URL is appended by code in agents/researcher.py, not by the LLM.
    """
    return _SUMMARIZE.format(query=query)


def writer_draft(topic: str, research_findings: list[str]) -> str:
    """Build the first-draft prompt.

    Inputs: topic (str), research_findings (list of "<text> | <url>" strings).
    Expected LLM output: 900-1400 word Markdown with the 5 exact headings,
    citations as [source](url) in Key Findings only.
    """
    return _DRAFT.format(topic=topic, findings="\n".join(research_findings))


def writer_revise(draft: str, critique: str) -> str:
    """Build the revision prompt.

    Inputs: draft (str, full Markdown), critique (str).
    Expected LLM output: the full revised Markdown, no commentary.
    """
    return _REVISE.format(draft=draft, critique=critique)