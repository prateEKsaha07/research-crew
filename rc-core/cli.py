"""CLI entry — run the research pipeline for a topic."""
import sys
from uuid import uuid4

from graph.builder import build_graph
from tools.llm import LLMUnavailableError, get_llm
from agents.researcher import ResearchError
from agents.critic import CriticError
from tools.search import SearchUnavailableError
from tools.memory import MemoryUnavailableError, store
from tools.tracing import init_tracing, span


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
        init_tracing()
        # Tag every span in this run with the checkpoint thread_id so
        # the feenion UI groups them as one trace.
        try:
            import feenion
            feenion.set_session(tid)
        except Exception:
            pass

        final = graph.invoke(initial_state, config=config)
    except LLMUnavailableError as e:
        print(f"error: LLM unavailable - {e}", file=sys.stderr)
        sys.exit(1)
    except (SearchUnavailableError, ResearchError) as e:
        print(f"error: research failed - {e}", file=sys.stderr)
        sys.exit(1)
    except CriticError as e:
        print(f"[critic] FAILED: {e}", file=sys.stderr)
        sys.exit(2)

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

    # Confidence scores
    scores = final.get("confidence_scores", {})
    if scores:
        print("\nconfidence_scores:")
        for key in ("coverage", "evidence", "structure", "clarity", "avg"):
            if key in scores:
                print(f"  {key}: {scores[key]}")
    else:
        print("\nconfidence_scores: n/a")

    # Persist to vector memory (best-effort; never fails a finished report)
    if final.get("is_approved"):
        try:
            with span("memory.store", topic=topic):
                store(
                    topic,
                    final["draft"],
                    final["research_findings"],
                )
        except MemoryUnavailableError as e:
            print(f"[memory] FAILED: {e}", file=sys.stderr)

    # Usage summary
    if llm.usage:
        print("\nusage:")
        for provider, tokens in llm.usage.items():
            print(f"  {provider}: {tokens} tokens")
    else:
        print("\nusage: n/a")


if __name__ == "__main__":
    main()