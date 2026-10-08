import sys
from uuid import uuid4

from graph.builder import build_graph


def main():
    # Join all argv after script name so multi-word topics work:
    #   python cli.py quantum computing  ->  "quantum computing"
    topic = " ".join(sys.argv[1:])
    if not topic:
        print("usage: python cli.py <topic>")
        sys.exit(1)

    initial_state = {
        "topic": topic,
        "research_findings": [],
        "draft": "",
        "critique": "",
        "confidence_scores": {},
        "revision_count": 0,
        "is_approved": False,
        "current_step": "start",
    }

    tid = str(uuid4())
    config = {"configurable": {"thread_id": tid}}

    graph = build_graph()
    final = graph.invoke(initial_state, config=config)

    # ── Checkpoint verification ────────────────────────────────
    snap = graph.get_state(config)
    print(f"[checkpoint] thread={tid}")
    print(
        f"[checkpoint] revision_count={snap.values['revision_count']} "
        f"next={snap.next}"
    )

    # ── Report ─────────────────────────────────────────────────
    print("\n" + "-" * 60 + "\n")
    print(final["draft"])
    print(f"\nrevision_count={final['revision_count']}")


if __name__ == "__main__":
    main()