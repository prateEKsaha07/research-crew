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

    for source in (START, "researcher", "writer", "critic"):
        graph.add_conditional_edges(source, decide, route_map)

    return graph.compile(checkpointer=MemorySaver())