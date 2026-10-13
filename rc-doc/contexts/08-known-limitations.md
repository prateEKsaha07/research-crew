# Known Limitations

Current state as of Phase 3 (tag `v0.4-jiro`).

## Phase 2 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| `provider=<unknown>`, `model=<unknown>` in `[llm]` logs | Can't attribute calls to specific providers | Phase 5 (feenion) |
| `tokens_in=0`, `tokens_out=0` in `[llm]` logs | No token cost visibility | Phase 5 (feenion) |
| Critic is a stub | No real rubric scoring | Phase 4 |
| Latency logged as float (`1750.0ms`) | Cosmetic | Fix anytime |
| No streaming | Caller waits for full LLM response | Phase 6 |

## Phase 3 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| Search is sequential | 3 queries x ~2-5s each dominates wall time | Consider parallel in Phase 5 |
| One result per query | Report uses at most N findings where N = queries | Acceptable for PoC |
| Budget check runs between queries only | One slow search can overshoot `RESEARCH_BUDGET_S` | Acceptable for PoC |
| `[search]` log line can appear to lose a space at the console wrap boundary on Windows PowerShell | Cosmetic; redirected output is correct | Fix anytime |
| LLM report text may contain em dashes that render as `u` under non-UTF-8 PowerShell code pages | Console only; file output is correct | Fix anytime |

## Infrastructure Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `MemorySaver` is in-process | No resume across processes | Phase 6 |
| Fresh `uuid4` per CLI run | Can't resume a prior job | Phase 6 |
| Groq commented out | Region-restricted for user | N/A |
| No observability integration | Can't inspect agent traces | Phase 5 |
| No Docker / K8s | Manual setup only | Phase 7 / 8 |

## Schema Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `confidence_scores` is an untyped `dict` | No validation | Phase 4 |
| No version field in state | Can't detect schema drift | Consider Phase 6 |

## Prompt Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `writer_draft` output starts with `##` not `#` | Missing top-level title | Consider Phase 4 prompt tweak |
| No system/user message split | All prompts are single-user-message | Phase 3+ if needed |
| No few-shot examples in `writer_draft` | Consistency depends on prompt adherence | Consider Phase 4 |

## Deferred Improvements

| Item | Phase |
|---|---|
| Cohere integration | 4 |
| Provider/model attribution from `response.raw` | 4 |
| Per-provider error granularity (`AuthError` vs `RateLimited`) | 4 |
| Real token tracking via feenion | 5 |
| Streaming | 6 |
| Async `chat()` | 6 |