"""LLM client — thin wrapper around freelm.FreeLLM.

Adds per-call logging and exception translation. Failover, retries,
and provider selection are handled by freelm internally.

Known limitations (Phase 2):
    - Token usage is not surfaced by ChatResponse; logged as 0.
      Real usage tracking arrives with feenion in Phase 5.
    - Provider/model attribution is not exposed; logged as <unknown>.
      If ChatResponse.raw contains it, parse in Phase 3.
"""

import os

from dotenv import load_dotenv
from freelm import (
    FreeLLM,
    FreeLLMError,
    GoogleAIStudio,
    Mistral,
    OpenRouter,
    NIM,
)


# ── Token budgets ────────────────────────────────────────────────────
DEFAULT_MAX_TOKENS = 2000
QUERY_MAX_TOKENS   = 500
SUMMARY_MAX_TOKENS = 300
DRAFT_MAX_TOKENS   = 3500
CRITIC_MAX_TOKENS  = 800   # Phase 4


class LLMUnavailableError(Exception):
    """Raised when freelm fails to produce a response.

    Attributes:
        errors: list[tuple[provider_name, error_string]]
    """

    def __init__(self, errors):
        self.errors = errors
        providers = ", ".join(name for name, _ in errors)
        super().__init__(f"All {len(errors)} providers failed: {providers}")

class LLMClient:
    """Wraps freelm.FreeLLM with logging and error translation."""

    def __init__(self, providers, usage=None):
        self.providers = providers
        self.usage = {} if usage is None else usage
        self._llm = FreeLLM(providers)

    def chat(self, messages, *, temperature=0.0, max_tokens=DEFAULT_MAX_TOKENS):
        """Single entry point. Delegates to freelm. Returns reply string."""
        try:
            response = self._llm.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except FreeLLMError as e:
            print(f"[llm] FAILED: {type(e).__name__}: {e}")
            raise LLMUnavailableError([("<freelm>", str(e))]) from e

        self._record(response)
        return response.text

    def _record(self, response):
        # Phase 2: provider/model/tokens not surfaced by ChatResponse.
        # Log placeholders so the format stays stable.
        print(
            f"[llm] provider=<unknown> tokens_in=0 tokens_out=0 "
            f"latency={int(response.latency_ms)}ms model=<unknown>"
        )


def get_llm() -> LLMClient:
    """Read env, build provider list, return one shared client.

    Providers are added in priority order; missing keys are skipped.

    Raises:
        ValueError: if no provider keys are set.
    """
    load_dotenv()

    providers = []
    if key := os.environ.get("GEMINI_API_KEY"):
        providers.append(GoogleAIStudio(keys=key, priority=0))
    if key := os.environ.get("MISTRAL_API_KEY"):
        providers.append(Mistral(keys=key))
    if key := os.environ.get("OPENROUTER_API_KEY"):
        providers.append(OpenRouter(keys=key))
    if key := os.environ.get("NVIDIA_API_KEY"):
        providers.append(NIM(keys=key, priority=3))

    if not providers:
        raise ValueError(
            "No LLM providers configured. "
            "Copy .env.example to .env and set at least one key."
        )
    return LLMClient(providers=providers)