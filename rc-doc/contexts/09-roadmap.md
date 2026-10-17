# Roadmap

**Current phase:** 6 — FastAPI + SSE
**Latest tag:** `v0.6-memory`
**Active branch:** `phase-6-api`

## Progress Tracker

| Phase | Status | Tag | Deliverable |
|---|---|---|---|
| 0 — Walking Skeleton | Done | `v0.1-skeleton` | Full pipeline with fake data |
| 1 — Checkpointing | Done | `v0.2-checkpointing` | Verified routing + MemorySaver |
| 2 — Real LLM | Done | `v0.3-real-llm` | Real LLM for Researcher + Writer |
| 3 — ddgs Search | Done | `v0.4-jiro` | Real URLs, `list[dict]` findings |
| 4 — Real Critic | Done | `v0.5-critic` | Rubric scoring, JSON output |
| 5 — feenion + pgvector | Done | `v0.6-memory` | Tracing, semantic memory |
| 6 — FastAPI + SSE | In Progress | — | HTTP API, streaming progress |
| 7 — Docker Compose | Pending | — | Container orchestration |
| 8 — Kubernetes | Pending | — | Cluster deployment |

**6 of 9 phases complete.**

## Phase 0 — Walking Skeleton

**Delivered:**
- `graph/state.py` — `ResearchState` TypedDict with `add` reducer
- `graph/builder.py` — StateGraph with 4 nodes, conditional edges, MemorySaver
- 4 agent stubs (supervisor, researcher, writer, critic)
- `cli.py` — end-to-end pipeline
- Fake report printed, `revision_count=2`

**Tag:** `v0.1-skeleton`

## Phase 1 — Checkpointing Verification

**Delivered:**
- 8 supervisor tests (every branch, boundary, stale-flag edge case)
- 2 checkpointing tests (save, isolation)
- CLI checkpoint diagnostics
- Confirmed: `.next=()`, `revision_count=2` matches final state

**Tag:** `v0.2-checkpointing`

## Phase 2 — Real LLM

**Delivered:**
- `tools/llm.py` — `LLMClient` wrapping freelm.FreeLLM with 4-provider chain
- `prompts/templates.py` — 4 prompt templates
- `.env.example` — API key template
- `agents/researcher.py` — LLM-only researcher with query parsing
- `agents/writer.py` — real LLM writer with draft/revise modes
- `graph/builder.py` — injects `llm` via `functools.partial`
- `cli.py` — calls `get_llm()`, handles errors, prints usage
- `tests/_fake_llm.py` — test helper

**Verified:** 6 LLM calls in ~22s, real Markdown report, revision loop fires, checkpoint saved.

**Tag:** `v0.3-real-llm`

## Phase 3 — ddgs Search

**Delivered:**
- `tools/search.py` — ddgs client, one retry, empty-result handling
- `graph/state.py` — `Finding` TypedDict, `research_findings` is `list[Finding]`
- `prompts/templates.py` — `researcher_summarize(query, snippet)`; `writer_draft` renders `list[dict]` findings
- `agents/researcher.py` — real search + summarize, `ResearchError`, `RESEARCH_BUDGET_S = 18`
- `agents/writer.py` — reads findings as dicts, no pipe parsing
- `cli.py` — catches `SearchUnavailableError` and `ResearchError`
- `tests/test_search.py` (7), `test_researcher.py` (4), `test_writer.py` (1); supervisor fixtures migrated to dicts
- `requirements.txt` created
- `.env.example` created

**Verified:** 22 tests passing. Full CLI run in ~26s, 4 real URLs, no `example.com`.

**Note:** Jiro was abandoned on Python 3.12 (selectolax, aiosqlite). Replaced with `ddgs`.

**Tag:** `v0.4-jiro`

## Phase 4 — Real Critic

