```markdown
# ResearchCrew

> **Four AI agents. One cited report.** Multi-agent research powered by LangGraph.

ResearchCrew is a multi-agent AI system that autonomously researches any topic and produces a structured, citation-backed Markdown report. A **Supervisor** orchestrates a **Researcher**, **Writer**, and **Critic** through an iterative refinement loop, with full observability and vector memory.

Built on a 100% free, self-hostable stack.

---

## How It Works

```
Topic in
   │
   ▼
SUPERVISOR ◄──────────────────┐
   │                          │
   ├──► RESEARCHER            │
   ├──► WRITER                │
   └──► CRITIC ───────────────┘
          │
          ▼
   Final report (cited)
```

**Agent roles:**

| Agent          | Job                                                                                         |
|----------------|---------------------------------------------------------------------------------------------|
| **Supervisor** | Pure rule-based router. No LLM. Decides who works next based on state.                      |
| **Researcher** | Generates search queries, fetches web results, summarizes into cited findings.              |
| **Writer**     | Produces a 900–1400 word Markdown report with inline citations. Revises on critique.        |
| **Critic**     | Scores the draft on Coverage, Evidence, Structure, Clarity. Triggers revisions or approves. |

The pipeline loops through Writer ↔ Critic until the Critic approves or a hard cap of 3 revisions is hit.

---

## Tech Stack

All free and self-hostable. No paid APIs, no cloud vector DBs, no proprietary locked models.

| Layer             | Tech                      | Purpose                                                                                           |
|-------------------|---------------------------|---------------------------------------------------------------------------------------------------|
| **Orchestration** | LangGraph + LangChain     | Stateful multi-agent graph with conditional routing                                               |
| **LLM**           | freelm                    | Multi-provider failover across free tiers (OpenRouter, Google AI Studio, Groq, Cerebras, Mistral) |
| **Search**        | Jiro (self-hosted)        | Web search — self-hosted, free forever                                                            |
| **Memory**        | PostgreSQL + pgvector     | Semantic recall of past findings                                                                  |
| **Observability** | feenion                   | Local per-step tracing                                                                            |
| **Backend**       | FastAPI + Uvicorn         | REST API + SSE streaming                                                                          |
| **Frontend**      | React + Vite + React Flow | Live agent graph visualization                                                                    |
| **Container**     | Docker Compose            | Local orchestration                                                                               |
| **Production**    | Kubernetes + Helm         | Cluster deployment                                                                                |

---

## Repository Layout

```
research-crew/
├── README.md
├── .gitignore
├── docker-compose.yml
├── rc-core/                    # Backend
│   ├── cli.py                  # CLI entry point
│   ├── requirements.txt
│   ├── .env.example
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── researcher.py
│   │   ├── writer.py
│   │   └── critic.py
│   ├── graph/
│   │   ├── state.py            # ResearchState TypedDict
│   │   └── builder.py          # StateGraph construction
│   ├── prompts/
│   ├── tools/                  # Search + memory integrations
│   ├── api/                    # FastAPI app
│   ├── tests/
│   └── Dockerfile
└── rc-web/                     # Frontend
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- `pip` and `venv` (or `uv`)

### Setup

```bash
git clone https://github.com/<your-username>/research-crew.git
cd research-crew

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r rc-core/requirements.txt
```

### Run

```bash
python rc-core/cli.py "quantum computing"
```

Produces a Markdown research report for the given topic.

### Run Tests

```bash
cd rc-core
python -m pytest tests/ -v
```

---

## Architecture

### State

Every node reads from and writes to a shared `ResearchState`:

```python
class ResearchState(TypedDict):
    topic: str
    research_findings: Annotated[list[str], add]  # append-only
    draft: str
    critique: str
    confidence_scores: dict
    revision_count: int
    is_approved: bool
    current_step: str
```

`research_findings` uses an `add` reducer so findings accumulate across Researcher runs instead of being overwritten.

### Routing

The Supervisor (`decide()`) is a pure function invoked as a LangGraph edge. It returns one of:

- `"researcher"` — no findings yet
- `"writer"` — findings exist but no draft
- `"critic"` — draft exists but no critique
- `"writer"` — critique rejected, revisions remain
- `"end"` — approved or revision cap reached

**No LLM calls in the router.** Deterministic, testable, cheap.

### Contracts

Three invariants keep the loop well-defined:

1. **Writer clears `critique`** after producing a draft — signals "feedback consumed, re-evaluate".
2. **Critic always writes non-empty `critique`** — even on approval (uses `"approved"`).
3. **Supervisor reads only presence/absence of `critique`** to decide routing.

Break any of these and the loop either spins forever or terminates early.

---

## Design Decisions

- **Supervisor pattern over peer-to-peer** — easier to debug, extend, and log
- **Rule-based routing over LLM routing** — deterministic, cheap, testable
- **Hard revision cap of 3** — protects free LLM quotas from runaway loops
- **pgvector inside PostgreSQL** — one database, one transaction, fewer services
- **SSE over WebSockets** — simpler, one-way, proxy-friendly
- **Citations validated against state** — prevents hallucination at the critic stage

---

## Contributing

1. Open an issue describing the change
2. Branch from `main`
3. Include tests for new logic
4. Keep the free-stack constraint

---

## License

None at this point

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) — stateful multi-agent orchestration
- [pgvector](https://github.com/pgvector/pgvector) — vector search in PostgreSQL
- [FastAPI](https://fastapi.tiangolo.com/) — backend framework

---

**Multi-agent research, free infrastructure, production-grade orchestration.**
```