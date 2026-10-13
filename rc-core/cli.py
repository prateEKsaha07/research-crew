"""CLI entry — run the research pipeline for a topic."""

import sys
from uuid import uuid4

from graph.builder import build_graph
from tools.llm import LLMUnavailableError, get_llm


def main():
    topic = " ".join(sys.argv[1:])
    if not topic:
        print("usage: python cli.py <topic>")
        sys.exit(1)

    # Build the LLM client once
    try:
        llm = get_llm()
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
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

    graph = build_graph(llm)

    try:
        final = graph.invoke(initial_state, config=config)
    except LLMUnavailableError as e:
        print(f"error: LLM unavailable — {e}", file=sys.stderr)
        sys.exit(1)

    # Checkpoint verification
    snap = graph.get_state(config)
    print(f"[checkpoint] thread={tid}")
    print(
        f"[checkpoint] revision_count={snap.values['revision_count']} "
        f"next={snap.next}"
    )

    # Report
    print("\n" + "-" * 60 + "\n")
    print(final["draft"])
    print(f"\nrevision_count={final['revision_count']}")

    # Usage summary
    if llm.usage:
        print("\nusage:")
        for provider, tokens in llm.usage.items():
            print(f"  {provider}: {tokens} tokens")
    else:
        print("\nusage: n/a")


if __name__ == "__main__":
    main()