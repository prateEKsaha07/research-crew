# rc-core/graph/builder.py
import time
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import ResearchState
from agents.supervisor import decide
from agents.researcher import researcher
from agents.writer import writer
from agents.critic import critic

PHASE = "p0"
ROUTE_MAP = {"researcher": "researcher", "writer": "writer", "critic": "critic", "end": END}


def _apply_reducer(state, out):
    merged = dict(state)
    for key, value in out.items():
        if key == "research_findings":
            merged[key] = state.get(key, []) + value
        else:
            merged[key] = value
    return merged


def _reason(name, out, state):
    if name == "researcher":
        return f"{len(out.get('research_findings', []))} findings appended"
    if name == "writer":
        return f"draft {len(out.get('draft', ''))} chars"
    if name == "critic":
        score = out.get("confidence_scores", {}).get("avg")
        score_txt = f"score={score}, " if score is not None else ""
        return score_txt + ("approved" if out.get("is_approved") else "revision requested")
    return ""


def logged(name, fn):
    def wrapper(state):
        t0 = time.perf_counter()
        out = fn(state)
        ms = int((time.perf_counter() - t0) * 1000)
        nxt = decide(_apply_reducer(state, out))
        print(f"[{PHASE}] {name} → {nxt} | {_reason(name, out, state)} | {ms}ms")
        return out
    return wrapper


def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("researcher", logged("researcher", researcher))
    g.add_node("writer", logged("writer", writer))
    g.add_node("critic", logged("critic", critic))
    for src in (START, "researcher", "writer", "critic"):
        g.add_conditional_edges(src, decide, ROUTE_MAP)
    return g.compile(checkpointer=MemorySaver())