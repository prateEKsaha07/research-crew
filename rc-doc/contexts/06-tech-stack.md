# Tech Stack

All free and self-hostable. No paid APIs, no cloud vector DBs, no proprietary locked models.

## Stack Table

| Layer | Tech | Purpose | Why this one | Phase |
|---|---|---|---|---|
| Orchestration | LangGraph + LangChain | Stateful multi-agent graph with conditional routing | Conditional edges map cleanly to the Supervisor pattern; MemorySaver is trivial; no paid cloud required | 0 |
| LLM | `freelm` | Multi-provider failover across free tiers | Handles Gemini/Mistral/OpenRouter/NIM failover without reimplementation | 2 |
| Search | `ddgs` (DuckDuckGo) | Web search, pure Python | No server, no key, real URLs; Jiro abandoned on 3.12 | 3 |
| Memory | PostgreSQL + pgvector | Semantic recall | pgvector is one extension; same DB as future API persistence | 5 |
| Observability | feenion | Local per-step tracing | Self-hosted, Apache 2.0, no SaaS | 5 |
| Backend | FastAPI + Uvicorn | REST API + SSE | Async, SSE is one-way and proxy-friendly | 6 |
| Frontend | React + Vite + React Flow | Live agent graph | React Flow renders the LangGraph diagram | 6 |
| Container | Docker Compose | Local orchestration | One command to run everything | 7 |
| Production | Kubernetes + Helm | Cluster deployment | Optional | 8 |

## LLM Chain

**Priority:** Gemini -> Mistral -> OpenRouter -> NVIDIA NIM

| Provider | Env Variable | Free Tier | Role |
|---|---|---|---|
| Gemini | `GEMINI_API_KEY` | 1,500 RPD (Flash) | Primary |
| Mistral | `MISTRAL_API_KEY` | 60 RPM, uncapped daily | Secondary |
| OpenRouter | `OPENROUTER_API_KEY` | 50 RPD (`:free` models) | Tertiary |
| NVIDIA NIM | `NVIDIA_API_KEY` | 40 RPM, credit-limited | Quaternary |
| Cohere | — | not in freelm | Deferred; no provider class in the Python package |
| Cerebras | `CEREBRAS_API_KEY` | Free Trial requires card | Deferred |
| Groq | `GROQ_API_KEY` | — | Region-restricted, commented out |

## Memory Stack

| Component | Package | Version | Why |
|---|---|---|---|
| Driver | `psycopg` | 3.3.6 | Native pgvector adapter; async-ready |
| Vector type | `pgvector` | 0.5.1 | Registers `vector(N)` on the connection |
| Embeddings | `fastembed` | 0.9.0 | ONNX runtime, no torch, small footprint |
| Model | `BAAI/bge-small-en-v1.5` | 384 dim | Small, fast, good at topic similarity |
| DB | `pgvector/pgvector:pg16` | image | Postgres 16 + vector extension preinstalled |

## Observability Stack

| Component | Package | Version | Why |
|---|---|---|---|
| Tracer | `feenion` | 0.1.2 | Self-hosted, Apache 2.0, Python SDK + Docker server |
| Default exporter | `JSONLExporter` | — | No server needed; appends to `telemetry/traces.jsonl` |
| Optional exporter | HTTP to self-hosted server | — | `FEENION_SERVER_URL` set; UI shows spans |

## freelm API Surface (verified)

**`FreeLLM`:**

```text
FreeLLM(providers, *, http_client=None, **kw)
FreeLLM.chat(messages, model="auto", **kw) -> ChatResponse
FreeLLM.text(messages, model="auto", **kw) -> str
FreeLLM.stream / stream_chunks / health / close / from_env / refresh_models / reset_keys
```

**`ChatResponse`** exposes: `text`, `latency_ms`, `raw`, `tool_calls`
**Not exposed:** provider name, model name, token usage

**Provider constructors:**

```text
GoogleAIStudio(keys, *, priority=0, free_only=False, ...)
Mistral(keys, **kw)
OpenRouter(keys, **kw)
NIM(keys, *, priority=0, free_only=False, ...)
```

## Environment

`.env.example`:

```text
GEMINI_API_KEY=
MISTRAL_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=

DATABASE_URL=postgresql://rc:rc@localhost:5432/researchcrew

# FEENION_SERVER_URL=http://localhost:8000
# FEENION_WORKSPACE_ID=
# FEENION_API_KEY=
```

`.env` is gitignored. Only `.env.example` is committed.

## Tooling Versions

| Tool | Version |
|---|---|
| Python | 3.12.2 |
| pytest | 9.1.1 |
| langgraph | 1.2.14 |
| langchain-core | 1.6.9 |
| freelm | 0.5.2 |
| ddgs | 9.16.0 |
| python-dotenv | 1.2.4 |
| feenion | 0.1.2 |
| psycopg | 3.3.6 |
| pgvector | 0.5.1 |
| fastembed | 0.9.0 |
```
