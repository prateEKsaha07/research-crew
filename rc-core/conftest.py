"""Shared pytest fixtures for rc-core.

Autouse fixture isolates the external services (Postgres + fastembed +
feenion) so unit tests are hermetic and fast.

Tests that want the real services can opt out with @pytest.mark.integration.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def _isolate_externals(monkeypatch, request):
    """Stub memory + tracing for every test unless marked integration
    or the test itself lives in test_memory.py / test_tracing.py
    (those modules patch internals directly)."""
    if "integration" in request.keywords:
        yield
        return

    module_name = request.module.__name__.rsplit(".", 1)[-1]
    if module_name in ("test_memory", "test_tracing"):
        yield
        return

    # Memory: stub the high-level functions used by agents and cli.
    from tools import memory as mem

    monkeypatch.setattr(mem, "find_similar", lambda topic, *, k=3: [])
    monkeypatch.setattr(mem, "store", lambda *a, **kw: None)
    monkeypatch.setattr(
        mem, "_embed", lambda texts: [[0.0] * mem.EMBED_DIM for _ in texts]
    )

    try:
        from agents import researcher as res_mod
        monkeypatch.setattr(res_mod, "find_similar", lambda topic, **kw: [])
    except ImportError:
        pass

    from tools import tracing as tr
    monkeypatch.setattr(tr, "_ENABLED", False)

    yield

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests that require the real Postgres + fastembed stack",
    )