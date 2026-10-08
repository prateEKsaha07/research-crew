import time 
from graph.state import ResearchState
from typing import Literal
def decide(state: ResearchState) -> Literal["researcher", "writer", "critic", "end"]:
    """Pick the next node. First matching branch wins:

    1. no research_findings                          -> "researcher"
    2. no draft                                      -> "writer"
    3. no critique (Critic has not run)              -> "critic"
    4. not is_approved and revision_count < 3        -> "writer"
    5. otherwise                                     -> "end"
    """
    if not state["research_findings"]:
        return "researcher"
    if not state["draft"]:
        return "writer"
    if not state["critique"]:
        return "critic"
    if not state["is_approved"] and state["revision_count"] < 3:
        return "writer"
    return "end"

# This Python function acts as a **supervisor node** in an agentic workflow (like LangGraph) that decides the next step for an execution graph based on the current state.
# Here is a breakdown of what it does:
# 1. **Timer Start (`t0 = time.perf_counter()`):** Starts a high-precision timer to track execution duration.
# 2. **Decision Making (`nxt, reason = decide(...)`):** Evaluates the graph's current state (`state`) using a helper function (`decide`) to determine what to do next (`nxt`) and why (`reason`).
# 3. **Timer End & Logging (`ms = ...`, `print(...)`):** Calculates how long the decision step took in milliseconds and prints a formatted log.
# 4. **State Update (`return {...}`):** Returns a dictionary containing the next step name, the reason for selecting it, and the execution duration in milliseconds, updating the global application state.

def supervise_node(state: ResearchState) -> dict:
    t0 = time.perf_counter()
    nxt, reason = decide(state=state)
    ms = int((time.perf_counter() - t0) * 1000)
    print(f"supervisor: {nxt} because {reason} in {ms} ms")
    return {"current_step": nxt, "reason": reason, "time_ms": ms}

def route(state: ResearchState) -> str:
    return state["current_step"]