**Delivered:**
- `graph/state.py` — `ConfidenceScores` TypedDict (`total=False`, all `float`)
- `prompts/templates.py` — `critic_score(draft, findings)`, `critic_repair(raw_output)` (Six templates now)
- `agents/critic.py` — real LLM rubric, JSON parse + validate, one repair pass, `CriticError`, invariant 2 honored
- `agents/supervisor.py` — `MAX_REVISIONS = 3` extracted; single source of truth
- `graph/builder.py` — `partial(critic, llm=llm)`; `_reason("critic")` returns `avg=<x> approved=<b>`
- `cli.py` — catches `CriticError`, prints `confidence_scores:` block
- `tests/_fake_llm.py` — `CriticAwareFakeLLM`, `_fake_llm(critic_replies=...)`
- `tests/test_critic.py` (11 tests)
- `tests/test_graph_integration.py` (2 tests)

**Verified:** 35 tests passing. Real CLI run: `[critic] coverage=10 ... avg=10.00 approved=True`, `revision_count=1`, clean terminate.

**Skipped:** Cohere (not in freelm), Cerebras (card required).

**Tag:** `v0.5-critic`

## Phase 5 — feenion + pgvector

**Delivered:**
- `tools/tracing.py` — `init_tracing()`, `span(name, **attrs)`; JSONL when no server, HTTP when `FEENION_SERVER_URL` is set
- `tools/memory.py` — pgvector store/recall, `find_similar`, `store`, `ensure_schema`, `MemoryUnavailableError`
- `agents/researcher.py` — recall step before search; recalled + new merged; memory failure degrades
- `graph/builder.py` — `logged()` span wraps `fn(state)` so inner calls can attach
- `tools/llm.py` — `llm.chat` span
- `tools/search.py` — `search` span
- `cli.py` — `init_tracing()`, `feenion.set_session(tid)`, `store()` after approval
- `conftest.py` — autouse fixture stubs memory + tracing for unit tests; `integration` marker
- `tests/test_memory.py` (6 + 1 integration), `test_tracing.py` (3), `test_researcher.py` +2
- `requirements.txt` — feenion, psycopg, pgvector, fastembed pinned
- `.env.example` — `DATABASE_URL` and optional feenion vars

**Verified:** 46 passed, 1 skipped. CLI run: `[memory] recalled=1 distance_min=0.21`, then `[memory] stored findings=6`. `reports` and `findings` counts increase.

**Note:** feenion 0.1.2 does not nest spans. Traces are flat, grouped by session.

**Tag:** `v0.6-memory`

## Phase 6 — FastAPI + SSE

**Goal:** HTTP API with streaming progress.

**Planned changes:**
- `api/main.py` — FastAPI app with 3 endpoints
- `POST /research` — background task, returns job_id
- `GET /research/{id}` — status + report
- `GET /research/{id}/stream` — SSE progress
- Jobs persisted to Postgres
- Swap `MemorySaver` for persistent checkpointer
- Retune `MEMORY_MAX_DISTANCE` on real topics
- Consider ANN index if `findings` grows

**Success check:** curl submit -> poll -> live SSE progress.

## Phase 7 — Docker Compose

**Goal:** One-command full-stack startup.

**Planned changes:**
- `rc-core/Dockerfile`
- `docker-compose.yml` — app + Postgres + feenion + UI
- Health checks, depends_on ordering, named volumes
- Retire the dev `rc-pg` container

**Success check:** `docker compose up` -> all services healthy -> API reachable.

## Phase 8 — Kubernetes (optional)

**Goal:** Production-grade deployment.

**Planned changes:**
- Minikube local cluster
- PostgreSQL as StatefulSet with PVC
- FastAPI as Deployment + Service
- Ingress, ConfigMap, Secret
- Helm chart packaging

**Success check:** `kubectl apply -f k8s/` -> Pods running -> externally reachable.

## Acceptance for PoC Completion

- API accepts a topic
- Returns Markdown with >=3 real clickable citations in <=30 seconds
- Full observability trace visible
- `docker compose up` works
- Similar second topic demonstrates memory recall
- Phases 0-7 merged, tagged `v1.0-poc`

## Next Atomic Action

**Phase 6, Task 1:** Design `api/main.py` — `POST /research` returns `job_id`; `GET /research/{id}` returns status + report; `GET /research/{id}/stream` returns SSE. Decide the persistent checkpointer (Postgres or SqliteSaver) before implementing.
