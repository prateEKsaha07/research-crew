# Roadmap

**Current phase:** 3 — Jiro Search + Real Citations
**Latest tag:** `v0.3-real-llm`
**Active branch:** `phase-3-jiro`

## Progress Tracker

| Phase | Status | Tag | Deliverable |
|---|---|---|---|
| 0 — Walking Skeleton | ✅ Done | `v0.1-skeleton` | Full pipeline with fake data |
| 1 — Checkpointing | ✅ Done | `v0.2-checkpointing` | Verified routing + MemorySaver |
| 2 — Real LLM | ✅ Done | `v0.3-real-llm` | Real LLM for Researcher + Writer |
| 3 — Jiro Search | 🚧 In Progress | — | Real URLs, `list[dict]` findings |
| 4 — Real Critic | ⏳ Pending | — | Rubric scoring, JSON output |
| 5 — feenion + pgvector | ⏳ Pending | — | Tracing, semantic memory |
| 6 — FastAPI + SSE | ⏳ Pending | — | HTTP API, streaming progress |
| 7 — Docker Compose | ⏳ Pending | — | Container orchestration |
| 8 — Kubernetes | ⏳ Pending | — | Cluster deployment |

**3 of 9 phases complete.**

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

## Phase 3 — Jiro Search 🚧 IN PROGRESS

**Goal:** Replace `example.com/<slug>` with real Jiro URLs.

**Planned changes:**
- `tools/search.py` — Jiro HTTP client
- `graph/state.py` — `research_findings` from `list[str]` to `list[dict]` with `{text, url}`
- `agents/researcher.py` — call Jiro per query, use real URLs
- `prompts/templates.py` — `researcher_summarize` takes a search snippet
- `agents/writer.py` — read `finding["url"]` instead of parsing strings
- `tests/test_search.py` — new unit tests with mocked HTTP

**Success check:** `python rc-core/cli.py "quantum computing"` produces a report where every URL is clickable and points to a real page.

## Phase 4 — Real Critic ⏳

**Goal:** Replace stub with LLM-scored rubric.

**Planned changes:**
- `prompts/templates.py` — add `critic_score(draft, findings)` template
- `agents/critic.py` — real LLM scoring, JSON parsing, retry on malformed
- Code computes `avg` and `is_approved`; cap stays in supervisor

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

**Phase 3, Task 1:** Install Jiro and verify local server runs.

```bash
pip install jirosearch
jiro serve
curl http://localhost:8000/health
text

---