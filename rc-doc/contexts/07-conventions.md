# Conventions

## Response Rules for AI

- Always name the exact file/path you are discussing
- Prefer pseudo-code, decision trees, checklists, atomic next steps
- **NEVER emit full source code or complete files unless the user says "write code" / "implement" / "generate"**
- If the user asks for code without those exact trigger words → reply with pseudo-code only and ask for confirmation
- Stay inside the current phase unless asked to jump
- Token-efficient. No filler.
- When ambiguous, ask which phase we are in before answering

## Development Discipline

- **One phase = one new class of change.** Never mix concerns.
- **Design first** (pseudo-code), verify, then "write code."
- **Every phase ends runnable + git-committable.**
- **Vertical slice methodology**, not horizontal layers.
- **Tests before swapping fakes for real implementations.**
- **ASCII-only console output** for Windows PowerShell compatibility (`->` not `→`, `-` not `─`).
- **No code generation** until user says "write code" / "implement" / "generate."

## Git Convention

- One branch per phase: `phase-N-slug`
- Merge to `main` on phase completion
- Tag on merge: `v0.N-slug`
- Commit message: `phase-N: what changed`

**Branches shipped:**
- `phase-0-skeleton`
- `phase-1-checkpointing`
- `phase-2-real-llm`
- `phase-3-jiro` (current)

**Tags shipped:**
- `v0.1-skeleton`
- `v0.2-checkpointing`
- `v0.3-real-llm`

## Testing Expectations

- Phase 0–2: manual run + console output
- Phase 3+: unit test per agent
- Phase 4+: integration test of full graph (mock LLM)
- Phase 6+: API test via httpx

**Current:** 10 tests passing (`test_supervisor.py` × 8, `test_checkpointing.py` × 2)

## Console Log Formats

**Node transition (Phase 2+):**
[p2] <node> -> <next> | <reason> | <ms>ms

text

**LLM call:**
[llm] provider=<name> tokens_in=<N> tokens_out=<M> latency=<ms>ms model=<name>
[llm] FAILED: <ExceptionType>: <message>

text

**Checkpoint (CLI):**
[checkpoint] thread=<uuid>
[checkpoint] revision_count=N next=()

text

## Contracts Summary (5 invariants)

| # | Invariant | Owner |
|---|---|---|
| 1 | Writer clears `critique` after producing a draft | `writer.py` |
| 2 | Critic always writes non-empty `critique` | `critic.py` |
| 3 | Supervisor reads only presence/absence of `critique` | `supervisor.py` |
| 4 | `tools/llm.py` never reimplements failover | `tools/llm.py` |
| 5 | `research_findings` nodes return only new data | `researcher.py` |

## Error Handling Philosophy

- LLM failure → freelm failover chain; if all fail, job fails with clear error
- Search failure → retry once, then proceed with fewer findings (no crash)
- Citation missing → Critic flags, Writer revision required
- Never silently degrade: all failures logged with `job_id`

## Design Decisions

- **Supervisor pattern > peer-to-peer** — debuggable, extendable
- **Rule routing > LLM routing** — deterministic, cheap, testable
- **Hard revision cap = 3** — protects free LLM quotas
- **pgvector inside Postgres** — one database, one transaction
- **SSE > WebSockets** — simpler, one-way, proxy-friendly
- **Citations validated against state** — prevents hallucination
- **Wrap `FreeLLM`, don't reimplement failover** — freelm does it correctly
- **URLs generated in code, not LLM** — LLMs hallucinate URLs
- **Templates are pure string formatters** — testable in isolation