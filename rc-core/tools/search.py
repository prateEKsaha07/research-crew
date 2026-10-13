"""Search client — thin wrapper around ddgs (duckduckgo-search).

Phase 3: replaces example.com placeholders with real URLs.
No server, no config. ddgs handles timeouts internally.

Design:
    - One retry on any exception (SEARCH_RETRIES=1, 2 attempts total).
    - Zero results is not an error; returns [].
    - ddgs raises DDGSException("No results found") on empty result
      sets; that is treated as [] and does NOT trigger retry.
    - Non-http(s) URLs and empty snippets are dropped.
    - Latency logged as an int on success only.
"""

from time import perf_counter

from ddgs import DDGS


# -- Constants -------------------------------------------------------
DEFAULT_MAX_RESULTS = 3
SEARCH_RETRIES      = 1


class SearchUnavailableError(Exception):
    """Raised when all search attempts fail.

    Attributes:
        errors: list[Exception] from each failed attempt.
    """

    def __init__(self, errors):
        self.errors = errors
        last = errors[-1] if errors else None
        detail = f"{type(last).__name__}: {last}" if last else "no attempts"
        super().__init__(
            f"search unavailable after {SEARCH_RETRIES + 1} attempts ({detail})"
        )


def _log(msg: str) -> None:
    print(f"[search] {msg}", flush=True)


def _map_results(raw_list, max_results: int) -> list[dict]:
    """Filter and shape ddgs rows into {title, url, snippet}."""
    out = []
    for r in raw_list:
        if not isinstance(r, dict):
            continue
        url     = r.get("href")
        snippet = r.get("body")
        title   = r.get("title") or ""

        if not isinstance(url, str) or not (
            url.startswith("http://") or url.startswith("https://")
        ):
            continue
        if not isinstance(snippet, str) or not snippet.strip():
            continue

        out.append({
            "title":   title,
            "url":     url,
            "snippet": snippet.strip(),
        })
        if len(out) >= max_results:
            break
    return out


def search(query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    """Run a web search. Returns list of {title, url, snippet}.

    Raises:
        SearchUnavailableError: if all attempts fail.
    """
    errors = []
    attempts = SEARCH_RETRIES + 1

    for _ in range(attempts):
        t0 = perf_counter()
        try:
            raw = DDGS().text(query, max_results=max_results)
            raw_list = list(raw) if raw is not None else []
        except Exception as e:
            # ddgs raises DDGSException on empty result sets.
            # Per spec, zero results is [] -- not a failure, no retry.
            if "No results found" in str(e):
                raw_list = []
            else:
                errors.append(e)
                _log(f"FAILED: {type(e).__name__}: {e}")
                continue

        latency_ms = int((perf_counter() - t0) * 1000)
        mapped = _map_results(raw_list, max_results)
        _log(f"query={query} results={len(mapped)} latency={latency_ms}ms")
        return mapped

    last = errors[-1] if errors else RuntimeError("unknown")
    _log(f"FAILED: {type(last).__name__}: {last}")
    raise SearchUnavailableError(errors)