"""Thin wrapper around feenion for optional tracing.

Tracing is best-effort: if feenion is missing, misconfigured, or fails
to initialize, every call becomes a no-op and the run proceeds.

Contract:
    init_tracing() -> bool      # True if enabled, False otherwise.
                                # Never raises.
    span(name, **attrs)         # context manager. No-op when disabled.

Configuration:
    If FEENION_SERVER_URL is set in the environment, use the HTTP
    exporter (feenion's self-hosted server via docker compose on
    localhost:8000).
    Otherwise, use JSONLExporter writing to telemetry/traces.jsonl.

The trace id equals the checkpoint thread_id, which cli.py prints.
"""

import contextlib
import os
from pathlib import Path


_ENABLED = False


def init_tracing() -> bool:
    """Configure feenion once. Returns True on success, False otherwise.

    Never raises. Called exactly once by cli.py, next to get_llm().
    """
    global _ENABLED
    try:
        import feenion
        from feenion.exporters import JSONLExporter  # type: ignore

        server_url = os.environ.get("FEENION_SERVER_URL")
        workspace_id = os.environ.get("FEENION_WORKSPACE_ID")
        api_key = os.environ.get("FEENION_API_KEY")

        if server_url:
            kwargs = {"server_url": server_url}
            if workspace_id:
                kwargs["workspace_id"] = workspace_id
            if api_key:
                kwargs["api_key"] = api_key
            feenion.configure(**kwargs)
            print(f"[tracing] enabled server_url={server_url}")
        else:
            Path("telemetry").mkdir(exist_ok=True)
            feenion.configure(exporter=JSONLExporter("telemetry/traces.jsonl"))
            print("[tracing] enabled exporter=JSONLExporter path=telemetry/traces.jsonl")

        _ENABLED = True
        return True
    except Exception as e:
        print(f"[tracing] disabled: {type(e).__name__}: {e}")
        _ENABLED = False
        return False


@contextlib.contextmanager
def span(name: str, **attrs):
    """Context manager. Wraps feenion.span when enabled, else no-op.

    Attributes are passed as a dict. The span never changes the path
    of the code inside it (invariant 4).
    """
    if not _ENABLED:
        yield None
        return

    try:
        import feenion
        with feenion.span(name, attributes=attrs or None):
            yield None
    except Exception as e:
        # Tracing failure never fails the run.
        print(f"[tracing] span failed: {type(e).__name__}: {e}")
        yield None