"""Vector memory — pgvector-backed recall and store (Phase 5).

Storage:
    reports(id, topic, report, created_at)
    findings(id, report_id FK ON DELETE CASCADE, text, url UNIQUE,
             embedding vector(EMBED_DIM))

Recall:
    find_similar(topic) -> nearest findings by cosine distance,
    distance <= MEMORY_MAX_DISTANCE, deduped by url.

Store:
    store(topic, report, findings) -> one transaction: insert report,
    batch-embed findings, insert with ON CONFLICT (url) DO NOTHING.

Any DB or connect error becomes MemoryUnavailableError. Failures are
logged and never propagate further than cli.py.

Embedding model: BAAI/bge-small-en-v1.5 via fastembed, EMBED_DIM=384.
A changed model requires dropping and recreating the tables. No
migration at PoC scale.
"""

import os
import time

from fastembed import TextEmbedding
from pgvector.psycopg import register_vector
import psycopg
from psycopg import Connection
from dotenv import load_dotenv


# -- Constants -------------------------------------------------------
EMBED_DIM              = 384
MEMORY_K               = 3
MEMORY_MAX_DISTANCE    = 0.35
DB_CONNECT_TIMEOUT_S   = 3
EMBED_MODEL_NAME       = "BAAI/bge-small-en-v1.5"


class MemoryUnavailableError(Exception):
    """Raised when the memory layer cannot reach or query Postgres."""


# -- Module state ----------------------------------------------------
_MODEL = None
_SCHEMA_ENSURED = False


def _log(msg: str) -> None:
    print(f"[memory] {msg}", flush=True)


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with fastembed. Lazy-loads the model, cached globally.

    Returns list[list[float]] of length EMBED_DIM per row.
    Monkeypatchable in tests.
    """
    global _MODEL
    if _MODEL is None:
        _MODEL = TextEmbedding(model_name=EMBED_MODEL_NAME)
    vectors = list(_MODEL.embed(texts))
    return [list(map(float, v)) for v in vectors]


def _connect() -> Connection:
    """Open a psycopg connection with the vector type registered."""
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise MemoryUnavailableError("DATABASE_URL is not set")
    try:
        conn = psycopg.connect(url, connect_timeout=DB_CONNECT_TIMEOUT_S)
        register_vector(conn)
        return conn
    except Exception as e:
        raise MemoryUnavailableError(
            f"connect failed: {type(e).__name__}: {e}"
        ) from e

def ensure_schema() -> None:
    """Create tables and the vector extension. Idempotent, once per process."""
    global _SCHEMA_ENSURED
    if _SCHEMA_ENSURED:
        return
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS reports (
                        id SERIAL PRIMARY KEY,
                        topic TEXT NOT NULL,
                        report TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS findings (
                        id SERIAL PRIMARY KEY,
                        report_id INTEGER NOT NULL REFERENCES reports(id)
                            ON DELETE CASCADE,
                        text TEXT NOT NULL,
                        url TEXT NOT NULL UNIQUE,
                        embedding vector({EMBED_DIM}) NOT NULL
                    )
                    """
                )
            conn.commit()
        _SCHEMA_ENSURED = True
    except MemoryUnavailableError:
        raise
    except Exception as e:
        raise MemoryUnavailableError(
            f"ensure_schema failed: {type(e).__name__}: {e}"
        ) from e


def find_similar(topic: str, *, k: int = MEMORY_K) -> list[dict]:
    """Return up to k stored findings nearest to the topic by cosine.

    Each item: {"text": str, "url": str, "distance": float}
    Returns [] on empty DB or when no row is within MEMORY_MAX_DISTANCE.
    Raises MemoryUnavailableError on DB failure.
    """
    t0 = time.perf_counter()
    try:
        ensure_schema()
        vec = _embed([topic])[0]
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT text, url, embedding <=> %s::vector AS distance
                    FROM findings
                    WHERE embedding <=> %s::vector <= %s
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (vec, vec, MEMORY_MAX_DISTANCE, k * 4),
                )
                rows = cur.fetchall()
    except MemoryUnavailableError:
        raise
    except Exception as e:
        _log(f"FAILED: {type(e).__name__}: {e}")
        raise MemoryUnavailableError(
            f"find_similar failed: {type(e).__name__}: {e}"
        ) from e

    # Dedup by url, preserve distance order, truncate to k
    seen = set()
    out = []
    for text, url, distance in rows:
        if url in seen:
            continue
        seen.add(url)
        out.append({"text": text, "url": url, "distance": float(distance)})
        if len(out) >= k:
            break

    latency_ms = int((time.perf_counter() - t0) * 1000)
    dmin = min((r["distance"] for r in out), default=0.0)
    _log(f"recalled={len(out)} distance_min={dmin:.2f} latency={latency_ms}ms")
    return out


def store(topic: str, report: str, findings: list[dict]) -> None:
    """Persist a report and its findings in one transaction.

    Findings with a url that already exists are skipped (ON CONFLICT).
    Raises MemoryUnavailableError on DB failure.
    """
    t0 = time.perf_counter()
    if not findings:
        _log("stored findings=0 latency=0ms")
        return

    try:
        ensure_schema()
        vectors = _embed([f["text"] for f in findings])
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO reports (topic, report) VALUES (%s, %s) "
                    "RETURNING id",
                    (topic, report),
                )
                report_id = cur.fetchone()[0]
                for f, vec in zip(findings, vectors):
                    cur.execute(
                        """
                        INSERT INTO findings
                            (report_id, text, url, embedding)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                        """,
                        (report_id, f["text"], f["url"], vec),
                    )
            conn.commit()
    except MemoryUnavailableError:
        raise
    except Exception as e:
        _log(f"FAILED: {type(e).__name__}: {e}")
        raise MemoryUnavailableError(
            f"store failed: {type(e).__name__}: {e}"
        ) from e

    latency_ms = int((time.perf_counter() - t0) * 1000)
    _log(f"stored findings={len(findings)} latency={latency_ms}ms")