from graph.state import ResearchState


def writer(state: ResearchState) -> dict:
    """Phase 0 stub: returns a fake Markdown draft with 5 sections.

    Reads research_findings for citations and critique (if present)
    to enter revision mode. Clears critique after writing so the
    Supervisor routes back to Critic for re-evaluation.

    Contract: Writer MUST set critique = "" on every return.
    """
    findings = state["research_findings"]
    critique = state["critique"]

    urls = [f.split(" | ", 1)[-1] for f in findings]
    findings_md = "\n".join(f"- {f}" for f in findings)

    title_suffix = " (revised)" if critique else ""
    draft = f"""# Research Findings{title_suffix}

## Executive Summary
This is a placeholder executive summary.

## Background
This is a placeholder background section.

## Key Findings
{findings_md}

Sources: {', '.join(urls)}

## Implications
Placeholder implications.

## Conclusion
Placeholder conclusion.
"""

    return {"draft": draft, "critique": ""}