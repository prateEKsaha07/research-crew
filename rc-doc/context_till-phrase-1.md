# Research & Report Crew — Project Context v1.5

**Last updated:** End of Phase 1
**Status:** Phase 2 ready to begin

---

## 0. Current Status

- **Phase:** 2 — Real LLM Integration (freelm)
- **Last completed:** Phase 1 — checkpoint verification merged, tagged `v0.2-checkpointing`
- **Next deliverable:** freelm client wrapper, real prompts, wire into researcher/writer/critic
- **Success check:** `python rc-core/cli.py "quantum computing"` produces an LLM-generated draft (no search yet)
- **Blockers:** none
- **Environment:** Python 3.12, Docker (pending), Jiro (Phase 3), Postgres (Phase 5)
- **Active branch:** `phase-2-real-llm`
- **Repo root:** `research-crew/`
- **Tags shipped:** `v0.1-skeleton` (Phase 0), `v0.2-checkpointing` (Phase 1)

---

## 0a. Folder Structure (LOCKED)

```
research-crew/
├── .gitignore
├── README.md
├── docker-compose.yml              # P7
├── rc-core/                        # backend
│   ├── cli.py                      # CLI entry
│   ├── requirements.txt
│   ├── .env.example                # P2
│   ├── README.md                   # (optional, not yet created)
│   ├── agents/
│   │   ├── README.md               # agent contract docs
│   │   ├── __init__.py
│   │   ├── supervisor.py           # decide() router
│   │   ├── researcher.py           # evidence gatherer
│   │   ├── writer.py               # draft producer
│   │   └── critic.py               # quality gate
│   ├── graph/
│   │   ├── README.md               # state + builder docs
│   │   ├── __init__.py
│   │   ├── state.py                # ResearchState TypedDict
│   │   └── builder.py              # StateGraph assembly + log decorator
│   ├── prompts/                    # P2
│   │   └── templates.py
│   ├── tools/                      # P3, P5
│   │   ├── search.py               # P3 (Jiro)
│   │   └── memory.py               # P5 (pgvector)
│   ├── api/                        # P6
│   │   └── main.py
│   ├── tests/
│   │   ├── test_supervisor.py      # 8 tests
│   │   └── test_checkpointing.py   # 2 tests
│   └── Dockerfile                  # P7
└── rc-web/                         # frontend (after P6)
```

**Naming rules:**
- `rc-core` = backend, `rc-web` = frontend
- CLI entry is `rc-core/cli.py` (not `main.py`) to avoid collision with `api/main.py` in P6
- All Python module paths are relative to `rc-core/`

---

## 1. Mission

Topic in → structured Markdown report out (≤30s, ≥3 real clickable citations).
Multi-agent LangGraph. Free/self-hostable stack only.
No code generation until user explicitly asks.

---

## 2. Core Agents & File Responsibilities

### `rc-core/agents/supervisor.py`

Pure rule-based router. Zero LLM calls.

```
decide(state) -> Literal["researcher", "writer", "critic", "end"]:

  1. if not state["research_findings"]                     -> "researcher"
  2. if not state["draft"]                                 -> "writer"
  3. if not state["critique"]                              -> "critic"
  4. if not state["is_approved"] and revision_count < 3    -> "writer"
  5. otherwise                                             -> "end"
```

**Contract:** Structural checks precede content checks. Branch 3 ("has the Critic run?") comes before branch 4 ("was it good?"). Reordering breaks the loop.

**Tests:** 8 tests covering every branch, boundary at `revision_count=2`, cap at `revision_count=3`, and stale-flag edge case.

### `rc-core/agents/researcher.py`

Phase 0 stub (still in place for Phase 1; replaced in Phase 2/3).

1. Query pgvector for similar past topics → inject priors (P5)
2. LLM generates 3–5 search queries (P2)
3. Parallel Jiro calls (P3)
4. Fetch + summarize top pages → list of "finding + URL" (P3)
5. Append to `research_findings` via `add` reducer

**Contract:** Returns **only new findings**, never the concatenation with prior state.

**Current stub returns:** 3 hardcoded strings in format `"<text> | <url>"`.

### `rc-core/agents/writer.py`

Input: topic + research_findings + critique (if any)
Output: 900–1400 word Markdown
Sections: Executive Summary | Background | Key Findings (inline citations) | Implications | Conclusion
Revision mode: when critique present → address feedback only.

**Contract:** Writer MUST set `critique = ""` on every return. This signals the Supervisor that the critique has been consumed and routes back to Critic for re-evaluation.

**Current stub returns:** fake Markdown with all 5 sections, 3 URLs, `(revised)` suffix when critique was present.

### `rc-core/agents/critic.py`

Input: draft + research_findings
Output: JSON `{scores: {coverage, evidence, structure, clarity}, avg, is_approved, critique}`.

Rubric 0–10 each. Avg ≥ 8 → approve. Must verify citations exist in `research_findings`.

**Contract:** `critique` is **ALWAYS non-empty** on every return path.

| Outcome | `critique` | `is_approved` |
|---|---|---|
| Reject | Specific feedback | `False` |
| Approve | `"approved"` | `True` |
| Forced approve | `"approved"` | `True` |

