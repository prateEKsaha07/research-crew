# Tech Stack

All free and self-hostable. No paid APIs, no cloud vector DBs, no proprietary locked models.

## Stack Table

| Layer | Tech | Purpose | Phase |
|---|---|---|---|
| Orchestration | LangGraph + LangChain | Stateful multi-agent graph with conditional routing | 0 |
| LLM | `freelm` | Multi-provider failover across free tiers | 2 |
| Search | `ddgs` (DuckDuckGo) | Web search, pure Python | 3 |
| Memory | PostgreSQL + pgvector | Semantic recall | 5 |
| Observability | feenion | Local per-step tracing | 5 |
| Backend | FastAPI + Uvicorn | REST API + SSE | 6 |
| Frontend | React + Vite + React Flow | Live agent graph | 6 |
| Container | Docker Compose | Local orchestration | 7 |
| Production | Kubernetes + Helm | Cluster deployment | 8 |

## LLM Chain

**Priority:** Gemini → Mistral → OpenRouter → NVIDIA NIM

| Provider | Env Variable | Free Tier | Role |
|---|---|---|---|
| Gemini | `GEMINI_API_KEY` | 1,500 RPD (Flash) | Primary |
| Mistral | `MISTRAL_API_KEY` | 60 RPM, uncapped daily | Secondary |
| OpenRouter | `OPENROUTER_API_KEY` | 50 RPD (`:free` models) | Tertiary |
| NVIDIA NIM | `NVIDIA_API_KEY` | 40 RPM, credit-limited | Quaternary |
| Cohere | `COHERE_API_KEY` | 1,000/month | Phase 4 (last resort) |
| Groq | `GROQ_API_KEY` | — | Region-restricted, commented out |

## freelm API Surface (verified)

**`FreeLLM`:**

```text
FreeLLM(providers, *, http_client=None, **kw)
FreeLLM.chat(messages, model="auto", **kw) -> ChatResponse
FreeLLM.text(messages, model="auto", **kw) -> str
FreeLLM.stream / stream_chunks / health / close / from_env / refresh_models / reset_keys
ChatResponse exposes: text, latency_ms, raw, tool_calls
Not exposed: provider name, model name, token usage

Provider constructors:

text
GoogleAIStudio(keys, *, priority=0, free_only=False, ...)
Mistral(keys, **kw)
OpenRouter(keys, **kw)
NIM(keys, *, priority=0, free_only=False, ...)
Environment
.env.example:

text
GEMINI_API_KEY=
MISTRAL_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=
# COHERE_API_KEY=
# GROQ_API_KEY=
.env is gitignored. Only .env.example is committed.

Tooling Versions
Tool	Version
Python	3.12.2
pytest	9.1.1
langgraph	1.2.14
langchain-core	1.6.9
freelm	0.5.2
ddgs	9.16.0
python-dotenv	1.2.4
text

---