 Tools

External integrations live in `rc-core/tools/`. Each is a focused module with a clear contract.

Every module obeys the same rule: **it wraps its dependency, it does not reimplement it.** Failover, HTTP, JSON parsing, retries, model loading — all delegated.

## `tools/llm.py` (DONE — Phase 2, updated Phase 4/5)

**Why it exists:** the project must use free-tier LLM providers with failover. `freelm.FreeLLM` already does provider selection, retries, and failover. Reimplementing that is duplicated risk. This module is a thin wrapper that adds logging, one exception type, and (from Phase 5) one trace span.

**Objective:** expose a single `LLMClient.chat()` that turns `messages` into a reply string, or raises `LLMUnavailableError`. Never leak freelm internals to the rest of the codebase.

Wraps `freelm.FreeLLM` with a 4-provider failover chain and adds logging plus error translation.

### Public Surface

```python
LLMClient(providers, usage=None)
LLMClient.chat(messages, *, temperature=0.0, max_tokens=DEFAULT_MAX_TOKENS) -> str
LLMUnavailableError(errors)   # errors: list[tuple[provider_name, error_str]]
get_llm() -> LLMClient        # raises ValueError if no keys
```

### Constants

```text
DEFAULT_MAX_TOKENS = 2000
QUERY_MAX_TOKENS   = 500     # researcher_query_gen
SUMMARY_MAX_TOKENS = 300     # researcher_summarize
DRAFT_MAX_TOKENS   = 3500    # writer_draft, writer_revise
CRITIC_MAX_TOKENS  = 800     # critic_score, critic_repair
```

### Provider Chain

Priority order: Gemini -> Mistral -> OpenRouter -> NVIDIA NIM

Cohere: not available as a provider class in the freelm Python package (checked Phase 4). Cerebras is available in freelm but requires a card on signup. 5th provider deferred.

Groq: commented out (region-restricted)

All providers accept `keys=` (not `api_key=`). Gemini and NIM accept `priority=`.

### Log Formats

```text
[llm] provider=<name> tokens_in=<N> tokens_out=<M> latency=<ms>ms model=<name>
[llm] FAILED: <ExceptionType>: <message>
```

**Known limitation:** `provider=<unknown>`, `model=<unknown>`, `tokens_in=0`, `tokens_out=0`. `ChatResponse` doesn't expose them. Real tracking arrives with a feenion integration that reads `response.raw` in a later phase.

### Tracing (Phase 5)

Each `chat()` call wraps its work in `span("llm.chat", temperature=..., max_tokens=..., prompt_chars=..., latency_ms=...)`. No provider/model/tokens in the span because `ChatResponse` does not expose them (do not invent attribution fields).

### Contract

Never reimplements failover. Delegates to `freelm.FreeLLM`. Any provider added to freelm is picked up by `get_llm()` without code changes.

### Environment

`.env.example`:

```text
GEMINI_API_KEY=
MISTRAL_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=
```

`get_llm()` skips providers with missing keys. Raises `ValueError` if all keys are missing.

## `tools/search.py` (DONE — Phase 3, updated Phase 5)

**Why it exists:** the Researcher needs real URLs. The choice of search backend should be one module, not scattered through agents. Replacing ddgs (or adding a second backend) should not touch `researcher.py`.

**Objective:** given a query string, return up to `max_results` normalized `{title, url, snippet}` dicts. Or raise `SearchUnavailableError`. Never return placeholder URLs. Never invent URLs.

Thin wrapper around `ddgs` (the renamed `duckduckgo-search` package). Pure Python, no server, no config.

### Public Surface

```python
search(query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]
# Returns: [{"title": str, "url": str, "snippet": str}, ...]
# Raises SearchUnavailableError after all attempts fail.
```

### Constants

```text
DEFAULT_MAX_RESULTS = 3
SEARCH_RETRIES      = 1   # 2 attempts total
```

### Behavior

- ddgs `DDGS().text(query, max_results=N)` per attempt.
- One retry on any exception except "no results" (see below).
- `DDGSException("No results found")` is treated as `[]`, not an error.
- Zero results returns `[]`.
- Non-http(s) URLs and empty snippets are dropped.
- Result list truncated to `max_results`.

### Log Formats

```text
[search] query=<q> results=<N> latency=<int>ms
[search] FAILED: <ExceptionType>: <message>
```

### Tracing (Phase 5)

Each successful search wraps its work in `span("search", query=..., results=..., latency_ms=...)`.

### Field Mapping

| ddgs field | ours |
|---|---|
| `title` | `title` |
| `href`  | `url` |
| `body`  | `snippet` |

### Deferred

Jiro was abandoned on Python 3.12 (selectolax Modest backend removed; aiosqlite event-loop race). ddgs replaced it.

## `tools/memory.py` (Phase 5)

**Why it exists:** repeated runs on similar topics need not re-research the same facts. Storing report + findings in pgvector lets the Researcher recall them, which (a) makes the second run faster, (2) makes the second run consistent with the first, and (3) demonstrates a cross-session memory layer for the PoC acceptance criteria.

**Objective:** persist reports and their findings, and answer "what findings are close to this topic?" in one query. Best-effort — a dead DB must not fail a run.

**Owns:** the `reports` and `findings` tables. Nothing else touches pgvector.

**Dependencies:** `psycopg` (driver), `pgvector.psycopg` (vector type registration), `fastembed` (embedding model), `BAAI/bge-small-en-v1.5` (model weights, downloaded once).