Empty `critique` means one thing only: **Critic has not run yet**.

**Current stub:** Forces exactly one revision cycle (reject at count 0, approve at count 1).

---

## 3. State Schema (`rc-core/graph/state.py`)

```python
from typing import Annotated, TypedDict
from operator import add


class ResearchState(TypedDict):
    topic: str
    research_findings: Annotated[list[str], add]   # append-only
    draft: str
    critique: str
    confidence_scores: dict
    revision_count: int
    is_approved: bool
    current_step: str
```

**Convention:** State keys use `snake_case`, matching the TypedDict exactly. Every producer must return a `dict` whose keys are a subset of this schema.

**The reducer:** `research_findings` uses `add` so findings accumulate across Researcher runs instead of being overwritten. Nodes must return **only new data** for this key. The reducer handles the merge.

**TODO(phase-3):** migrate `research_findings` from `list[str]` (pipe-delimited `"text | url"`) to `list[dict]` with `{text, url}` once Jiro returns structured results.

---

## 4. Graph Assembly (`rc-core/graph/builder.py`)

`StateGraph(ResearchState)`
Nodes: `researcher`, `writer`, `critic` (no `supervisor` node)
Conditional edges from `START`, `researcher`, `writer`, `critic` — all calling `decide()`
`MemorySaver` checkpointing
Entry → `supervisor` (via `START` conditional edge)

**The log decorator** wraps each node:
- Times execution
- Applies the reducer to compute the post-node state (special-cases `research_findings`)
- Calls `decide()` on that state to know the next node
- Prints: `[p0] <node> -> <next> | <reason> | <ms>ms`
- Returns the node's **original** output (not the merged state) so LangGraph applies the real update

**Success check:**
```bash
python -c "from graph.builder import build_graph; print(list(build_graph().get_graph().nodes))"
# ['__start__', 'researcher', 'writer', 'critic', '__end__']
```

---

## 5. Tools

- `rc-core/tools/search.py` — Jiro HTTP client (P3) → `POST /search` → `{title, url, snippet}`
- `rc-core/tools/memory.py` — pgvector similarity search + embed + store findings (P5)

---

## 6. Prompts (`rc-core/prompts/templates.py`)

Five templates to be authored in Phase 2:

- `researcher_query_gen` — topic → 3–5 search queries
- `researcher_summarize` — raw search results → cited findings
- `writer_draft` — topic + findings → Markdown report
- `writer_revise` — previous draft + critique → improved draft
- `critic_score` — draft + findings → JSON scores + verdict

Keep short. Structured output (JSON) required for Critic.

---

## 7. API (`rc-core/api/main.py`, P6)

- `POST /research` → `job_id` (BackgroundTasks)
- `GET /research/{id}` → status + report
- `GET /research/{id}/stream` → SSE progress
- Jobs stored in Postgres.

---

## 8. Stack Constraints (never violate)

- **LLM:** `freelm` only (OpenRouter → Google AI Studio → Groq → others)
- **Search:** Jiro self-hosted
- **Memory:** PostgreSQL + pgvector (no separate vector DB)
- **Obs:** feenion (local)
- **Backend:** FastAPI + Uvicorn
- **Deploy:** Docker Compose first, K8s later
- **No paid APIs, no cloud vector DBs, no proprietary locked models.**

---

## 9. Data Flow (target timings)

```
T+0.0  submit topic
T+0.1  return job_id
T+0.2  supervisor → researcher
T+1-4  Jiro parallel + summarize
T+4.1  → writer
T+10   draft ready
T+10.1 → critic
T+12   score / revise (max 3)
T+20-30 approved → save to DB + pgvector → completed
```

---

## 10. Implementation Phases (strict order)

- **0** — Walking skeleton (fake nodes, end-to-end print) — ✅ **DONE**, tagged `v0.1-skeleton`
- **1** — Real supervisor routing + MemorySaver verification — ✅ **DONE**, tagged `v0.2-checkpointing`
- **2** — freelm wired (Researcher LLM-only first) — 🚧 **NEXT**
- **3** — Jiro real search + real citations
- **4** — Critic loop + revision_count cap (real scoring)
- **5** — feenion traces + pgvector memory
- **6** — FastAPI + SSE
- **7** — Docker Compose
- **8** — Kubernetes (optional)

Each phase must be runnable + git-committable before next.

### 10a. Testing Expectations

- Phase 0–2: manual run + console output acceptable
- Phase 3+: unit test per agent (input → expected shape of output)
- Phase 4+: integration test of full graph (mock LLM)
- Phase 6+: API test via httpx

**Current state:** 10 tests passing (`test_supervisor.py` × 8, `test_checkpointing.py` × 2)

### 10b. Git Convention

- One branch per phase: `phase-N-slug`
- Merge to `main` when phase passes acceptance
- Tag on merge: `v0.N-slug` (e.g., `v0.1-skeleton`, `v0.2-checkpointing`)
- Commit message format: `phase-N: what changed`

---

## 11. Design Decisions

