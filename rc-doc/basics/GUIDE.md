# ResearchCrew — A Plain-English Guide

You have never seen an agentic system or Docker. This document assumes
nothing. It walks through what the project is, how it works, why each
piece exists, and what you would see if you ran it yourself.

Read top to bottom. Each section builds on the last.

---

## 1. What this project does

You type a topic. A minute later you get a written report with real
sources cited.

Example:

    Input:  "quantum computing"
    Output: A 900-1400 word Markdown report with sections
            (Executive Summary, Background, Key Findings, Implications,
            Conclusion) and inline citations like
            [source](https://en.wikipedia.org/wiki/Quantum_computing)

That is the entire product. Everything else exists to make that output
reliable, fast, sourced, and debug-able.

---

## 2. Why "agents" and not just one big prompt

You could write one enormous prompt:

    "Research quantum computing and write me a report with sources."

Three problems with that:

1. **The LLM will invent URLs.** It does not browse. It hallucinates
   links that look plausible and 404 when clicked.
2. **You cannot tell what went wrong.** If the report is bad, was it
   because the LLM did not know enough, or because it wrote badly, or
   because the sources were bad? One prompt hides all of that.
3. **You cannot improve one part without breaking another.** If you
   want better sources, you have to rewrite the whole prompt.

"Agents" fixes all three by splitting the work into small, named,
single-responsibility pieces. Each piece has a defined input and output.
Each piece can be tested alone. Each piece can be replaced without
touching the others.

This project has four agents:

| Agent | Job | Analogy |
|---|---|---|
| Researcher | Find real, cited facts | A research assistant |
| Writer | Turn facts into a report | A staff writer |
| Critic | Score the draft and demand fixes | An editor |
| Supervisor | Decide who goes next | A project manager |

The Supervisor is not a person, it is a rule. "If there is no research
yet, send the Researcher. If there is research but no draft, send the
Writer. If there is a draft but no review, send the Critic. If the
Critic rejected the draft, send the Writer again. If the Critic
approved, we are done."

That is the whole routing logic. It is a pure Python function, no LLM
involved. Deterministic, free, fast, testable.

---

## 3. A full run, step by step

You type:

    python cli.py "quantum computing"

Here is what happens. Times are from a real run on a laptop.

**t = 0.0s — The Supervisor looks at a blank slate.**

Nothing exists yet. No research, no draft, no review. The first branch
of the routing rule fires:

    if no research_findings: return "researcher"

Next node: Researcher.

**t = 0.1s — The Researcher starts.**

First, it checks vector memory. Memory is a small database of findings
from past runs. If you researched "qubits" last week, the Researcher
may already know a few relevant facts. We will come back to memory in
Section 6.

Then it asks the LLM: "Generate 3 to 5 distinct web search queries to
research this topic: quantum computing."

The LLM returns something like:

    quantum computing latest breakthroughs and milestones
    how quantum error correction works
    top companies developing quantum computers
    qubits vs classical bits

**t = 0.5s — The Researcher searches the web.**

For each query, it calls DuckDuckGo (via a Python library called
`ddgs`) and gets back real URLs, titles, and snippets.

    Query: "how quantum error correction works"
    Result 1: { title: "...", url: "https://en.wikipedia.org/wiki/...", snippet: "..." }
    Result 2: { ... }
    Result 3: { ... }

The Researcher keeps the first result whose URL has not already been
used, and asks the LLM to summarize the snippet into one sentence:

    LLM: "Write ONE factual sentence about [query], using ONLY this
          snippet: [snippet]. Max 30 words."

    LLM output: "Quantum error correction uses logical qubits
                 encoded across many physical qubits to suppress
                 decoherence."

The Researcher attaches the URL:

    Finding: {
        text: "Quantum error correction uses logical qubits...",
        url:  "https://en.wikipedia.org/wiki/Quantum_error_correction"
    }

It does this for each query. Total time budget: 18 seconds. If it
exceeds the budget, it stops and moves on with whatever it has.

**t = 17.5s — The Researcher finishes.**

It has 3-4 findings, each with a real URL. These findings go into the
shared "state" (a Python dictionary).

**t = 17.6s — The Supervisor looks at the state again.**

Research exists. No draft yet. Second branch fires:

    if no draft: return "writer"

Next node: Writer.

**t = 17.7s — The Writer starts.**

The Writer gets the topic and the findings. It builds a prompt:

    "Write a 900-1400 word report in Markdown on this topic:
     quantum computing

     Sections (exact headings):
     ## Executive Summary
     ## Background
     ## Key Findings
     ## Implications
     ## Conclusion

     Citation rules:
     - Inline citations in Key Findings ONLY.
     - Use ONLY URLs from the findings below.
     - Format: [source](url).
     ...

     Findings:
     [text] | [url]
     [text] | [url]
     ..."

The LLM writes the draft. It takes 4-6 seconds on a free-tier model.

**t = 23s — The Writer finishes.**

It returns a Markdown draft, ~6000 characters. It also clears the
`critique` field, which signals "the previous round of feedback has
been consumed."

**t = 23.1s — The Supervisor looks again.**

Research exists. Draft exists. No critique yet. Third branch fires:

    if no critique: return "critic"

Next node: Critic.

**t = 23.2s — The Critic starts.**

The Critic asks the LLM to score the draft on four dimensions, 0-10
each: coverage, evidence, structure, clarity. The LLM must return strict
JSON:

    {
      "scores": {
        "coverage": 10,
        "evidence": 10,
        "structure": 10,
        "clarity": 10
      },
      "critique": "approved"
    }

The Critic then does its own math:

    avg = (10 + 10 + 10 + 10) / 4 = 10.0

If avg >= 8, approve. If avg < 8 and the revision cap (3) has not been
hit, reject with a critique. If the cap has been hit, force approve
because we cannot loop forever.

**t = 24s — The Critic approves.**

    Critique: "approved"
    is_approved: True

**t = 24.1s — The Supervisor looks one last time.**

Research exists. Draft exists. Critique exists (non-empty). Approved.
Fifth branch fires:

    otherwise: return "end"

Done.

**t = 24.2s — The CLI prints the report.**

The draft is printed. `confidence_scores` are printed. The report and
its findings are stored in vector memory for next time. A trace file
(or a live tracing server) has recorded every step.

Total time: ~24 seconds.

---

## 4. What "state" is, and why it matters

There is one Python dictionary that every agent reads and writes. It
is called `ResearchState`.

    {
      "topic":             "quantum computing",
      "research_findings": [ {text, url}, {text, url}, ... ],
      "draft":             "## Executive Summary\n\nQuantum computing...",
      "critique":          "approved",
      "confidence_scores": {coverage: 10, evidence: 10, structure: 10, clarity: 10, avg: 10.0},
      "revision_count":    1,
      "is_approved":       True,
      "current_step":      "start",
    }

Agents do not talk to each other directly. They read from state, return
a small dict of changes, and the system merges the changes back in.

Example: the Researcher returns `{"research_findings": [finding1, finding2]}`.
The system merges that into state. The Writer later reads
`state["research_findings"]` and uses it.

This is why the Supervisor can look at state and decide the next step
without talking to the agents. It just reads the dictionary.

Why is this a big deal? Because it makes the whole pipeline inspectable.
You can pause at any point, look at state, and know exactly where you
are. You can resume from a checkpoint. You can serialize state to disk.
None of that is possible with a single giant prompt.

---

## 5. The Writer-Critic loop

The Writer does not always write a good draft first time. The Critic
exists to catch that.

Here is the loop:

    Writer -> draft, clear critique
    Supervisor: no critique? -> Critic
    Critic -> scores + critique, is_approved
    Supervisor: rejected and under cap? -> Writer
    Writer -> revise draft, clear critique
    Supervisor: no critique? -> Critic
    Critic -> scores + critique, is_approved
    ...

The loop stops when:
- The Critic approves (avg >= 8), OR
- The revision count hits 3 (forced approve, cap enforced).

Three invariants make this loop safe:

**Invariant 1: Writer clears critique after drafting.**
If the Writer did not clear critique, the Supervisor would think the
critique is still active, send it back to the Writer again forever.

**Invariant 2: Critic always writes non-empty critique.**
Even when approving, the Critic writes `"approved"`, not `""`. If it
wrote `""`, the Supervisor would think the Critic never ran, and loop
back to the Critic.

**Invariant 3: Supervisor reads only presence/absence of critique.**
It does not parse the critique text. It just asks "is this string empty
or not?" That is what makes the whole thing deterministic.

Breaking any of these three produces an infinite loop or a premature
exit. They are tested explicitly in `tests/test_supervisor.py`.

---

## 6. Memory: why recall findings

Suppose you researched "quantum computing" on Monday. On Tuesday you
research "quantum supremacy". The topics overlap. A lot of the Monday
findings apply.

Without memory, Tuesday re-searches the web from scratch. Same queries,
same results, same summaries. Wasted time, wasted LLM tokens, and the
Tuesday report may contradict Monday's.

With memory:

1. Before searching, the Researcher asks a vector database: "What stored
   findings are within distance 0.35 of the topic 'quantum supremacy'?"
2. The database returns up to 3 findings from past runs.
3. The Researcher seeds its list with those.
4. Then it does live search, but skips any URL already in the recalled
   set.
5. The final report cites both recalled and freshly found sources.

**What is a vector database?**

Normal databases search by exact match: "SELECT * WHERE name = 'Bob'".
A vector database searches by meaning. Each text is converted to a list
of 384 numbers (a "vector") by a small model. Two texts with similar
meaning produce similar vectors. "Quantum error correction" and
"correcting errors in quantum computers" produce vectors that are close
together, even though the words differ.

Postgres, the same database that stores user accounts in a million
other apps, has an extension called `pgvector` that adds vector search.
So we do not need a separate service. It is just a column of type
`vector(384)`.

**How close is "close enough"?**

The distance metric we use is cosine distance. 0 means identical
meaning. 2 means opposite. In practice:

| Query | Nearest finding | Distance |
|---|---|---|
| `qubits and superposition` | qubit fact | 0.07 |
| `quantum computing` | qubit fact | 0.21 |
| `RSA encryption` | Shor fact | 0.32 |
| `cooking pasta` | nearest stored | 0.545 |

We set the threshold at 0.35. That means "RSA encryption" recalls the
Shor finding (0.32 is under 0.35), but "cooking pasta" does not recall
anything (0.545 is over 0.35). The gap between 0.32 and 0.545 gives us
room to be right on both.

**When memory is down**

If the database is unreachable, the Researcher logs a warning and
continues with no recall. The report still ships. Memory is best-effort.
The product is the report.

---

## 7. Tracing: why every step emits a span

When something goes wrong, "it was slow" is not a diagnosis. You need
to know which step was slow.

A "span" is a single unit of work with a start time, end time, and some
metadata. Every node, every LLM call, every search emits one.

Example trace from a real run:

    span memory.find_similar  duration=321ms  recalled=1
    span llm.chat             duration=922ms   prompt_chars=209 max_tokens=500
    span search               duration=3596ms  query="quantum computing..." results=3
    span llm.chat             duration=1077ms  prompt_chars=614 max_tokens=300
    span search               duration=3370ms  results=3
    span llm.chat             duration=702ms
    span search               duration=3200ms  results=3
    span llm.chat             duration=1016ms
    span search               duration=3302ms  results=0
    span researcher           duration=17535ms findings=4
    span llm.chat             duration=4829ms  max_tokens=3500
    span writer               duration=4827ms  draft_chars=5925
    span llm.chat             duration=1438ms  max_tokens=800
    span critic               duration=7462ms  approved=True
    span memory.store         duration=397ms   findings=6

That trace tells you instantly:
- Search is the bottleneck (4 searches x 3-4s each).
- The Writer is fast (4.8s for a 6000-char draft).
- The Critic is slow (7.4s) because the first call may have been the
  repair path.
- Memory is cheap (~350ms per call).

You cannot get that from a log that says "done in 24s."

**Where does the trace go?**

Two options, chosen by one environment variable:

- `FEENION_SERVER_URL` is set: spans ship to a local feenion server.
  A React dashboard at `http://localhost:8000` shows them with timings
  and DAG visualizations.
- `FEENION_SERVER_URL` is not set: spans append to
  `telemetry/traces.jsonl`. One JSON object per line, grep-able.

Both are free and self-hosted. No SaaS, no cloud, no per-seat pricing.

**Tracing is best-effort.**

If feenion is missing, misconfigured, or the server is down, `span()`
becomes a no-op. The run continues. A broken tracer never breaks a
report.

---

## 8. Docker, plainly

Docker is a way to run software in boxes ("containers") that include
everything the software needs. A container has its own filesystem, its
own network, its own ports. It is isolated from the host operating
system except for what you explicitly share.

Why does this matter here?

**Postgres** (the database) is not a Python library. It is a separate
program. Installing it natively on Windows is painful. Patching it is
painful. Removing it cleanly is painful. A Docker container avoids all
that.

The command we ran for Phase 5:

    docker run -d --name rc-pg \
      -e POSTGRES_USER=rc \
      -e POSTGRES_PASSWORD=rc \
      -e POSTGRES_DB=researchcrew \
      -p 5432:5432 \
      -v rc_pgdata:/var/lib/postgresql/data \
      pgvector/pgvector:pg16

Piece by piece:

| Piece | Meaning |
|---|---|
| `docker run -d` | Start a new container, run it in the background |
| `--name rc-pg` | Call this container `rc-pg` |
| `-e POSTGRES_USER=rc` | Set env var inside the container |
| `-e POSTGRES_PASSWORD=rc` | Same |
| `-e POSTGRES_DB=researchcrew` | Create a database called `researchcrew` on first start |
| `-p 5432:5432` | Forward host port 5432 to container port 5432 |
| `-v rc_pgdata:/var/lib/postgresql/data` | Persist data in a named volume, so restarting the container does not lose data |
| `pgvector/pgvector:pg16` | Use the official `pgvector` image built on Postgres 16 |

After that command, `localhost:5432` on your Windows machine is the
container's Postgres. `psql` (or psycopg from Python) connects to
`postgresql://rc:rc@localhost:5432/researchcrew`. Done.

**What is a volume?**

The `-v rc_pgdata:/var/lib/postgresql/data` piece says "inside the
container, `/var/lib/postgresql/data` is where Postgres stores its
tables. Put that directory in a named volume called `rc_pgdata`, not
inside the container." Volumes live on the host and survive container
deletion. So:

    docker rm -f rc-pg
    docker run ... (same command again)

Your data is still there, because the volume still exists.

**Why not install Postgres natively?**

You could. It works. But:
- `pgvector` needs to be compiled or separately installed, depending on
  the Postgres distribution.
- Uninstalling leaves files in weird places.
- Different Windows users get different behaviors.
- The Phase 7 plan is to run everything via Docker Compose anyway:
  app, Postgres, feenion, frontend, all orchestrated together. Starting
  Docker now means Phase 7 is additive, not a rewrite.

**How does Docker relate to the CLI run?**

Not directly, for the pipeline itself. The CLI does not need Docker.
But the CLI touches Postgres (memory) and feenion (tracing). If
Postgres is in a container, `docker run` made it reachable. If feenion
is in a container or run as a local uvicorn server, `docker`/`uvicorn`
made it reachable.

The chain:

    python cli.py -> Researcher -> tools.memory.find_similar()
                                  -> psycopg -> localhost:5432
                                  -> rc-pg Docker container -> Postgres

If you stop the container (`docker stop rc-pg`), `find_similar` throws
`MemoryUnavailableError`, the Researcher logs a warning, and the run
continues with no recall. That is the best-effort design from Section 6
in action.

---

## 9. The tools layer

Everything outside `rc-core/` sits inside `rc-core/tools/`. Each tool
wraps one external dependency and owns exactly one concern.

| Tool | Wraps | Owns |
|---|---|---|
| `llm.py` | `freelm.FreeLLM` | Failover across Gemini/Mistral/OpenRouter/NVIDIA |
| `search.py` | `ddgs` | Web search, one retry, empty-result handling |
| `memory.py` | `psycopg` + `pgvector` + `fastembed` | Store and recall findings |
| `tracing.py` | `feenion` | Emit spans, JSONL or HTTP |

Why a tools layer at all? So that replacing a dependency does not
touch the agents. If you swap `ddgs` for a different search backend
tomorrow, `agents/researcher.py` does not change one line. The tools
layer absorbs the swap.

Every tool follows the same shape:

1. A single public function or class.
2. A single exception type (`LLMUnavailableError`, `SearchUnavailableError`,
   `MemoryUnavailableError`, no exception for tracing because it
   never fails a run).
3. Logs one line per operation.
4. Best-effort where it matters. The product is the report.

---

## 10. What you would see if you ran it

Open two terminals.

**Terminal 1 — feenion server (optional).**

    cd D:\research-crew\feenion
    uvicorn feenion_server.main:app --host 0.0.0.0 --port 8000 --app-dir server

Leave it running. If you skip this, tracing falls back to
`telemetry/traces.jsonl`.

**Terminal 2 — the CLI.**

    cd D:\research-crew\rc-core
    python cli.py "quantum computing"

Output, abbreviated:

    [tracing] enabled server_url=http://localhost:8000
    [memory] recalled=1 distance_min=0.21 latency=321ms
    [llm] provider=<unknown> tokens_in=0 tokens_out=0 latency=922ms model=<unknown>
    [search] query=quantum computing state of the art results=3 latency=3596ms
    [llm] provider=<unknown> ... latency=1077ms ...
    [search] query=how do quantum computers work results=3 latency=3370ms
    ...
    [p2] researcher -> writer | 4 findings appended | 17535ms
    [llm] ... latency=4829ms ...
    [p2] writer -> critic | draft 5925 chars | 4827ms
    [llm] ... latency=1438ms ...
    [critic] coverage=10 evidence=10 structure=10 clarity=10 avg=10.00 approved=True
    [p2] critic -> end | avg=10.0 approved=True | 7462ms
    [checkpoint] thread=bb99f1dc-...
    [checkpoint] revision_count=1 next=()

    ------------------------------------------------------------

    ## Executive Summary

    Quantum computing represents a paradigm shift...

    ...
    revision_count=1

    confidence_scores:
      coverage: 10.0
      evidence: 10.0
      structure: 10.0
      clarity: 10.0
      avg: 10.0

    [memory] stored findings=6 latency=397ms
    usage: n/a

Read the log top to bottom. Every line answers a question:

- `[tracing] enabled` — where do spans go?
- `[memory] recalled=1` — did memory help this run?
- `[search] query=... results=N latency=Xms` — how did search perform?
- `[p2] researcher -> writer` — how long did the researcher take?
- `[critic] coverage=10...` — what did the editor think?
- `[checkpoint] revision_count=1` — how many editor rounds?
- `confidence_scores:` — the editor's scorecard
- `[memory] stored findings=6` — what got saved for next time?

If the browser at `http://localhost:8000` shows a matching trace, the
whole system ran cleanly.

---

## 11. Common failure modes

**`[memory] FAILED: ...`** — Postgres is down. `docker start rc-pg`
fixes it. Or leave it down: the report still ships without recall.

**`[feenion] export failed`** — `FEENION_SERVER_URL` is set but no
server is listening. Either start the server, or comment out the env
var to fall back to JSONL.

**`[search] FAILED: DDGSException: No results found`** — that is not a
failure. It means the query had no results. Treated as `[]` and the
loop moves on.

**`[critic] FAILED: Critic failed to produce valid JSON after repair`** —
the LLM emitted junk twice. The run aborts with exit code 2. Rerun, or
try a different provider.

**`error: research failed - Researcher produced zero findings`** — the
LLM could not produce queries, or no search returned anything useful.
Check network connectivity.

**`error: LLM unavailable - All 4 providers failed`** — all free-tier
keys are down or rate-limited. Check `.env`.

---

## 12. Why this architecture

Three design choices worth understanding.

**Choice 1: The Supervisor is a pure function, not an LLM.**

If the Supervisor were an LLM call, every routing decision would cost
tokens, be non-deterministic, and take 1-2 seconds. A pure function is
free, instant, and reproducible. It also makes routing unit-testable:
`test_supervisor.py` covers all five branches in 8 hand-written tests.

**Choice 2: Findings carry their URL, not the LLM.**

The LLM never sees a URL in a prompt and never writes one in a finding.
The Researcher obtains a real URL from search and attaches it in code.
The Writer is told "use only URLs from the findings below." The result
is that every citation in the report is a URL that was returned by a
real search, not a hallucination.

**Choice 3: Memory and tracing are best-effort.**

If Postgres is down, or feenion is unreachable, or the embedding model
is not installed, the report still ships. These are enhancements, not
prerequisites. The one exception is the LLM chain — if all providers
fail, the run aborts, because there is no report without an LLM.

---

## 13. Where each file lives and why

    rc-core/
      cli.py             Entry point. Wires everything, catches errors,
                         prints the report.
      conftest.py        Pytest path setup + autouse isolation for tests.
      requirements.txt   Pinned versions.
      .env.example       Template. Real .env is gitignored.

      agents/            Four single-responsibility agents.
        supervisor.py      Pure routing function. No LLM.
        researcher.py      Recall + search + summarize.
        writer.py          Draft + revise.
        critic.py          Score + approve or reject.

      graph/             The orchestration layer.
        state.py           The shared dictionary shape.
        builder.py         Assembles nodes and edges. Log decorator.

      prompts/           Pure string formatters. No side effects.
        templates.py       Six prompt templates.

      tools/             External integrations, one module each.
        llm.py             freelm wrapper + failover.
        search.py          ddgs wrapper.
        memory.py          pgvector store and recall.
        tracing.py         feenion wrapper.

      tests/             46 tests, all hermetic (no live network, no
                         live DB unless marked integration).

      telemetry/         Gitignored. Where JSONL spans land when
                         FEENION_SERVER_URL is unset.

The split is not arbitrary:

- `agents/` are the decisions.
- `graph/` is the wiring.
- `prompts/` are the words.
- `tools/` are the outside world.

If you want to change behavior, you edit `agents/` or `prompts/`.
If you want to change routing, you edit `graph/`. If you want to swap a
dependency, you edit `tools/`. Nothing else changes.

---

## 14. A mental model

Picture a small office.

- There is a whiteboard (state).
- There is a manager (Supervisor) who reads the whiteboard and says who
  works next.
- There are three workers (Researcher, Writer, Critic).
- Each worker reads the whiteboard, does their job, and writes their
  update to the whiteboard. They do not talk to each other.
- The manager looks at the whiteboard after every update and decides who
  goes next.
- The workers have access to outside tools (search engine, LLM, database,
  tracing server). Those tools are stable interfaces, not workers.

When you run `python cli.py "topic"`, you are starting a workday. The
manager reads a blank whiteboard and assigns. The workers take turns.
Within a few minutes, the report is on the whiteboard, the manager is
satisfied, and the day is over.

If you draw that on paper, you have the whole system.

---

## 15. Where to go next

If you want to actually change something:

- **Change the routing rules:** edit `agents/supervisor.py:decide()`.
  It is 15 lines of plain Python. Run `tests/test_supervisor.py`
  after.
- **Change the report structure:** edit `prompts/templates.py:_DRAFT`.
  Run `tests/test_writer.py` after.
- **Change the critic rubric:** edit `prompts/templates.py:_CRITIC_SCORE`
  and `agents/critic.py:_DIMENSIONS`. Run `tests/test_critic.py` after.
- **Swap the search backend:** rewrite `tools/search.py` to return the
  same `list[dict]` shape from a different source.
  `agents/researcher.py` does not change.
- **Add a new agent:** add a node in `graph/builder.py`, add a branch
  in `agents/supervisor.py`, add a `test_` for both.

If you want to understand why a phase exists, read that phase's section
in `09-roadmap.md` and the deep-dive in `10-phase5-memory-tracing.md`.

If you want to run it, follow `00-project-overview.md` and
`07-conventions.md`.

Nothing else in this repo is essential for understanding. The rest is
detail.