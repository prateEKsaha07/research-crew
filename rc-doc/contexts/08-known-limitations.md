# Known Limitations

Current state as of Phase 2 (tag `v0.3-real-llm`).

## Phase 2 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| `provider=<unknown>`, `model=<unknown>` in `[llm]` logs | Can't attribute calls to specific providers | Phase 5 (feenion) |
| `tokens_in=0`, `tokens_out=0` in `[llm]` logs | No token cost visibility | Phase 5 (feenion) |
| URLs are `example.com/<slug>` placeholders | Citations aren't real | Phase 3 (Jiro) |
| Critic is a stub | No real rubric scoring | Phase 4 |
| Latency logged as float (`1750.0ms`) | Cosmetic | Fix anytime |
| No streaming | Caller waits for full LLM response | Phase 6 |

## Infrastructure Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `MemorySaver` is in-process | No resume across processes | Phase 6 |
| Fresh `uuid4` per CLI run | Can't resume a prior job | Phase 6 |
| Cohere not in failover chain | One fewer fallback | Phase 3 |
| Groq commented out | Region-restricted for user | N/A |
| No observability integration | Can't inspect agent traces | Phase 5 |
| No Docker / K8s | Manual setup only | Phase 7 / 8 |

## Schema Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `research_findings` is `list[str]` (pipe-delimited) | Fragile parsing; LLM-embedded separators break | Phase 3 |
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
| Cohere integration | 3 |
| `research_findings` migration to `list[dict]` | 3 |
| Provider/model attribution from `response.raw` | 3 |
| Per-provider error granularity (`AuthError` vs `RateLimited`) | 3 |
| Real token tracking via feenion | 5 |
| Streaming | 6 |
| Async `chat()` | 6 |