- **Supervisor pattern > peer-to-peer** — easier to debug, extend, log
- **Rule routing > LLM routing** — deterministic, cheap, testable
- **Hard revision cap = 3** — protects free LLM quotas from runaway loops
- **pgvector inside Postgres** — one database, one transaction
- **SSE > WebSockets** — simpler, one-way, proxy-friendly
- **Citations validated against state** — prevents hallucination at Critic stage

### 11a. Error Handling Philosophy

- LLM failure → freelm failover chain; if all fail, job fails with clear error
- Search failure → retry once, then proceed with fewer findings (no crash)
- Citation missing → Critic flags, Writer revision required
- Never silently degrade: all failures logged with `job_id`

---

## 12. Acceptance (PoC done when)

- API accepts topic
- Returns Markdown with ≥3 real clickable citations in ≤30s
- Full feenion trace visible
- `docker compose up` works
- Similar second topic shows memory recall
- Phases 0–7 merged + tagged `v1.0-poc`

---

## 13. Risks

- Free LLM 429 → freelm failover + `persist=True`
- Infinite loop → `revision_count` hard stop
- Bad search → multi-query + Jiro fallback
- Fake citations → Critic checks against `research_findings`
- Volume loss → named Docker volumes / PVC

---

## 14. Response Rules for AI (this project)

- Always name the exact file/path you are discussing
- Prefer pseudo-code, decision trees, checklists, atomic next steps
- **NEVER emit full source code or complete files unless user says "write code" / "implement" / "generate"**
- If user asks for code without those exact trigger words → reply with pseudo-code only and ask for confirmation
- Stay inside current phase unless asked to jump
- Token-efficient. No filler.
- When ambiguous, ask which phase we are in before answering

---

## 15. Console Log Format (for debugging)

Each node transition prints one line:

```
[p0] <node> -> <next> | <reason> | <ms>ms
```

Example (Phase 1 verified output):

```
[p0] researcher -> writer | 3 findings appended | 0ms
[p0] writer -> critic | draft 639 chars | 0ms
[p0] critic -> writer | score=6.5, revision requested | 0ms
[p0] writer -> critic | draft 649 chars | 0ms
[p0] critic -> end | score=8.5, approved | 0ms
[checkpoint] thread=<uuid>
[checkpoint] revision_count=2 next=()
```

The format stays consistent across phases; feenion replaces the print sink in Phase 5.

**Note:** ASCII-only (`->` not `→`, `-` not `─`) for Windows PowerShell compatibility.

---

## 16. Contracts (Invariants That Keep the Loop Well-Defined)

Three invariants. Break any one and the graph either spins forever or terminates early.

| # | Invariant | Owner | Why |
|---|---|---|---|
| 1 | Writer clears `critique` after producing a draft | `writer.py` | Signals "feedback consumed, re-evaluate" |
| 2 | Critic always writes non-empty `critique` | `critic.py` | Empty means "not yet critiqued" — never valid post-critique |
| 3 | Supervisor reads only presence/absence of `critique` | `supervisor.py` | Structural check before content check |

**State transitions the contracts enforce:**

| State | Meaning | Next |
|---|---|---|
| `critique == ""`, `draft == ""` | Nothing written | → Researcher |
| `critique == ""`, `draft != ""` | Draft fresh, un-reviewed | → Critic |
| `critique != ""`, `is_approved == False` | Rejected, revision available | → Writer |
| `critique != ""`, `is_approved == True` | Approved | → END |

Every row is distinguishable. That's the whole point.

---

## 17. Tooling Reference

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12.2 | Runtime |
| pytest | 9.1.1 | Test runner |
| langgraph | (pinned in `requirements.txt`) | Graph orchestration |
| langchain-core | (pinned) | LLM abstractions (used P2+) |
| freelm | (to install P2) | Multi-provider LLM failover |
| Jiro | (to install P3) | Self-hosted search |

---

## 18. Known Limitations (at end of Phase 1)

| Limitation | Phase to address |
|---|---|
| `MemorySaver` is in-process — no resume across processes | Phase 6 |
| Each CLI run uses `uuid4` — no resume of prior runs | Phase 6 |
| `research_findings` are pipe-delimited strings | Phase 3 (migrate to `list[dict]`) |
| Agents return hardcoded data, no LLM | Phase 2 |
| No observability integration | Phase 5 |
| No Docker / K8s | Phase 7 / 8 |

---

## 19. Shipped Artifacts

| Tag | Phase | Deliverable |
|---|---|---|
| `v0.1-skeleton` | 0 | Walking skeleton — full pipeline runs with fake data |
| `v0.2-checkpointing` | 1 | Verified routing + MemorySaver persistence |

**Repo state:** clean, tests green (10/10), README + agents README + graph README in place.

---

## 20. Phase 2 Preview (design-first)

Before any Phase 2 code, design must cover:

1. **freelm client wrapper** — module-level, injected, or config-based?
2. **5 prompt templates** — input, output shape, expected tokens each
3. **JSON parsing for critic_score** — reliable structured output
4. **Error handling** — freelm exhausts all providers → ?
5. **Token usage tracking** — where logged, what format

No Phase 2 code until all five are designed, reviewed, and frozen.

---

**End of Project Context v1.5.**