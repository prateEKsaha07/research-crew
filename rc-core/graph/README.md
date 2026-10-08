---

##  `rc-core/graph/README.md`

# Graph

The orchestration layer. Defines the state contract every agent reads from, and assembles the LangGraph pipeline that routes between agents.

---

## Overview

| File | Purpose |
|---|---|
| [`state.py`](#statepy) | The `ResearchState` TypedDict — the single contract all nodes share |
| [`builder.py`](#builderpy) | Assembles the `StateGraph` with nodes, edges, and checkpointer |

The graph is **Supervisor-only**: there is no Supervisor node. Every transition is a conditional edge whose target is decided by `agents/supervisor.py:decide()`.

---

## `state.py`

**Purpose:** Define the shape of state that flows through the pipeline.

### Schema

```python
from typing import Annotated, TypedDict
from operator import add


class ResearchState(TypedDict):
    topic: str
    research_findings: Annotated[list[str], add]
    draft: str
    critique: str
    confidence_scores: dict
    revision_count: int
    is_approved: bool
    current_step: str
```

### Field Reference

| Key | Type | Written by | Purpose |
|---|---|---|---|
| `topic` | `str` | CLI / API | The subject to research |
| `research_findings` | `Annotated[list[str], add]` | Researcher | Cited evidence, append-only |
| `draft` | `str` | Writer | Current Markdown report |
| `critique` | `str` | Writer, Critic | Feedback or `"approved"` |
| `confidence_scores` | `dict` | Critic | Per-dimension rubric scores |
| `revision_count` | `int` | Critic | Number of Critic passes so far |
| `is_approved` | `bool` | Critic | Terminal flag set on approval |
| `current_step` | `str` | (reserved) | Diagnostic marker |

### The Reducer

`research_findings` uses `Annotated[list[str], add]`. When a node returns this key, LangGraph runs `add(existing, returned)` instead of overwriting.

**Consequence:** the Researcher node must return **only new findings**, never the concatenation. Returning `state["research_findings"] + new` causes exponential duplication across runs.

### Naming Convention

State keys use `snake_case` and match the TypedDict exactly. Every producer must return a `dict` whose keys are a subset of this schema.

---

## `builder.py`

**Purpose:** Assemble and compile the LangGraph pipeline.

### Structure

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import ResearchState
from agents.researcher import researcher
from agents.writer import writer
from agents.critic import critic
from agents.supervisor import decide


def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("researcher", researcher)
    graph.add_node("writer", writer)
    graph.add_node("critic", critic)

    route_map = {
        "researcher": "researcher",
        "writer": "writer",
        "critic": "critic",
        "end": END,
    }

    graph.add_conditional_edges(START, decide, route_map)
    graph.add_conditional_edges("researcher", decide, route_map)
    graph.add_conditional_edges("writer", decide, route_map)
    graph.add_conditional_edges("critic", decide, route_map)

    return graph.compile(checkpointer=MemorySaver())
```

### Nodes

Three registered nodes. No Supervisor node — `decide()` is invoked as an edge function.

| Node | Function |
|---|---|
| `researcher` | `agents/researcher.py:researcher` |
| `writer` | `agents/writer.py:writer` |
| `critic` | `agents/critic.py:critic` |

### Edges

Four conditional edges. Every source calls `decide()` to pick the next node.

| Source | Calls | Routes to |
|---|---|---|
| `START` | `decide(state)` | `researcher` (on fresh state) |
| `researcher` | `decide(state)` | `writer` |
| `writer` | `decide(state)` | `critic` |
| `critic` | `decide(state)` | `writer` or `END` |

**No fixed edges.** Every transition is conditional.

### Why Every Source Needs a Conditional Edge

LangGraph requires each node to declare its outgoing edge(s). Since every node returns to the Supervisor conceptually, but the Supervisor is not a node, each node needs its own `add_conditional_edges(..., decide, route_map)` call.

**Forgetting one** causes `ValueError: Node 'X' has no outgoing edges` at compile time.

### The `route_map`

Maps the string `decide()` returns to a target node:

| `decide()` returns | `route_map` resolves to |
|---|---|
| `"researcher"` | node `researcher` |
| `"writer"` | node `writer` |
| `"critic"` | node `critic` |
| `"end"` | `END` sentinel |

The map is what makes routing explicit. A typo in `decide()` returns a string that isn't in the map, and LangGraph raises `KeyError` — you fail fast instead of silently routing to a nonexistent node.

### Checkpointer

`MemorySaver` persists state by `thread_id`. In-process only — state is lost when the Python process exits.

**For CLI runs:** each `python cli.py` invocation generates a fresh `uuid4()` thread_id, so runs are independent.

**For Phase 6 (FastAPI):** the same checkpointer pattern supports resumable jobs keyed by persistent `thread_id`s.

---

## Pipeline Flow

```
              ┌──────────────┐
              │     START    │
              └──────┬───────┘
                     │ decide()
                     ▼
              ┌──────────────┐
       ┌─────►│  researcher  │─────┐
       │      └──────────────┘     │
       │            │              │
       │            │ decide()     │
       │            ▼              │
       │      ┌──────────────┐     │
       │ ┌───►│    writer    │───┐ │
       │ │    └──────────────┘   │ │
       │ │          │            │ │
       │ │          │ decide()   │ │
       │ │          ▼            │ │
       │ │    ┌──────────────┐   │ │
       │ └────│    critic    │───┘ │
       │      └──────┬───────┘     │
       │             │             │
       └─────────────┘             │
             decide()              │
                                  ▼
                            ┌──────────┐
                            │   END    │
                            └──────────┘
```

The loop between Writer and Critic executes until the Critic approves or `revision_count` hits 3.

---

## Success Check

From `rc-core/`:

```bash
python -c "from graph.builder import build_graph; print(list(build_graph().get_graph().nodes))"
```

**Expected output:**

```
['__start__', 'researcher', 'writer', 'critic', '__end__']
```

Five entries. Three worker nodes plus two sentinels. No `supervisor` node.

**If you see a `ValueError` about outgoing edges:** a conditional edge is missing.
**If `__start__` or `__end__` is missing:** the `START`/`END` wiring is broken.
**If an unexpected node appears:** an extra `add_node` call exists.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| **No Supervisor node** | The Supervisor is a routing function, not a worker. Invoking it as an edge avoids a node visit per hop. |
| **Every transition conditional** | Keeps all routing logic in one place (`decide()`). No hidden fixed edges. |
| **`MemorySaver` in Phase 0** | Simplest checkpointer. Swap for `SqliteSaver` when persistent resume is needed. |
| **Explicit `route_map`** | Fail-fast on typos. Unknown return values raise `KeyError` at runtime instead of silently misrouting. |
| **Reducer on `research_findings`** | Accumulate across Researcher runs without manual concatenation. |
| **`snake_case` state keys** | Match Python conventions; consistent with agent code. |

---

## File Layout

```
graph/
├── README.md      ← this file
├── __init__.py
├── state.py       ← ResearchState TypedDict
└── builder.py     ← StateGraph assembly
```

---

## Extension Points

Where future phases plug in:

| Phase | Change to `graph/` |
|---|---|
| Phase 2 | Node prompts updated in `agents/`, not here. No graph changes. |
| Phase 3 | Researcher node imports real search tool. No graph changes. |
| Phase 4 | Critic node gets real rubric. No graph changes. |
| Phase 5 | Observability decorator wraps nodes at registration. |
| Phase 6 | `api/main.py` imports `build_graph()`. Checkpointer may swap to `SqliteSaver`. |
| Phase 7 | `Dockerfile` copies this folder into the image. |

**The graph layer should rarely change.** If a phase requires touching `builder.py`, ask whether the change belongs in an agent's contract instead.

---

## Debugging Tips

- **`ValueError: no outgoing edges`** — a node is missing `add_conditional_edges`. All three workers plus `START` need one.
- **`KeyError` on `decide()` return value** — the string returned isn't in `route_map`. Add it or fix the typo.
- **Loop runs past `revision_count = 3`** — check the Supervisor's branch 4 condition (`< 3`, not `<= 3`).
- **State resets between invocations** — `MemorySaver` is in-process. Use the same process for persistence to apply.
- **Two runs interfere** — same `thread_id` reused. Generate a fresh `uuid4()` per invocation.
```

---

## Commit

```bash
cd D:\research-crew
git add rc-core/graph/README.md
git commit -m "docs: graph folder README"
```

---
