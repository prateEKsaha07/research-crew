# Graph and State

## State Schema

**File:** `rc-core/graph/state.py`

```python
from typing import Annotated, TypedDict
from operator import add


class Finding(TypedDict):
    text: str
    url: str


class ResearchState(TypedDict):
    topic: str
    research_findings: Annotated[list[Finding], add]   # append-only
    draft: str
    critique: str
    confidence_scores: dict
    revision_count: int
    is_approved: bool
    current_step: str

```
Field Reference
Key	Type	Writer	Purpose
topic	str	CLI / API	Subject to research
research_findings	Annotated[list[Finding], add]	Researcher	Cited evidence: list of {text, url}, append-only
draft	str	Writer	Current Markdown report
critique	str	Writer (clears), Critic (writes)	Feedback or "approved"
confidence_scores	dict	Critic	Per-dimension rubric scores
revision_count	int	Critic	Number of Critic passes
is_approved	bool	Critic	Terminal flag
current_step	str	(reserved)	Diagnostic
The Reducer
research_findings uses Annotated[list[Finding], add]. When a node returns this key, LangGraph runs add(existing, returned) instead of overwriting.

Consequence: Researcher must return only new findings. Returning state["research_findings"] + new causes exponential duplication.

Convention
State keys use snake_case. Every producer returns a dict whose keys are a subset of this schema.

Graph Assembly
File: rc-core/graph/builder.py

build_graph(llm) returns a compiled StateGraph.

Nodes
Three registered nodes. No Supervisor node — decide() is invoked as an edge function.

Node	Function
researcher	agents/researcher.py:researcher
writer	agents/writer.py:writer
critic	agents/critic.py:critic
Edges
Four conditional edges. Every source calls decide().

Source	Calls	Routes to
START	decide(state)	researcher (on fresh state)
researcher	decide(state)	writer
writer	decide(state)	critic
critic	decide(state)	writer or END
No fixed edges. Every transition is conditional.

LLM Injection
llm is injected via functools.partial when registering nodes:

python
graph.add_node("researcher", logged("researcher", partial(researcher, llm=llm)))
graph.add_node("writer", logged("writer", partial(writer, llm=llm)))
graph.add_node("critic", logged("critic", critic))
get_llm() is called once by the caller (cli.py), never at module level.

The route_map
python
route_map = {
    "researcher": "researcher",
    "writer": "writer",
    "critic": "critic",
    "end": END,             # sentinel, not the string "end"
}
Maps decide()'s return value to a node. Unknown return values raise KeyError — fail fast on typos.

Checkpointer
MemorySaver — in-process only. State is lost when the Python process exits.

CLI: each run uses fresh uuid4() thread_id

Phase 6 (FastAPI): thread_id persisted to Postgres for resumable jobs

Log Decorator
Wraps each node:

text
```
def logged(name, fn):
    def wrapper(state):
        t0 = perf_counter()
        out = fn(state)
        merged = apply_reducer(state, out)
        nxt = decide(merged)
        ms = int((perf_counter() - t0) * 1000)
        print(f"[p2] {name} -> {nxt} | {reason(name, out)} | {ms}ms")
        return out          # returns original output, not merged
    return wrapper
```
Critical: merged must respect the add reducer on research_findings. Naive {**state, **out} merge loses prior findings.

Success Check
```bash
python -c "from graph.builder import build_graph; print(list(build_graph(llm=None).get_graph().nodes))"
# Expected: ['__start__', 'researcher', 'writer', 'critic', '__end__']
```
Pipeline Flow
text
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