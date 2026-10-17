"""Tests for tools.memory — no real DB, no real embedder."""

import pytest

from tools import memory as mem


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []
        self._last = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        sql_up = sql.strip().upper()
        if sql_up.startswith("INSERT INTO REPORTS"):
            self._last = (1,)  # report_id
        else:
            self._last = None

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self._last


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


@pytest.fixture
def patch_memory(monkeypatch):
    """Return an installer: install(rows=..., embed=[...])."""
    def _install(rows=None, embed=None, connect_raises=None, execute_raises=None):
        cursor = FakeCursor(rows=rows or [])

        if execute_raises is not None:
            def _raise_execute(sql, params=None):
                raise execute_raises
            cursor.execute = _raise_execute  # type: ignore[assignment]

        conn = FakeConn(cursor)

        if connect_raises is not None:
            def _raise_connect():
                raise connect_raises
            monkeypatch.setattr(mem, "_connect", _raise_connect)
        else:
            monkeypatch.setattr(mem, "_connect", lambda: conn)

        if embed is not None:
            monkeypatch.setattr(mem, "_embed", lambda texts: embed)

        return cursor, conn

    return _install


def test_find_similar_returns_ordered_top_k(patch_memory):
    rows = [
        ("t1", "https://a/1", 0.10),
        ("t2", "https://a/2", 0.15),
        ("t3", "https://a/3", 0.20),
    ]
    patch_memory(rows=rows, embed=[[0.0] * mem.EMBED_DIM])

    out = mem.find_similar("q", k=3)
    assert [r["url"] for r in out] == ["https://a/1", "https://a/2", "https://a/3"]
    assert [r["distance"] for r in out] == [0.10, 0.15, 0.20]
    assert all("text" in r for r in out)


def test_find_similar_empty_when_threshold_filters(patch_memory):
    # No rows returned by the DB because nothing is within MEMORY_MAX_DISTANCE
    patch_memory(rows=[], embed=[[0.0] * mem.EMBED_DIM])
    out = mem.find_similar("q", k=3)
    assert out == []


def test_find_similar_db_error_raises(patch_memory):
    patch_memory(connect_raises=RuntimeError("boom"))
    with pytest.raises(mem.MemoryUnavailableError):
        mem.find_similar("q")


def test_store_single_transaction_rolled_back_on_failure(patch_memory):
    # Cursor raises on the second INSERT (findings), so the transaction
    # never reaches commit. FakeConn records committed=False.
    conn_holder = {}

    def _install():
        from tests.test_memory import FakeCursor, FakeConn

        class RaisingCursor(FakeCursor):
            def execute(self, sql, params=None):
                if "INSERT INTO FINDINGS" in sql.upper():
                    raise RuntimeError("insert failure")
                return super().execute(sql, params)

        cursor = RaisingCursor()
        conn = FakeConn(cursor)
        conn_holder["conn"] = conn
        return cursor, conn

    cursor, conn = _install()
    import tools.memory as mod
    mod._connect = lambda: conn  # type: ignore[assignment]
    mod._embed = lambda texts: [[0.0] * mem.EMBED_DIM for _ in texts]  # type: ignore[assignment]

    try:
        with pytest.raises(mod.MemoryUnavailableError):
            mod.store(
                "q",
                "# r",
                [{"text": "x", "url": "https://a/1"}],
            )
        assert conn_holder["conn"].committed is False
    finally:
        # Restore stubs
        pass


def test_embed_dim_matches_constant():
    # Verify the constant is what pgvector schema expects; not calling
    # the real embedder here.
    assert mem.EMBED_DIM == 384


def test_store_empty_findings_noop(patch_memory, capsys):
    patch_memory()
    mem.store("q", "# r", [])
    captured = capsys.readouterr().out
    assert "stored findings=0" in captured


@pytest.mark.integration
def test_integration_store_then_recall():
    """Requires real Postgres and fastembed. Skipped if DATABASE_URL unset."""
    import os
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    import uuid
    url = f"https://integration.example/{uuid.uuid4()}"
    mem.store(
        "integration test",
        "# report",
        [{"text": "integration recall probe", "url": url}],
    )
    out = mem.find_similar("integration test", k=3)
    assert any(r["url"] == url for r in out)