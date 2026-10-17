```markdown
# Agents

Four agents. One is a router (edge function). Three are nodes.

## Supervisor

**File:** `rc-core/agents/supervisor.py`
**Type:** Edge function (pure, no LLM, no side effects)
**Signature:** `decide(state) -> Literal["researcher", "writer", "critic", "end"]`

**Why it exists:** the pipeline needs deterministic routing between nodes. Doing this with an LLM would (1) cost tokens per step, (2) be non-deterministic, (3) be untestable. A pure function is cheap, reproducible, and unit-testable.

**Objective:** given the state, return exactly one next-node name. Never touch state. Never call the LLM.

Rule-based router. First matching branch wins:
not state["research_findings"] -> "researcher"

not state["draft"] -> "writer"

not state["critique"] -> "critic"

not state["is_approved"] and revision_count < MAX_REVISIONS -> "writer"

otherwise -> "end"

text

`MAX_REVISIONS = 3` is defined in `supervisor.py` and imported by `critic.py`. Single source of truth so the cap cannot drift.

**Contract:** Structural before content. Branch 3 (has Critic run?) precedes branch 4 (was it good?).

**Tests:** 8 tests in `test_supervisor.py` covering all branches, boundary at 2, cap at 3, stale-flag edge case.

## Researcher

**File:** `rc-core/agents/researcher.py`
**Type:** Node
**Signature:** `researcher(state, llm) -> dict`

**Why it exists:** a report without real, cited evidence is fabrication. The researcher converts a free-text topic into a list of `{text, url}` findings, each URL a live source. Before searching, it recalls prior findings from vector memory so the same topic does not need to be re-researched every time.

**Objective:** produce `research_findings` that the Writer can cite, with at least one real URL, within `RESEARCH_BUDGET_S`.

**Phase 5 (current):** recall + real ddgs search + LLM summaries.

Flow:
1. Extract topic
2. Record `t0 = perf_counter()` at function entry
3. Recall from vector memory (best-effort):
   - `find_similar(topic)` inside `span("memory.find_similar", topic=...)`
   - `MemoryUnavailableError` -> log, continue without recall
   - Recalled URLs seed `seen_urls` so live search picks different results
4. `researcher_query_gen(topic)` -> prompt
5. `llm.chat(..., temperature=0.3, max_tokens=QUERY_MAX_TOKENS)` -> queries
6. Parse: strip numbering/bullets/quotes, dedup (case-insensitive), cap 5
7. Zero usable queries -> raise `ResearchError`
8. Per query, in order:
   - If `perf_counter() - t0 > RESEARCH_BUDGET_S` (18s): log
     "[researcher] budget exceeded after N queries" and break
   - `search(q, max_results=3)` from `tools.search`
   - `SearchUnavailableError` -> log, continue to next query
   - Pick first result whose url is not already in `seen_urls`
   - `researcher_summarize(q, chosen["snippet"])` -> prompt
   - `llm.chat(..., temperature=0.3, max_tokens=SUMMARY_MAX_TOKENS)`
   - Append `{"text": text, "url": chosen["url"]}`, add to `seen_urls`
9. Merge: `out = recalled_stripped + new_findings`
10. Empty `out` -> raise `ResearchError`
11. Return `{"research_findings": out}`

**Why this merge order:** recalled findings come first so the report reflects memory continuity; new findings supplement. `distance` is stripped from recalled items before returning because state does not own it (invariant 4 in `07-conventions.md`).

**Contract:** Returns **only new findings**. The `add` reducer handles
the merge. `ResearchError` is defined in `researcher.py` and caught
by `cli.py`.

**Budget:** `RESEARCH_BUDGET_S = 18`. Checked between queries only;
one slow search call can overshoot. Lowered from 25 after a Phase 3
run measured 30.8s researcher wall time. Includes the recall call.

**Tests:** 6 in `test_researcher.py` (4 from Phase 3, 2 added in Phase 5: recall merge + memory-unavailable degradation).

## Writer

**File:** `rc-core/agents/writer.py`
**Type:** Node
**Signature:** `writer(state, llm) -> dict`

**Why it exists:** the Critic reviews Markdown, not raw findings. The Writer is the only node that produces the report artifact. It is separated from the Researcher because generation is an LLM task with a different prompt, temperature, and failure mode.

**Objective:** produce a 900-1400 word Markdown report with five exact headings and inline citations drawn only from `research_findings`.

Modes:
- **Draft** when `state["critique"] == ""`
- **Revise** when `state["critique"] != ""`

Flow:
1. Read topic, findings, critique
2. `writer_revise(draft, critique)` OR `writer_draft(topic, findings)`
3. `llm.chat(..., temperature=0.7, max_tokens=DRAFT_MAX_TOKENS)`
4. Return `{"draft": <markdown>, "critique": ""}`

**Contract:** Always clears `critique` after writing. This is invariant 1: clearing the critique tells the supervisor "the feedback was consumed, evaluate again."

## Critic

**File:** `rc-core/agents/critic.py`
**Type:** Node
**Signature:** `critic(state, llm) -> dict`

**Why it exists:** the Writer's first draft is not always good. Without a quality gate, every run ships whatever the LLM produced. The Critic is the only node that decides "this is good enough" or "revise." It also produces the confidence scores the CLI prints.

**Objective:** score the draft against a four-dimension rubric, produce an actionable critique when rejected, and record the scores and revision counter for later inspection.

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

**Why temperature 0.0:** scoring must be reproducible. Higher temperature produces score drift across runs.

**Why repair once, then fail:** one retry catches the common case (LLM emits fences or a stray sentence). Two failures mean the provider is emitting junk; silently falling back to "approve" would let bad drafts through.

**Critique contract:**

| Outcome | `critique` | `is_approved` |
|---|---|---|
| Reject | Specific feedback, or fallback naming lowest dim | `False` |
| Approve (avg >= 8) | `"approved"` | `True` |
| Forced approve (cap hit) | `"approved"` | `True` |

Empty `critique` means only: "Critic has not run yet".

**`CriticError`** is defined in `critic.py` and caught by `cli.py` (exit code 2).

**Tests:** 11 in `test_critic.py`.

## Agent Contract Invariants

1. **Writer clears critique** after producing a draft — signals "feedback consumed, re-evaluate"
2. **Critic always writes non-empty critique** — empty means "not yet critiqued"
3. **Researcher returns only new findings** — reducer handles accumulation
4. **All agents return dicts**, only touching keys they own

## State Transitions Enforced

| State | Meaning | Next |
|---|---|---|
| `critique == ""`, `draft == ""` | Nothing written | -> Researcher |
| `critique == ""`, `draft != ""` | Draft fresh, un-reviewed | -> Critic |
| `critique != ""`, `is_approved == False` | Rejected, revision available | -> Writer |
| `critique != ""`, `is_approved == True` | Approved | -> END |
```

---