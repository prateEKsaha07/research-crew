# Known Limitations

Current state as of Phase 5 (tag `v0.6-memory`).

## Phase 2 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| `provider=<unknown>`, `model=<unknown>` in `[llm]` logs | Can't attribute calls to specific providers | Deferred; `ChatResponse` does not expose them |
| `tokens_in=0`, `tokens_out=0` in `[llm]` logs | No token cost visibility | Deferred |
| Latency logged as float (`1750.0ms`) | Cosmetic | Fix anytime |
| No streaming | Caller waits for full LLM response | Phase 6 |

## Phase 3 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| Search is sequential | 3 queries x ~2-5s each dominates wall time | Consider parallel in a later phase |
| One result per query | Report uses at most N findings where N = queries | Acceptable for PoC |
| Budget check runs between queries only | One slow search can overshoot `RESEARCH_BUDGET_S` | Acceptable for PoC |
| `[search]` log line can appear to lose a space at the console wrap boundary on Windows PowerShell | Cosmetic; redirected output is correct | Fix anytime |
| LLM report text may contain em dashes that render as `u` under non-UTF-8 PowerShell code pages | Console only; file output is correct | Fix anytime |

## Phase 4 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| Critic latency is one LLM call per pass (~1-2s on free tier) | Adds to wall time when the revise loop fires | Acceptable for PoC |
| LLM-judge score variance across providers | Same draft can score 8 on Gemini and 6 on Mistral | Prompt anchors mitigate; no cross-provider calibration |
| JSON validity depends on provider | Some free-tier models occasionally emit fences or prose around the JSON | One repair pass, then `CriticError` |
| Critic approves at 10/10/10/10 first pass on some runs | Weak signal; the rubric is not always exercised | Consider tightening anchors in a later phase |
| Writer citation format drifts (`[url]` instead of `[text](url)`) | Critic does not always catch it | Consider Critic prompt tightening |

## Phase 5 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| feenion 0.1.2 does not propagate `parent_span_id` to nested spans | Traces are flat, grouped by `session_id` only; no parent-child tree | Revisit if feenion fixes `SpanContextManager` |
| `MEMORY_MAX_DISTANCE=0.35` tuned on synthetic pairs only | Real-topic distances may shift; recall may become too strict or too loose | Retune with real topics in Phase 6 |
| `findings.url UNIQUE` collapses cross-report duplicates | Same URL cannot exist in two reports; the second store skips it | Acceptable for PoC |
| No ANN index on `findings.embedding` | Cosine scan is linear; O(n) grows with stored rows | Add HNSW if `findings` > ~100k rows |
| A changed embedding model requires dropping and recreating the tables | No migration path | Acceptable for PoC |
| Recall happens before query generation and counts toward the 18s budget | A slow DB eats search budget | `DB_CONNECT_TIMEOUT_S = 3` bounds the worst case |
| Memory and tracing silently no-op on failure | A misconfigured DB or tracer produces no error, only a log line | Intentional; the report must still ship |
| Tracing via JSONL grows unbounded | `telemetry/traces.jsonl` accumulates across runs | Manual cleanup; gitignored |

## Infrastructure Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `MemorySaver` is in-process | No resume across processes | Phase 6 |
| Fresh `uuid4` per CLI run | Can't resume a prior job | Phase 6 |
| No 5th LLM provider | Cohere not in freelm; Cerebras needs a card | Deferred |
| Groq commented out | Region-restricted for user | N/A |
| No Docker / K8s | Manual setup only | Phase 7 / 8 |
| Postgres container is a dev container | Phase 7 compose replaces it | Phase 7 |

## Schema Limitations

| Limitation | Impact | Phase |
|---|---|---|
| No version field in state | Can't detect schema drift | Consider Phase 6 |
| `reports` table has no unique constraint on topic | Same topic can be stored many times; recall relies on `findings.url UNIQUE` | Acceptable for PoC |

## Prompt Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `writer_draft` output starts with `##` not `#` | Missing top-level title | Consider Phase 6 prompt tweak |
| No system/user message split | All prompts are single-user-message | Phase 6+ if needed |
| No few-shot examples in `writer_draft` | Consistency depends on prompt adherence | Consider Phase 6 |

## Deferred Improvements

| Item | Phase |
|---|---|
| Real token tracking | Deferred |
| Provider/model attribution from `response.raw` | Deferred |
| 5th provider (Cohere or Cerebras) | Deferred |
| Parallel search | Deferred |
| ANN index for `findings` | Deferred |
| Streaming | 6 |
| Async `chat()` | 6 |
| Persistent checkpointer (Postgres) | 6 |
```
