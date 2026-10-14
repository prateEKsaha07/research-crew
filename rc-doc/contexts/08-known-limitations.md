# Known Limitations

Current state as of Phase 4 (tag `v0.5-critic`).

## Phase 2 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| `provider=<unknown>`, `model=<unknown>` in `[llm]` logs | Can't attribute calls to specific providers | Phase 5 (feenion) |
| `tokens_in=0`, `tokens_out=0` in `[llm]` logs | No token cost visibility | Phase 5 (feenion) |
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

## Phase 4 Limitations

| Limitation | Impact | Phase to Address |
|---|---|---|
| Critic latency is one LLM call per pass (~1-2s on free tier) | Adds to wall time when the revise loop fires | Acceptable for PoC |
| LLM-judge score variance across providers | Same draft can score 8 on Gemini and 6 on Mistral | Prompt anchors mitigate; no cross-provider calibration |
| JSON validity depends on provider | Some free-tier models occasionally emit fences or prose around the JSON | One repair pass, then `CriticError` |
| Critic approves at 10/10/10/10 first pass on some runs | Weak signal; the rubric is not always exercised | Consider tightening anchors in Phase 5 |
| Writer citation format drifts (`[url]` instead of `[text](url)`) | Critic does not always catch it | Consider Critic prompt tightening in Phase 5 |

## Infrastructure Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `MemorySaver` is in-process | No resume across processes | Phase 6 |
| Fresh `uuid4` per CLI run | Can't resume a prior job | Phase 6 |
| No 5th LLM provider | Cohere not in freelm; Cerebras needs a card | Deferred |
| Groq commented out | Region-restricted for user | N/A |
| No observability integration | Can't inspect agent traces | Phase 5 |
| No Docker / K8s | Manual setup only | Phase 7 / 8 |

## Schema Limitations

| Limitation | Impact | Phase |
|---|---|---|
| No version field in state | Can't detect schema drift | Consider Phase 6 |

## Prompt Limitations

| Limitation | Impact | Phase |
|---|---|---|
| `writer_draft` output starts with `##` not `#` | Missing top-level title | Consider Phase 5 prompt tweak |
| No system/user message split | All prompts are single-user-message | Phase 5+ if needed |
| No few-shot examples in `writer_draft` | Consistency depends on prompt adherence | Consider Phase 5 |

## Deferred Improvements

| Item | Phase |
|---|---|
| Real token tracking via feenion | 5 |
| Provider/model attribution from `response.raw` | 5 |
| 5th provider (Cohere or Cerebras) | Deferred |
| Streaming | 6 |
| Async `chat()` | 6 |