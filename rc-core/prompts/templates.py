"""Prompt templates for Research & Report Crew (Phase 4).

Pure functions: inputs in, prompt string out.
No LLM calls, no state access.
Temperature and max_tokens are chosen by the calling agent, not here.

Phase 3 change: researcher_summarize takes (query, snippet);
writer_draft renders list[dict] findings as "<text> | <url>".
Phase 4 change: critic_score and critic_repair added. The LLM emits
only scores and critique; code computes avg and is_approved.
"""

_QUERY_GEN = """Generate 3 to 5 distinct web search queries to research this topic: {topic}

Rules:
- One query per line.
- No numbering, bullets, or quotes.
- No preamble, no closing remarks.
- Output queries only."""

_SUMMARIZE = """Write ONE factual sentence about: {query}

Use ONLY this snippet:
{snippet}

Rules:
- One sentence only. Max 30 words.
- No preamble. No URL. No citations.

Example:
Query: quantum computing RSA threat
Snippet: Shor's algorithm can factor large integers exponentially faster than classical methods.
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

_CRITIC_SCORE = """You are a strict research-report critic. Score the DRAFT on four dimensions.

Dimensions and anchors (integer 0-10):
- coverage: 10 = all 5 sections substantive and on-topic; 5 = some sections thin or off-topic; 0 = missing or empty sections.
- evidence: 10 = every Key Findings claim has an inline citation drawn from the findings below; 5 = some claims cited, some not; 0 = no citations, or citations not drawn from the findings.
- structure: 10 = exact section headings in order, clean Markdown; 5 = minor heading or ordering issues; 0 = missing or renamed headings.
- clarity: 10 = precise, no filler, no repetition; 5 = some vague or repetitive passages; 0 = unreadable or contradictory.

Rules:
- Output ONLY a JSON object. No fences. No preamble. No commentary.
- Schema: {{"scores": {{"coverage": <int>, "evidence": <int>, "structure": <int>, "clarity": <int>}}, "critique": "<specific, actionable>"}}
- The critique MUST target the lowest-scoring dimension.
- Do NOT request new sections.
- Do NOT request a change to the citation format.
- For evidence: check that Key Findings inline citations use URLs from the findings block below.

Findings (format "<text> | <url>", one per line):
{findings_block}

DRAFT:
<<<DRAFT>>>
{draft}
<<<END_DRAFT>>>"""

_CRITIC_REPAIR = """Your previous output was not valid JSON. Return ONLY the JSON object, no fences, no preamble.

Schema:
{{"scores": {{"coverage": 0, "evidence": 0, "structure": 0, "clarity": 0}}, "critique": "..."}}

Previous output:
<<<RAW>>>
{raw_output}
<<<END_RAW>>>"""


def researcher_query_gen(topic: str) -> str:
    """Build the query-generation prompt.

    Inputs: topic (str).
    Expected LLM output: 3-5 search queries, one per line, nothing else.
    """
    return _QUERY_GEN.format(topic=topic)


def researcher_summarize(query: str, snippet: str) -> str:
    """Build the one-sentence finding prompt from a search snippet.

    Inputs: query (str), snippet (str, search result body).
    Expected LLM output: ONE factual sentence, max 30 words, no URL.
    The URL is attached by code in agents/researcher.py, not by the LLM.
    """
    return _SUMMARIZE.format(query=query, snippet=snippet)


def writer_draft(topic: str, research_findings: list[dict]) -> str:
    """Build the first-draft prompt.

    Inputs: topic (str), research_findings (list of {"text","url"} dicts).
    Expected LLM output: 900-1400 word Markdown with the 5 exact headings,
    citations as [source](url) in Key Findings only.
    """
    findings_block = "\n".join(
        f"{f['text']} | {f['url']}" for f in research_findings
    )
    return _DRAFT.format(topic=topic, findings=findings_block)


def writer_revise(draft: str, critique: str) -> str:
    """Build the revision prompt.

    Inputs: draft (str, full Markdown), critique (str).
    Expected LLM output: the full revised Markdown, no commentary.
    """
    return _REVISE.format(draft=draft, critique=critique)


def critic_score(draft: str, findings: list[dict]) -> str:
    """Build the rubric-scoring prompt for the Critic.

    Inputs: draft (str, full Markdown), findings (list of {"text","url"}).
    Expected LLM output: {"scores": {...4 int keys...}, "critique": str}.
    The LLM never computes avg or is_approved; code does.
    """
    findings_block = "\n".join(
        f"{f['text']} | {f['url']}" for f in findings
    )
    return _CRITIC_SCORE.format(
        draft=draft,
        findings_block=findings_block,
    )


def critic_repair(raw_output: str) -> str:
    """Build the single repair prompt after malformed Critic JSON.

    Inputs: raw_output (str, the LLM's non-JSON reply).
    Expected LLM output: the same JSON schema as critic_score.
    """
    return _CRITIC_REPAIR.format(raw_output=raw_output)