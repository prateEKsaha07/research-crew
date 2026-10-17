Postgres + pgvector is the memory layer of ResearchCrew. It is the database that remembers what the Researcher has already found, so a similar topic later does not need to re-search the web from scratch.

## What pgvector is

pgvector is a PostgreSQL extension. It adds a new column type, `vector(N)`, and a set of distance operators to an ordinary Postgres database. You do not install a separate vector database. You enable the extension and keep using Postgres for everything else .

The core idea: a text embedding is a list of numbers (in ResearchCrew, 384 floats). Two texts that mean similar things produce vectors that point in similar directions. pgvector gives you SQL operators to sort stored vectors by how close they are to a query vector.

## How it is enabled

The `pgvector/pgvector:pg16` Docker image ships Postgres 16 with pgvector already installed. You still need to enable it inside the database once:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Verify:

```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';
```

In Phase 5, this returned `0.8.7`. The same pattern is documented by Microsoft for Azure Postgres: the extension is present but must be activated per database .

## How ResearchCrew uses it

There are two tables:

```sql
reports (id, topic, report, created_at)
findings (id, report_id, text, url UNIQUE, embedding vector(384))
```

When the CLI finishes an approved run, it calls `tools/memory.py:store()`. That function:

1. Inserts a row into `reports`.
2. Embeds each finding's `text` with fastembed (`BAAI/bge-small-en-v1.5`, 384 dims).
3. Inserts each finding with its vector into `findings`. `ON CONFLICT (url) DO NOTHING` skips URLs already stored.

When the Researcher starts, it calls `tools/memory.py:find_similar(topic)`. That function:

1. Embeds the topic string.
2. Runs a SQL query that sorts `findings` by cosine distance to that vector.
3. Filters out anything with distance above `MEMORY_MAX_DISTANCE` (0.35).
4. Returns up to 3 findings as `{text, url, distance}`.

## The distance operator

pgvector provides three distance operators. ResearchCrew uses `<=>` (cosine distance) .

- `0` means identical direction.
- `2` means opposite direction.
- Lower is closer.

The query shape:

```sql
SELECT text, url, embedding <=> %s::vector AS distance
FROM findings
WHERE embedding <=> %s::vector <= 0.35
ORDER BY distance ASC
LIMIT 3;
```

The `%s` is the topic embedding. `<=>` computes cosine distance. `ORDER BY distance ASC` puts the closest first.

The distances you measured in Phase 5 fit this model:

| Query | Nearest stored finding | Distance |
|---|---|---|
| `qubits and superposition` | qubit fact | 0.07 |
| `quantum computing` | qubit fact | 0.21 |
| `RSA encryption` | Shor fact | 0.32 |
| `cooking pasta` | nearest stored | 0.545 |

0.35 keeps the first three and rejects the fourth. The gap between 0.32 and 0.545 is what makes the threshold safe.

## Why this choice over a dedicated vector DB

Three reasons, all from the Phase 5 design:

**One database.** The Phase 6 API will persist jobs to Postgres anyway. A separate vector service would mean two databases, two connection pools, two backup strategies, and a data-sync problem between them. Microsoft makes the same argument for Azure Postgres: add vectors to the database you already run instead of introducing a new store .

**One transaction.** `store()` writes the report and its findings in a single Postgres transaction. If the findings insert fails, the report insert rolls back. With an external vector DB, the two writes cannot be atomic.

**No index needed at this scale.** Without an index, pgvector scans every row and computes the distance. For tables under ~10,000 rows, this is fine . ResearchCrew stores tens of findings per run. The scan is microseconds. An HNSW or IVFFlat index would be premature and adds tuning parameters (`lists`, `probes`) that do nothing at this size.

The limitation is recorded in `08-known-limitations.md`: if `findings` grows past ~100k rows, the sequential scan becomes slow and an ANN index becomes necessary. That is a Phase 6+ concern, not a Phase 5 one.

## What would break it

- **Changing the embedding model.** `vector(384)` is hardcoded. Swap to a 768-dim model and the column rejects inserts. The tables must be dropped and recreated. No migration path exists.
- **`findings.url UNIQUE`.** The same URL cannot exist in two reports. The second run's store skips it. This is intentional for deduplication but means the `findings` table is a global URL registry, not a per-report list.
- **A dead database.** `find_similar` and `store` raise `MemoryUnavailableError`. The Researcher logs a warning and continues without recall. The CLI logs a warning after the report prints and exits 0. Memory is best-effort; the report is the product.