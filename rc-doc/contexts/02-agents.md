# Agents

Four agents. One is a router (edge function). Three are nodes.

## Supervisor

**File:** `rc-core/agents/supervisor.py`
**Type:** Edge function (pure, no LLM, no side effects)
**Signature:** `decide(state) -> Literal["researcher", "writer", "critic", "end"]`

Rule-based router. First matching branch wins:
not state["research_findings"] -> "researcher"

not state["draft"] -> "writer"

not state["critique"] -> "critic"

not state["is_approved"] and revision_count < 3 -> "writer"

otherwise -> "end"

text

**Contract:** Structural before content. Branch 3 (has Critic run?) precedes branch 4 (was it good?).

**Tests:** 8 tests in `test_supervisor.py` covering all branches, boundary at 2, cap at 3, stale-flag edge case.

## Researcher

**File:** `rc-core/agents/researcher.py`
**Type:** Node
**Signature:** `researcher(state, llm) -> dict`

**Phase 3 (current):** real ddgs search + LLM summaries.

Flow:
1. Extract topic
2. `researcher_query_gen(topic)` -> prompt
3. `llm.chat(..., temperature=0.3, max_tokens=QUERY_MAX_TOKENS)` -> queries
4. Parse: strip numbering/bullets/quotes, dedup (case-insensitive), cap 5
5. Zero usable queries -> raise `ResearchError`
6. Record `t0 = perf_counter()` at function entry
7. Per query, in order:
   - If `perf_counter() - t0 > RESEARCH_BUDGET_S` (18s): log
     "[researcher] budget exceeded after N queries" and break
   - `search(q, max_results=3)` from `tools.search`
   - `SearchUnavailableError` -> log, continue to next query
   - Pick first result whose url is not already in `seen_urls`
   - `researcher_summarize(q, chosen["snippet"])` -> prompt
   - `llm.chat(..., temperature=0.3, max_tokens=SUMMARY_MAX_TOKENS)`
   - Append `{"text": text, "url": chosen["url"]}`, add to `seen_urls`
8. Zero findings -> raise `ResearchError`
9. Return `{"research_findings": [...]}`

**Contract:** Returns **only new findings**. The `add` reducer handles
the merge. `ResearchError` is defined in `researcher.py` and caught
by `cli.py`.

**Budget:** `RESEARCH_BUDGET_S = 18`. Checked between queries only;
one slow search call can overshoot. Lowered from 25 after a Phase 3
run measured 30.8s researcher wall time.

## Writer

**File:** `rc-core/agents/writer.py`
**Type:** Node
**Signature:** `writer(state, llm) -> dict`

Modes:
- **Draft** when `state["critique"] == ""`
- **Revise** when `state["critique"] != ""`

Flow:
1. Read topic, findings, critique
2. `writer_revise(draft, critique)` OR `writer_draft(topic, findings)`
3. `llm.chat(..., temperature=0.7, max_tokens=DRAFT_MAX_TOKENS)`
4. Return `{"draft": <markdown>, "critique": ""}`

**Contract:** Always clears `critique` after writing.

## Critic

**File:** `rc-core/agents/critic.py`
**Type:** Node
**Signature:** `critic(state) -> dict` (Phase 2 stub), later `critic(state, llm)` (Phase 4)

**Phase 2:** Stub. Forces one revision cycle (reject at count 0, approve at count 1).

**Phase 4:** Real LLM rubric.

Contract:
- LLM returns `{scores: {coverage, evidence, structure, clarity}, critique}`
- Code computes `avg` and `is_approved` (avg ≥ 8 → approve)
- Cap enforcement stays in `supervisor.py`
- Malformed JSON → retry once with repair prompt → fail job
- `critique` is **ALWAYS non-empty** on every return path

**Critique contract:**

| Outcome | `critique` | `is_approved` |
|---|---|---|
| Reject | Specific feedback | `False` |
| Approve | `"approved"` | `True` |
| Forced approve (cap hit) | `"approved"` | `True` |

Empty `critique` means only: "Critic has not run yet".

## Agent Contract Invariants

1. **Writer clears critique** after producing a draft — signals "feedback consumed, re-evaluate"
2. **Critic always writes non-empty critique** — empty means "not yet critiqued"
3. **Researcher returns only new findings** — reducer handles accumulation
4. **All agents return dicts**, only touching keys they own

## State Transitions Enforced

| State | Meaning | Next |
|---|---|---|
| `critique == ""`, `draft == ""` | Nothing written | → Researcher |
| `critique == ""`, `draft != ""` | Draft fresh, un-reviewed | → Critic |
| `critique != ""`, `is_approved == False` | Rejected, revision available | → Writer |
| `critique != ""`, `is_approved == True` | Approved | → END |