### Public Surface

```python
ensure_schema()                                      # idempotent, once per process
find_similar(topic, *, k=MEMORY_K) -> list[dict]     # [{text, url, distance}]
store(topic, report, findings) -> None
MemoryUnavailableError
```

### Constants

```text
EMBED_DIM             = 384
MEMORY_K              = 3
MEMORY_MAX_DISTANCE   = 0.35
DB_CONNECT_TIMEOUT_S  = 3
EMBED_MODEL_NAME      = "BAAI/bge-small-en-v1.5"
```

**Why `MEMORY_MAX_DISTANCE = 0.35`:** measured on synthetic pairs. `"qubits and superposition"` -> stored qubit fact = 0.07. `"quantum computing"` -> same = 0.21. `"RSA encryption"` -> stored Shor fact = 0.32. `"cooking pasta"` -> nearest stored = 0.545. 0.35 keeps all related pairs and rejects unrelated ones. Retune in Phase 6 with real topics.

**Why `DB_CONNECT_TIMEOUT_S = 3`:** a dead DB must not eat the researcher's 18s budget. 3s is enough for a local container, short enough to fall back fast.

**Why `url UNIQUE`:** cross-report deduplication. The second similar run recalls the first run's findings, and re-storing hits `ON CONFLICT (url) DO NOTHING` instead of duplicating. Cost: the same URL cannot exist in two reports. Acceptable for PoC; noted in `08-known-limitations.md`.

### Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    report TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE findings (
    id SERIAL PRIMARY KEY,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    embedding vector(384) NOT NULL
);
```

No ANN index. PoC scale (tens of rows). A changed embedding model requires dropping and recreating the tables — no migration.

### Behavior

- `_embed(texts)`: lazy-loads the model once per process, cached globally. Returns `list[list[float]]`, length 384. Monkeypatchable in tests.
- `find_similar(topic)`:
  - embeds the topic
  - `SELECT text, url, embedding <=> $1 AS distance FROM findings WHERE embedding <=> $1 <= $max ORDER BY distance LIMIT k*4`
  - dedups by url (defends against a future where `url UNIQUE` is relaxed)
  - truncates to `k`
  - logs `[memory] recalled=<N> distance_min=<x.xx> latency=<int>ms`
- `store(topic, report, findings)`:
  - one transaction: `INSERT INTO reports`, batch-embed, `INSERT INTO findings ... ON CONFLICT (url) DO NOTHING`
  - logs `[memory] stored findings=<N> latency=<int>ms`
- Any DB or embed error becomes `MemoryUnavailableError`. Logs `[memory] FAILED: <ExceptionType>: <msg>`.

### Tracing (Phase 5)

`find_similar` and `store` are wrapped in `span("memory.find_similar", ...)` and `span("memory.store", ...)` by their callers (`researcher.py` and `cli.py`), not inside `memory.py`. This keeps `memory.py` free of tracing concerns.

### Why sequential, no ANN index

At PoC scale, a sequential cosine scan over tens of rows is microseconds. Adding HNSW now would be premature. Revisit if `findings` exceeds ~100k rows.

## `tools/tracing.py` (Phase 5)

**Why it exists:** when a run is slow or produces a bad report, "open the code and add prints" is not a debugging strategy. feenion provides per-span capture with a local backend. This module is the only place that touches feenion, so the tracing backend stays swappable.

**Objective:** emit spans for nodes, LLM calls, searches, and memory operations. If feenion is missing or broken, become a no-op and never fail the run.

**Owns:** feenion configuration. Nothing else.

### Public Surface

```python
init_tracing() -> bool       # True if enabled, False otherwise. Never raises.
span(name, **attrs)          # context manager. No-op when disabled.
```

### Configuration

- If `FEENION_SERVER_URL` is set: `feenion.configure(server_url=..., workspace_id=..., api_key=...)`. Spans ship to the self-hosted feenion server (docker compose on `localhost:8000`).
- Otherwise: `feenion.configure(exporter=JSONLExporter("telemetry/traces.jsonl"))`. Spans append to `telemetry/traces.jsonl`, one JSON object per line.

The trace id equals the checkpoint thread id (`cli.py` calls `feenion.set_session(tid)`).

### Behavior

- `init_tracing()` calls `feenion.configure(...)`. Any exception -> `False`, `_ENABLED` stays `False`.
- `span(name, **attrs)` yields `None` when disabled. When enabled, wraps `feenion.span(name, attributes=attrs)`.
- `span()` catches any exception inside and prints `[tracing] span failed: <...>`. The run continues.

### Known limitation

feenion 0.1.2 does not propagate `parent_span_id` to nested spans. All spans are flat, grouped only by `session_id` (which equals the checkpoint `thread_id`). Parent-child tree is absent. Acceptable for PoC; revisit when feenion fixes `SpanContextManager`.

### Why JSONL when no server

No daemon to run. No workspace to configure. Fully local, grep-able, easy to attach to a bug report. When the feenion server is up, spans move to the UI with a one-line env change.

## Environment

`.env.example`:

```text
# LLM provider keys. Set at least one.
GEMINI_API_KEY=
MISTRAL_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=

# Dev defaults only. Do not use in production.
DATABASE_URL=postgresql://rc:rc@localhost:5432/researchcrew

# Optional. If unset, feenion writes to telemetry/traces.jsonl.
# FEENION_SERVER_URL=http://localhost:8000
# FEENION_WORKSPACE_ID=
# FEENION_API_KEY=
```
```
