# Tools

External integrations live in `rc-core/tools/`. Each is a focused module with a clear contract.

## `tools/llm.py` (DONE — Phase 2)

Wraps `freelm.FreeLLM` with a 4-provider failover chain and adds logging plus error translation.

### Public Surface

```python
LLMClient(providers, usage=None)
LLMClient.chat(messages, *, temperature=0.0, max_tokens=DEFAULT_MAX_TOKENS) -> str
LLMUnavailableError(errors)   # errors: list[tuple[provider_name, error_str]]
get_llm() -> LLMClient        # raises ValueError if no keys
Constants
text
DEFAULT_MAX_TOKENS = 2000
QUERY_MAX_TOKENS   = 500     # researcher_query_gen
SUMMARY_MAX_TOKENS = 300     # researcher_summarize
DRAFT_MAX_TOKENS   = 3500    # writer_draft, writer_revise
CRITIC_MAX_TOKENS  = 800     # Phase 4
Provider Chain
Priority order: Gemini → Mistral → OpenRouter → NVIDIA NIM

Cohere: deferred to Phase 3 (1,000 calls/month cap fits last-resort role)

Groq: commented out (region-restricted)

All providers accept keys= (not api_key=). Gemini and NIM accept priority=.

Log Formats
text
[llm] provider=<name> tokens_in=<N> tokens_out=<M> latency=<ms>ms model=<name>
[llm] FAILED: <ExceptionType>: <message>
Known Phase 2 limitation: provider=<unknown>, model=<unknown>, tokens_in=0, tokens_out=0. ChatResponse doesn't expose them. Real tracking arrives with feenion in Phase 5.

Contract
Never reimplements failover. Delegates to freelm.FreeLLM. Any provider added to freelm is picked up by get_llm() without code changes.

Environment
.env.example:

text
GEMINI_API_KEY=
MISTRAL_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=
# COHERE_API_KEY=
# GROQ_API_KEY=
get_llm() skips providers with missing keys. Raises ValueError if all keys are missing.

tools/search.py (Phase 3 — NEXT)
Jiro HTTP client.

Planned interface:

text
search(query: str, *, max_results: int = 3) -> list[dict]
# Returns: [{"title": str, "url": str, "snippet": str}, ...]
Details to be designed in Phase 3.

tools/memory.py (Phase 5)
pgvector similarity search + embed + store findings.

Planned interface:

text
find_similar(topic: str, *, k: int = 3) -> list[str]
store(report: str, findings: list[dict]) -> None
text

---