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

not state["is_approved"] and revision_count < MAX_REVISIONS -> "writer"

otherwise -> "end"

text

`MAX_REVISIONS = 3` is defined in `supervisor.py` and imported by
`critic.py`.

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
**Signature:** `critic(state, llm) -> dict`

**Phase 4:** real LLM rubric.

Flow:
1. Read draft, findings, revision_count
2. `critic_score(draft, findings)` -> prompt
3. `llm.chat(temp=0.0, max_tokens=CRITIC_MAX_TOKENS)` -> raw
4. `_parse(raw)`: strip Markdown fences, `json.loads`, validate
   - top-level must be an object
   - `scores` must be an object with exactly {coverage, evidence, structure, clarity}
   - each score must be a number (bool rejected explicitly), finite, in 0..10
   - `critique` must be a str
5. On parse failure: `critic_repair(raw)` -> `llm.chat` -> parse again. On second failure: raise `CriticError`.
6. `avg = mean(4 scores)`, unrounded (7.96 stays 7.96, not 8.0)
7. `new_count = revision_count + 1`
8. Decide:
   - `avg >= 8` -> `critique="approved"`, `is_approved=True`
   - `new_count >= MAX_REVISIONS` (3) -> `critique="approved"`, `is_approved=True` (forced)
   - else -> `critique = llm_critique.strip()`; if empty or `.lower() == "approved"`, replace with a fallback naming the lowest dimension; `is_approved=False`
9. Log: `[critic] coverage=N evidence=N structure=N clarity=N avg=X.XX approved=B`
10. Return: `{confidence_scores, critique, is_approved, revision_count: new_count}`

**Contract:** `critique` is **ALWAYS non-empty** on every return path (invariant 2). Critic touches only the four keys above.

**Critique contract:**

| Outcome | `critique` | `is_approved` |
|---|---|---|
| Reject | Specific feedback, or fallback naming lowest dim | `False` |
| Approve (avg >= 8) | `"approved"` | `True` |
| Forced approve (cap hit) | `"approved"` | `True` |

Empty `critique` means only: "Critic has not run yet".

**`CriticError`** is defined in `critic.py` and caught by `cli.py`.

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