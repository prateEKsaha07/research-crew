# Phase 5 Deep-Dive: Memory and Tracing

This document explains *why* Phase 5 exists, what it adds, and the design decisions that shaped it. Everything here is rationale, not a spec — the specs live in `04-tools.md`.

## Why Phase 5

Phases 0-4 produce a single, self-contained report. Every run starts from zero:

- No memory of prior runs. Researching "quantum computing" twice re-searches the same web and re-summarizes the same snippets.
- No visibility into what the run did. The console log shows node transitions and one line per LLM call, but nothing about why a run was slow, which search took 6s, or whether a critic call went through the repair path.
- No way to demonstrate "similar second topic demonstrates memory recall" from the PoC acceptance criteria.

Phase 5 fixes both.

## Objective

**Memory:** store each approved report and its findings in pgvector. On a later similar topic, recall the nearest findings before live search. The second run reuses knowledge without re-searching, and its report cites URLs from the first run.

**Tracing:** emit one span per node, per LLM call, per search, per memory operation. Local backend. No SaaS. Debuggable after the run.

## Why pgvector and not a separate vector DB

- The Phase 6 API already needs Postgres for job persistence. One database, one connection pool, one transaction boundary.
- `pgvector` is a Postgres extension, not a service. No extra container in the dev loop.
- `pgvector` 0.8.7 is installed in the `pgvector/pgvector:pg16` image. The extension is `CREATE EXTENSION IF NOT EXISTS vector` — no schema migration tool.
- HNSW indexes are not needed at PoC scale. A sequential cosine scan over tens of rows is microseconds.

The trade-off: if the project ever needs >100k stored findings, a sequential scan becomes slow. `08-known-limitations.md` records the threshold.

## Why fastembed and BAAI/bge-small-en-v1.5

- **fastembed** — ONNX runtime, no torch, small install footprint (~150MB with the model). Torch would add ~2GB.
- **BAAI/bge-small-en-v1.5** — 384 dimensions, small model, strong on semantic similarity for topics and short facts. 67MB download, cached once.
- The alternative (sentence-transformers) needs torch. Same embeddings, 30x the install.

The trade-off: fastembed supports a smaller model zoo than sentence-transformers. If a future phase needs a larger embedding model, migration is a table rebuild.

## Why `url UNIQUE`

The schema uses `findings.url UNIQUE` and `store()` uses `ON CONFLICT (url) DO NOTHING`. Consequences:

- **Pro:** the same URL is never stored twice. Repeated runs on the same topic do not duplicate rows.
- **Pro:** `find_similar` deduplicates implicitly. No post-query dedup needed (there is one anyway, as defense in depth).
- **Con:** the same URL cannot exist in two reports. If report A cites `example.org/x` and report B cites it too, report B's row is skipped. The `findings` table is a global URL registry, not a per-report list.

For PoC, this is fine. For Phase 6+, consider `UNIQUE (report_id, url)` — allows the same URL in multiple reports but requires a `DISTINCT ON (url)` in `find_similar` to keep recall clean.

## Why `MEMORY_MAX_DISTANCE = 0.35`

Measured on synthetic pairs (see T5 in the Phase 5 task list):

| Query | Nearest stored | Distance |
|---|---|---|
| `qubits and superposition` | Qubits | 0.07 |
| `quantum computing` | Qubits | 0.21 |
| `RSA encryption` | Shor | 0.32 |
| `cooking pasta` | nearest | 0.545 |

0.35 is the largest threshold that keeps `RSA encryption` -> Shor (0.32) and rejects `cooking pasta` (0.545). The gap between 0.32 and 0.545 is 0.22 — comfortable. Retune in Phase 6 with real topics; synthetic distances may not match live embeddings.

## Why `DB_CONNECT_TIMEOUT_S = 3`

The researcher has an 18s budget (`RESEARCH_BUDGET_S`). If the DB is down, a naive connect would block on the default 30s+ OS TCP timeout and blow the budget. 3s is enough for a local Docker container on a healthy host, short enough to fall back to "no recall" without eating the run.

## Why best-effort

Memory failure must not fail a report. If the DB is down or pgvector is missing, the run continues with no recall. The report still prints. `cli.py` catches `MemoryUnavailableError` around `store()` and prints a warning to stderr. Exit code stays 0.

The same rule applies to tracing: `span()` catches any exception inside and logs. The run proceeds with tracing disabled.

The reason: the report is the product. Observability and memory are enhancements. A broken enhancement must not break the product.

## Why feenion and not OpenTelemetry

- **feenion** — self-hosted, Apache 2.0, ships a Docker server with a React UI, Python SDK with `span()` and `configure()`. One `pip install`, one `docker compose up`.
- **OpenTelemetry** — standard, but requires an exporter, a collector, and a UI (Jaeger or similar). More moving parts, more YAML, more surface area for a PoC.
- The thin wrapper in `tools/tracing.py` makes feenion swappable. Replacing feenion with OTel is one file.

The trade-off: feenion 0.1.2 is early. It does not propagate `parent_span_id` to nested spans (all spans are flat, grouped by session). The fix is upstream.

## Why JSONL when no server

Three benefits over a mandatory server:

- **Zero configuration** for a fresh clone. `python cli.py "topic"` produces a `telemetry/traces.jsonl` with spans. No `docker compose up` required.
- **Grep-able.** A bug report can attach the JSONL. `Select-String "critic" telemetry\traces.jsonl` shows every critic call.
- **One-line switch to server mode.** Set `FEENION_SERVER_URL` in `.env` and the same spans flow to the UI.

The trade-off: the JSONL grows unbounded. It is gitignored; clean it manually or set `FEENION_SERVER_URL` for production use.

## What Phase 5 Does Not Do

- **No cross-run context injection into prompts.** Recall adds findings, not "here is what we concluded last time." The Writer sees findings, not prior reports.
- **No sub-topic clustering.** `find_similar(topic)` compares the topic string to stored finding texts. It does not search for "findings related to findings related to this topic."
- **No migration.** A changed embedding model requires dropping the tables.
- **No memory on aborted runs.** `store()` only runs when `is_approved` is true. A run that fails at the Critic or the Researcher writes nothing.
- **No span nesting.** feenion 0.1.2 limitation. Every span is top-level, grouped by session_id.
