# Roadmap

**Current phase:** 4 — Real Critic
**Latest tag:** `v0.4-jiro`
**Active branch:** `phase-4-critic`

## Progress Tracker

| Phase | Status | Tag | Deliverable |
|---|---|---|---|
| 0 — Walking Skeleton | ✅ Done | `v0.1-skeleton` | Full pipeline with fake data |
| 1 — Checkpointing | ✅ Done | `v0.2-checkpointing` | Verified routing + MemorySaver |
| 2 — Real LLM | ✅ Done | `v0.3-real-llm` | Real LLM for Researcher + Writer |
| 3 — ddgs Search | ✅ Done | `v0.4-jiro` | Real URLs, `list[dict]` findings |
| 4 — Real Critic | 🚧 In Progress | — | Rubric scoring, JSON output |
| 5 — feenion + pgvector | ⏳ Pending | — | Tracing, semantic memory |
| 6 — FastAPI + SSE | ⏳ Pending | — | HTTP API, streaming progress |
| 7 — Docker Compose | ⏳ Pending | — | Container orchestration |
| 8 — Kubernetes | ⏳ Pending | — | Cluster deployment |

**4 of 9 phases complete.**

## Phase 0 — Walking Skeleton ✅

**Delivered:**
- `graph/state.py` — `ResearchState` TypedDict with `add` reducer
- `graph/builder.py` — StateGraph with 4 nodes, conditional edges, MemorySaver
- 4 agent stubs (supervisor, researcher, writer, critic)
- `cli.py` — end-to-end pipeline
- Fake report printed, `revision_count=2`

**Tag:** `v0.1-skeleton`

## Phase 1 — Checkpointing Verification ✅

**Delivered:**
- 8 supervisor tests (every branch, boundary, stale-flag edge case)
- 2 checkpointing tests (save, isolation)
- CLI checkpoint diagnostics
- Confirmed: `.next=()`, `revision_count=2` matches final state

**Tag:** `v0.2-checkpointing`

## Phase 2 — Real LLM ✅

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

## Phase 3 — ddgs Search ✅

**Delivered:**
- `tools/search.py` — ddgs client, one retry, empty-result handling
- `graph/state.py` — `Finding` TypedDict, `research_findings` is `list[Finding]`
- `prompts/templates.py` — `researcher_summarize(query, snippet)`; `writer_draft` renders `list[dict]` findings
- `agents/researcher.py` — real search + summarize, `ResearchError`, `RESEARCH_BUDGET_S = 18`
- `agents/writer.py` — reads findings as dicts, no pipe parsing
- `cli.py` — catches `SearchUnavailableError` and `ResearchError`
- `tests/test_search.py` (7), `test_researcher.py` (4), `test_writer.py` (1); supervisor fixtures migrated to dicts
- `requirements.txt` created (langgraph, langchain-core, freelm, ddgs, python-dotenv, pytest)
- `.env.example` created

**Verified:** 22 tests passing. Full CLI run in ~26s, 4 real URLs, no `example.com`.

**Note:** Jiro was abandoned on Python 3.12 (selectolax, aiosqlite). Replaced with `ddgs`.

**Tag:** `v0.4-jiro`

## Phase 4 — Real Critic ⏳

**Goal:** Replace stub with LLM-scored rubric.

**Planned changes:**
- `prompts/templates.py` — add `critic_score(draft, findings)` template
- `agents/critic.py` — real LLM scoring, JSON parsing, retry on malformed
- Code computes `avg` and `is_approved`; cap stays in supervisor
- Cohere added to the provider chain

**Success check:** Critic returns JSON scores; approval at avg ≥ 8; malformed JSON retries once then fails job.

## Phase 5 — feenion + pgvector ⏳

**Goal:** Observability and cross-session memory.

**Planned changes:**
- `tools/memory.py` — pgvector queries and writes
- feenion integration — replace `print` in log decorator with structured traces
- `agents/researcher.py` — query pgvector for similar topics before research

**Success check:** Full trace per run; second similar topic demonstrates memory recall.

## Phase 6 — FastAPI + SSE ⏳

**Goal:** HTTP API with streaming progress.

**Planned changes:**
- `api/main.py` — FastAPI app with 3 endpoints
- `POST /research` — background task, returns job_id
- `GET /research/{id}` — status + report
- `GET /research/{id}/stream` — SSE progress
- Jobs persisted to Postgres
- Swap `MemorySaver` for persistent checkpointer

**Success check:** curl submit → poll → live SSE progress.

## Phase 7 — Docker Compose ⏳

**Goal:** One-command full-stack startup.

**Planned changes:**
- `rc-core/Dockerfile`
- `docker-compose.yml` — app + Postgres + Qdrant + Jaeger + Ollama
- Health checks, depends_on ordering, named volumes

**Success check:** `docker compose up` → all services healthy → API reachable.

## Phase 8 — Kubernetes (optional) ⏳

**Goal:** Production-grade deployment.

**Planned changes:**
- Minikube local cluster
- PostgreSQL/Qdrant as StatefulSets with PVCs
- FastAPI as Deployment + Service
- Ingress, ConfigMap, Secret
- Helm chart packaging

**Success check:** `kubectl apply -f k8s/` → Pods running → externally reachable.

## Acceptance for PoC Completion

- API accepts a topic
- Returns Markdown with ≥3 real clickable citations in ≤30 seconds
- Full observability trace visible
- `docker compose up` works
- Similar second topic demonstrates memory recall
- Phases 0–7 merged, tagged `v1.0-poc`

## Next Atomic Action

**Phase 4, Task 1:** Design `critic_score(draft, findings)` template and `agents/critic.py` LLM rubric. Temperature 0.0, `CRITIC_MAX_TOKENS = 800`. Malformed JSON -> one repair retry -> fail job.