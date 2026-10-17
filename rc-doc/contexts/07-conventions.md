# Conventions

## Response Rules for AI

- Always name the exact file/path you are discussing
- Prefer pseudo-code, decision trees, checklists, atomic next steps
- **NEVER emit full source code or complete files unless the user says "write code" / "implement" / "generate"**
- If the user asks for code without those exact trigger words -> reply with pseudo-code only and ask for confirmation
- Stay inside the current phase unless asked to jump
- Token-efficient. No filler.
- When ambiguous, ask which phase we are in before answering

## Development Discipline

- **One phase = one new class of change.** Never mix concerns.
- **Design first** (pseudo-code), verify, then "write code."
- **Every phase ends runnable + git-committable.**
- **Vertical slice methodology**, not horizontal layers.
- **Tests before swapping fakes for real implementations.**
- **ASCII-only console output** for Windows PowerShell compatibility (`->` not `->`, `-` not `-`).
- **No code generation** until user says "write code" / "implement" / "generate."

## Git Convention

- One branch per phase: `phase-N-slug`
- Merge to `main` on phase completion
- Tag on merge: `v0.N-slug`
- Commit message: `phase-N: what changed`

**Branches shipped:**
- `phase-0-skeleton`
- `phase-1-checkpointing`
- `phase-2-real-llm`
- `phase-3-jiro`
- `phase-4-critic`
- `phase-5-memory` (current)

**Tags shipped:**
- `v0.1-skeleton`
- `v0.2-checkpointing`
- `v0.3-real-llm`
- `v0.4-jiro`
- `v0.5-critic`
- `v0.6-memory`

## Testing Expectations

- Phase 0-2: manual run + console output
- Phase 3+: unit test per agent
- Phase 4+: integration test of full graph (mock LLM)
- Phase 5+: autouse external isolation via `conftest.py`
- Phase 6+: API test via httpx

**Current:** 46 tests passing, 1 skipped
- `test_supervisor.py` x 8
- `test_checkpointing.py` x 2
- `test_search.py` x 7
- `test_researcher.py` x 6
- `test_writer.py` x 1
- `test_critic.py` x 11
- `test_graph_integration.py` x 2
- `test_memory.py` x 6 (+ 1 integration, skipped by default)
- `test_tracing.py` x 3

**Integration tests:** marked `@pytest.mark.integration`. Run with `$env:RUN_INTEGRATION = "1"; pytest -q`.

## Console Log Formats

**Node transition (Phase 2+):**

```text
[p2] <node> -> <next> | <reason> | <ms>ms
```

**LLM call:**

```text
[llm] provider=<name> tokens_in=<N> tokens_out=<M> latency=<ms>ms model=<name>
[llm] FAILED: <ExceptionType>: <message>
```

**Search call (Phase 3+):**

```text
[search] query=<q> results=<N> latency=<int>ms
[search] FAILED: <ExceptionType>: <message>
```

**Critic score line (Phase 4+):**

```text
[critic] coverage=<N> evidence=<N> structure=<N> clarity=<N> avg=<X.XX> approved=<B>
```

**Memory (Phase 5+):**

```text
[memory] recalled=<N> distance_min=<x.xx> latency=<int>ms
[memory] stored findings=<N> latency=<int>ms
[memory] FAILED: <ExceptionType>: <message>
```

**Tracing (Phase 5+):**

```text
[tracing] enabled server_url=<url>
[tracing] enabled exporter=JSONLExporter path=<path>
[tracing] disabled: <ExceptionType>: <message>
[tracing] span failed: <ExceptionType>: <message>
```

**Checkpoint (CLI):**

```text
[checkpoint] thread=<uuid>
[checkpoint] revision_count=N next=()
```

## Contracts Summary (5 invariants)

| # | Invariant | Owner |
|---|---|---|
| 1 | Writer clears `critique` after producing a draft | `writer.py` |
| 2 | Critic always writes non-empty `critique` | `critic.py` |
| 3 | Supervisor reads only presence/absence of `critique` | `supervisor.py` |
| 4 | `tools/llm.py` never reimplements failover | `tools/llm.py` |
| 5 | `research_findings` nodes return only new data | `researcher.py` |

Invariants 1-3 protect the routing loop. Invariant 4 protects the failover chain. Invariant 5 protects the reducer.

## Error Handling Philosophy

- LLM failure -> freelm failover chain; if all fail, job fails with clear error
- Search failure -> retry once, then proceed with fewer findings (no crash)
- Memory failure -> log, continue. Never fails a finished run.
- Tracing failure -> log, continue. Never fails a finished run.
- Critic malformed JSON -> one repair, then `CriticError` (exit 2)
- Citation missing -> Critic flags, Writer revision required
- Never silently degrade: all failures logged with context

## Design Decisions

- **Supervisor pattern > peer-to-peer** — debuggable, extendable
- **Rule routing > LLM routing** — deterministic, cheap, testable
- **Hard revision cap = 3** — protects free LLM quotas
- **pgvector inside Postgres** — one database, one transaction
- **SSE > WebSockets** — simpler, one-way, proxy-friendly
- **Citations validated against state** — prevents hallucination
- **Wrap `FreeLLM`, don't reimplement failover** — freelm does it correctly
- **URLs come from search, not LLM** — LLMs hallucinate URLs
- **Templates are pure string formatters** — testable in isolation
- **Memory and tracing are best-effort** — a dead DB or a broken tracer must not fail a report
- **JSONL tracing when no server** — no daemon, no workspace, grep-able
- **Flat spans acceptable** — feenion 0.1.2 does not nest; session_id grouping is enough for PoC
```
