import time

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import ResearchState
from agents.researcher import researcher
from agents.writer import writer
from agents.critic import critic
from agents.supervisor import decide


def _apply_reducer(state: ResearchState, out: dict) -> ResearchState:
    """Merge a node's output into state, respecting the add reducer
    on research_findings (append) and overwriting all other keys."""
    merged = dict(state)
    for key, value in out.items():
        if key == "research_findings":
            merged[key] = state.get(key, []) + value
        else:
            merged[key] = value
    return merged


def _reason(name: str, out: dict) -> str:
    if name == "researcher":
        return f"{len(out.get('research_findings', []))} findings appended"
    if name == "writer":
        return f"draft {len(out.get('draft', ''))} chars"
    if name == "critic":
        scores = out.get("confidence_scores", {})
        avg = sum(scores.values()) / len(scores) if scores else 0
        verdict = "approved" if out.get("is_approved") else "revision requested"
        return f"score={avg:.1f}, {verdict}"
    return ""


def logged(name: str, fn):
    def wrapper(state: ResearchState) -> dict:
        t0 = time.perf_counter()
        out = fn(state)
        merged = _apply_reducer(state, out)
        nxt = decide(merged)
        ms = int((time.perf_counter() - t0) * 1000)
        print(f"[p0] {name} -> {nxt} | {_reason(name, out)} | {ms}ms")
        return out
    return wrapper


def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("researcher", logged("researcher", researcher))
    graph.add_node("writer", logged("writer", writer))
    graph.add_node("critic", logged("critic", critic))

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