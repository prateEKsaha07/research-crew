`rc-core/agents/README.md`
# Agents

The four agents that drive the ResearchCrew pipeline. Each agent is a LangGraph node or edge function with a specific contract.

## Overview

| Agent | Type | Role |
|---|---|---|
| [Supervisor](#supervisor) | Edge function | Routes to the next node based on state |
| [Researcher](#researcher) | Node | Gathers cited evidence from the web |
| [Writer](#writer) | Node | Produces the Markdown draft |
| [Critic](#critic) | Node | Scores the draft and triggers revisions |

The Supervisor is not a node — it's a pure function invoked as a LangGraph conditional edge. This keeps routing decisions centralized and testable.

---

## Supervisor

**File:** `supervisor.py`
**Type:** Edge function (no side effects, no LLM)
**Signature:** `decide(state: ResearchState) -> Literal["researcher", "writer", "critic", "end"]`

### Responsibility

Reads the current state and returns the next node name. No LLM calls, no state writes, no I/O. Pure function.

### Routing Rules

First matching branch wins:

| # | Condition | Returns |
|---|---|---|
| 1 | `not research_findings` | `"researcher"` |
| 2 | `not draft` | `"writer"` |
| 3 | `not critique` | `"critic"` |
| 4 | `not is_approved and revision_count < 3` | `"writer"` |
| 5 | otherwise | `"end"` |

### Invariant

Structural checks precede content checks. Branch 3 (structural: "has the Critic run?") comes before branch 4 (content: "was it good?"). Reordering breaks the loop.

---

## Researcher

**File:** `researcher.py`
**Type:** Node
**Signature:** `researcher(state: ResearchState) -> dict`

### Responsibility

Gather evidence about the topic. Produce a list of cited findings.

### Flow

1. Query pgvector for similar past topics — inject as priors
2. Generate 3–5 search queries via LLM
3. Call Jiro in parallel for each query
4. Fetch top pages and summarize each into a cited finding
5. Append to `research_findings` via the `add` reducer

### Inputs

| Key | Use |
|---|---|
| `topic` | Subject to research |
| `research_findings` | Read for existing priors (append-only) |

### Output

```python
{"research_findings": [<new findings only>]}
```

**Contract:** Returns **only new findings**, never the concatenation with prior state. The reducer handles the merge. Returning concatenated data causes exponential duplication.

### State Writes

- `research_findings` (via reducer)

---

## Writer

**File:** `writer.py`
**Type:** Node
**Signature:** `writer(state: ResearchState) -> dict`

### Responsibility

Produce a 900–1400 word Markdown report grounded in the Researcher's findings.

### Flow

1. Read topic and all accumulated findings
2. If `critique` is non-empty, enter revision mode — address feedback specifically
3. Structure the draft in 5 sections:
   - Executive Summary
   - Background
   - Key Findings (inline citations)
   - Implications
   - Conclusion
4. Every claim in Key Findings must cite a source URL from `research_findings`

### Inputs

| Key | Use |
|---|---|
| `topic` | Report subject |
| `research_findings` | Evidence and citations |
| `critique` | Revision feedback (if present) |

### Output

```python
{"draft": <markdown>, "critique": ""}
```

### State Writes

- `draft`
- `critique` → **always cleared to `""`**

### Contract

**Writer MUST set `critique = ""` on every return.** This signals "feedback consumed, re-evaluate" and routes the Supervisor back to the Critic. Without this, the Supervisor sees the still-populated critique and loops Writer → Writer indefinitely.

---

## Critic

**File:** `critic.py`
**Type:** Node
**Signature:** `critic(state: ResearchState) -> dict`

### Responsibility

Score the draft against a rubric and decide whether to approve or request revision.

### Rubric

Score each dimension 0–10:

| Dimension | Question |
|---|---|
| **Coverage** | Are all findings addressed? |
| **Evidence** | Are citations present and relevant? |
| **Structure** | Is the logical flow clear? |
| **Clarity** | Is it readable? |

Average ≥ 8 → approve. Otherwise, request revision with specific feedback.

### Inputs

| Key | Use |
|---|---|
| `draft` | Report to evaluate |
| `research_findings` | Source of truth for citation verification |

### Output

```python
{
    "critique": <non-empty string>,
    "is_approved": bool,
    "revision_count": int,
    "confidence_scores": {...}
}
```

### State Writes

- `critique`
- `is_approved`
- `revision_count`
- `confidence_scores`

### Contract

**Critic ALWAYS writes a non-empty `critique`** — including on approval.

| Outcome | `critique` | `is_approved` |
|---|---|---|
| Reject | Specific feedback | `False` |
| Approve | `"approved"` | `True` |
| Forced approve (cap hit) | `"approved"` or `"approved (cap reached)"` | `True` |

Empty `critique` means one thing only: **Critic has not run yet**. Returning `""` on approve causes the Supervisor to route back to Critic forever.

### Citation Verification

Critic must verify that every URL cited in the draft exists in `research_findings`. Citations not present in findings are flagged as hallucinations and trigger revision.

---

## The Three Invariants

These contracts keep the pipeline coherent. Break any one and the loop either spins forever or terminates early.

| # | Invariant | Set By | Why |
|---|---|---|---|
| 1 | Writer clears `critique` after producing a draft | `writer.py` | Signals "feedback consumed, re-evaluate" |
| 2 | Critic always writes non-empty `critique` | `critic.py` | Empty means "not yet critiqued" — never a valid post-critique state |
| 3 | Supervisor reads only presence/absence of `critique` | `supervisor.py` | Structural check before content check |

### State Transitions the Contracts Enforce

| State | Meaning | Next |
|---|---|---|
| `critique == ""`, `draft == ""` | Nothing written | → Researcher |
| `critique == ""`, `draft != ""` | Draft fresh, un-reviewed | → Critic |
| `critique != ""`, `is_approved == False` | Rejected, revision available | → Writer |
| `critique != ""`, `is_approved == True` | Approved | → END |

Every row is distinguishable. That's the whole point of the contract set.

---

## File Layout

```
agents/
├── README.md         ← this file
├── __init__.py
├── supervisor.py     ← decide() router
├── researcher.py     ← evidence gatherer
├── writer.py         ← draft producer
└── critic.py         ← quality gate
```

---

## Testing

Each agent's contract is verified by tests in `../tests/`:

| File | Covers |
|---|---|
| `test_supervisor.py` | Routing for all 5 branches + stale-flag edge case |
| `test_researcher.py` | Returns only new findings, not concatenation |
| `test_writer.py` | Clears critique, produces 5 sections |
| `test_critic.py` | Non-empty critique on all outcomes |
| `test_graph.py` | Full pipeline terminates in ≤ 3 revisions |

Run from `rc-core/`:

```bash
python -m pytest tests/ -v
```

---

## Debugging Tips

- **Infinite loop?** Check invariant 1 or 2. Whichever contract was broken, one node is failing to signal completion.
- **Pipeline terminates without a draft?** Supervisor routed past Writer. Check that Writer's output actually populates `draft`.
- **Duplicate findings?** Researcher returned the concatenation instead of only new data.
- **Citation check failing?** Critic is comparing draft URLs against `research_findings`. Verify the Writer is emitting URLs in a parseable format.
---

## Commit

```bash
cd D:\research-crew
git add rc-core/agents/README.md
git commit -m "docs: agents folder README"
```

---

