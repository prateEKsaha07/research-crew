# Prompts

**File:** `rc-core/prompts/templates.py`

Four pure string-returning functions. No LLM calls inside. No state access.

## Design Principles

- **One function per prompt.** Name matches purpose.
- **String only.** No system/user split yet. Agents wrap with `[{"role": "user", "content": prompt}]`.
- **Explicit rules blocks.** LLMs follow rules better than vague instructions.
- **No URLs from LLM.** URLs are appended by code — LLMs hallucinate URLs.
- **Keep short.** Long prompts cost tokens and dilute attention.

## Templates

### `researcher_query_gen(topic) -> str`

Produces 3–5 web search queries, one per line.
Generate 3 to 5 distinct web search queries to research this topic: {topic}

Rules:

One query per line.

No numbering, bullets, or quotes.

No preamble, no closing remarks.

Output queries only.

text

**Temperature:** 0.3 · **max_tokens:** `QUERY_MAX_TOKENS` (500)

### `researcher_summarize(query) -> str`

Produces a one-sentence finding for a query.
Write ONE factual sentence about: {query}

Rules:

One sentence only. Max 30 words.

No preamble. No URL. No citations.

Example:
Query: quantum computing RSA threat
Output: Quantum computers running Shor's algorithm could break RSA-2048 encryption within the next decade.

text

**Temperature:** 0.3 · **max_tokens:** `SUMMARY_MAX_TOKENS` (300)

**Note:** The URL is appended by code, not the LLM. Output is text only.

### `writer_draft(topic, research_findings) -> str`

Produces a 900–1400 word Markdown report.
Write a 900-1400 word report in Markdown on this topic: {topic}

Sections (exact headings, in order):

Executive Summary
Background
Key Findings
Implications
Conclusion
Citation rules:

Inline citations in Key Findings ONLY.

Use ONLY URLs from the findings below. Do not invent URLs.

Format: source where <url> is the exact URL from the findings, without angle brackets.

If a claim has no matching URL, omit the claim.

Findings (format "<text> | <url>", one per line):
{findings_block}

Output Markdown only. No preamble.

text

**Temperature:** 0.7 · **max_tokens:** `DRAFT_MAX_TOKENS` (3500)

### `writer_revise(draft, critique) -> str`

Surgical edits to address a critique.
Revise the draft below to address ONLY this critique.

Critique:
{critique}

Rules:

Keep all 5 section headings exactly.

Keep everything not related to the critique.

Do not add new sections.

Do not shorten unrelated content.

Do not change citation format.

Return full revised Markdown. No commentary.

Draft:
{draft}

text

**Temperature:** 0.7 · **max_tokens:** `DRAFT_MAX_TOKENS` (3500)

## Phase 4 Addition

### `critic_score(draft, findings) -> str`

Will return a JSON rubric:

```json
{
  "scores": {"coverage": 6, "evidence": 5, "structure": 7, "clarity": 8},
  "critique": "Add more citations in Key Findings."
}
LLM returns only scores and critique

Code computes avg and is_approved

Temperature 0.0

max_tokens CRITIC_MAX_TOKENS (800)