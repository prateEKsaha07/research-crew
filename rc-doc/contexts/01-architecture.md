# Architecture

## Agent Flow
┌──────────────┐
│ START │
└──────┬───────┘
│ decide()
▼
┌──────────────┐
│ SUPERVISOR │ (invoked as conditional edge,
│ decide() │ not a node)
└──────┬───────┘
│
┌──────────────────┼──────────────────┐
▼ ▼ ▼
(no findings) (no draft) (draft exists)
▼ ▼ ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│RESEARCHER│ │ WRITER │ │ CRITIC │
└────┬─────┘ └────┬─────┘ └────┬─────┘
│ │ │
└─────────────────┴─────────────────┘
│
▼
(all sources call
decide() again)

text

## Supervisor Routing Rules

First matching branch wins:

| # | Condition | Returns |
|---|---|---|
| 1 | `not research_findings` | `"researcher"` |
| 2 | `not draft` | `"writer"` |
| 3 | `not critique` | `"critic"` |
| 4 | `not is_approved and revision_count < 3` | `"writer"` |
| 5 | otherwise | `"end"` |

**Key design:** Structural checks precede content checks. Branch 3 ("has Critic run?") before branch 4 ("was it good?").

## The Supervisor Pattern

The Supervisor is **not a node**. It's a pure function `decide(state) -> str` invoked as a LangGraph conditional edge from every source: `START`, `researcher`, `writer`, `critic`.

**Advantages:**
- All routing logic in one place
- Deterministic (no LLM call for routing)
- Cheap (no token cost)
- Testable in isolation

**Contract:** every node's outgoing edge calls `decide()`. There are no fixed edges.

## Iterative Refinement Loop
Writer produces draft (critique cleared)
↓
Supervisor routes to Critic
↓
Critic scores and writes critique (non-empty)
↓
Supervisor sees critique + not approved + revision_count < 3
↓
Routes back to Writer
↓
Writer revises, clears critique
↓
...loop until Critic approves or cap reached

text

## The Three (Five) Invariants

See `02-agents.md` and `03-graph-and-state.md` for full contracts. Summary:

1. **Writer clears critique** after producing a draft
2. **Critic always writes non-empty critique** (including on approve)
3. **Supervisor reads only presence/absence of critique**
4. **`tools/llm.py` never reimplements failover** — delegates to freelm
5. **`research_findings` nodes return only new data** — reducer handles merge

Breaking any of these causes infinite loop, early termination, or corrupt state.

## Data Flow Timings (target)
T+0.0 submit topic
T+0.1 return job_id
T+0.2 supervisor → researcher
T+1-4 Jiro parallel + summarize
T+4.1 → writer
T+10 draft ready
T+10.1 → critic
T+12 score / revise (max 3)
T+20-30 approved → save to DB + pgvector → completed

text

**Phase 2 measured:** ~22s end-to-end, 6 LLM calls, real LLM report.