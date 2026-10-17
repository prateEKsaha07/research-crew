# ResearchCrew — Complete Flow Diagram

This file shows exactly what happens between typing a topic and getting
a report. It covers the CLI, the graph, every agent, every tool call,
the memory layer, the tracing layer, and every exit point.

Diagrams use Mermaid, which renders natively on GitHub, GitLab, VS Code
(with the Markdown Preview Mermaid extension), and Obsidian.

---

## 1. High-level architecture

```mermaid
graph TB
    User["User types topic<br/>python cli.py 'quantum computing'"]

    subgraph CLI["rc-core/cli.py"]
        GetLLM["get_llm()<br/>build provider chain"]
        BuildGraph["build_graph(llm)<br/>compile StateGraph"]
        InitTracing["init_tracing()<br/>feenion.configure"]
        SetSession["feenion.set_session(tid)"]
        Invoke["graph.invoke(state)"]
        Store["store(topic, draft, findings)<br/>best-effort"]
    end

    subgraph Graph["LangGraph StateGraph"]
        Start([START])
        Researcher[Researcher]
        Writer[Writer]
        Critic[Critic]
        End([END])
        Decide{{decide(state)}}
    end

    subgraph Tools["rc-core/tools/"]
        LLM["llm.py<br/>FreeLLM failover"]
        Search["search.py<br/>ddgs"]
        Memory["memory.py<br/>pgvector"]
        Tracing["tracing.py<br/>feenion"]
    end

    subgraph External["External services"]
        Postgres[(Postgres + pgvector<br/>localhost:5432)]
        Feenion["feenion server<br/>localhost:8000<br/>or JSONL"]
        Web["DuckDuckGo"]
        Providers["Gemini / Mistral<br/>OpenRouter / NVIDIA NIM"]
    end

    User --> GetLLM
    GetLLM --> BuildGraph
    BuildGraph --> InitTracing
    InitTracing --> SetSession
    SetSession --> Invoke
    Invoke --> Start

    Start -.-> Decide
    Researcher -.-> Decide
    Writer -.-> Decide
    Critic -.-> Decide

    Decide -->|"no findings"| Researcher
    Decide -->|"no draft"| Writer
    Decide -->|"no critique"| Critic
    Decide -->|"rejected, rev<3"| Writer
    Decide -->|"approved or capped"| End

    Researcher --> LLM
    Researcher --> Search
    Researcher --> Memory
    Writer --> LLM
    Critic --> LLM

    LLM --> Providers
    Search --> Web
    Memory --> Postgres
    Invoke --> Tracing
    Tracing --> Feenion

    End --> Store
    Store --> Memory

    style Start fill:#4caf50,color:#fff
    style End fill:#4caf50,color:#fff
    style Decide fill:#ff9800,color:#fff
    style Postgres fill:#2196f3,color:#fff
    style Feenion fill:#2196f3,color:#fff
```

---

## 2. Startup sequence

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant CLI as cli.py
    participant LLM as tools/llm.py
    participant Builder as graph/builder.py
    participant Tracing as tools/tracing.py
    participant Feenion as feenion
    participant Graph as StateGraph

    User->>CLI: python cli.py "quantum computing"
    CLI->>CLI: parse argv, topic = "quantum computing"

    CLI->>LLM: get_llm()
    LLM->>LLM: load_dotenv()
    LLM->>LLM: read *_API_KEY vars
    alt no keys set
        LLM-->>CLI: raise ValueError
        CLI-->>User: exit 1
    else at least one key
        LLM->>LLM: build FreeLLM(providers)
        LLM-->>CLI: LLMClient
    end

    CLI->>Builder: build_graph(llm)
    Builder->>Builder: add_node researcher/writer/critic
    Builder->>Builder: add_conditional_edges
    Builder->>Builder: compile(MemorySaver)
    Builder-->>CLI: compiled graph

    CLI->>Tracing: init_tracing()
    alt FEENION_SERVER_URL set
        Tracing->>Feenion: configure(server_url=...)
    else unset
        Tracing->>Feenion: configure(JSONLExporter)
    end
    Tracing-->>CLI: True

    CLI->>Feenion: set_session(tid)
    Note over Feenion: trace_id = checkpoint thread_id

    CLI->>Graph: invoke(initial_state, config)
    Note over Graph: pipeline runs (see next section)
    Graph-->>CLI: final_state

    CLI-->>User: print report + confidence_scores
```

---

## 3. The routing function

`decide(state)` runs before every node and after every node. No LLM.
Fifteen lines. Pure function.

```mermaid
flowchart TD
    A["decide(state)"] --> B{"not research_findings?"}
    B -->|yes| R1["return 'researcher'"]
    B -->|no| C{"not draft?"}
    C -->|yes| R2["return 'writer'"]
    C -->|no| D{"not critique?"}
    D -->|yes| R3["return 'critic'"]
    D -->|no| E{"not is_approved<br/>AND revision_count < 3?"}
    E -->|yes| R4["return 'writer'"]
    E -->|no| R5["return 'end'"]

    style R1 fill:#4caf50,color:#fff
    style R2 fill:#4caf50,color:#fff
    style R3 fill:#4caf50,color:#fff
    style R4 fill:#ff9800,color:#fff
    style R5 fill:#4caf50,color:#fff
    style A fill:#2196f3,color:#fff
```

**Rule:** structural checks precede content checks. "Has the Critic
run?" (empty critique) is checked before "was the Critic happy?"
(`is_approved`).

---

## 4. Full success path — first-pass approval

```mermaid
sequenceDiagram
    autonumber
    participant SR as Supervisor/Router
    participant RE as Researcher
    participant W as Writer
    participant C as Critic
    participant T as tools
    participant M as Memory
    participant F as feenion

    Note over SR: t=0.0s<br/>state: all empty

    SR->>SR: decide() -> "researcher"
    SR->>RE: invoke researcher(state, llm)
    activate RE

    RE->>T: span("memory.find_similar")
    T->>M: find_similar(topic)
    M->>M: embed topic (fastembed)
    M->>M: SELECT ... <=> 0.35 LIMIT 3
    M-->>T: [{text, url, distance}]
    T->>F: export span
    T-->>RE: recalled findings

    RE->>RE: seen_urls = {r.url for r in recalled}

    RE->>T: llm.chat(query_gen)
    T->>F: span("llm.chat")
    T-->>RE: "query one\nquery two\n..."
    RE->>RE: _parse_queries -> up to 5

    loop for each query
        RE->>T: span("search")
        T->>T: DDGS().text(q, 3)
        T->>F: export span
        T-->>RE: [{title, url, snippet}]
        RE->>RE: pick first url not in seen_urls
        RE->>T: llm.chat(summarize)
        T-->>RE: one sentence
        RE->>RE: append {text, url}
    end

    RE->>RE: out = recalled + new_findings
    RE-->>SR: {"research_findings": out}
    deactivate RE

    Note over SR: t~17.6s<br/>[p2] researcher -> writer | N findings

    SR->>SR: decide() -> "writer"
    SR->>W: invoke writer(state, llm)
    activate W
    W->>T: llm.chat(draft_prompt)
    T->>F: span("llm.chat")
    T-->>W: full Markdown draft
    W-->>SR: {"draft": md, "critique": ""}
    deactivate W

    Note over SR: t~23s<br/>[p2] writer -> critic

    SR->>SR: decide() -> "critic"
    SR->>C: invoke critic(state, llm)
    activate C
    C->>T: llm.chat(critic_score)
    T-->>C: raw JSON
    C->>C: _parse + _validate
    C->>C: avg = mean(scores)
    alt avg >= 8
        C->>C: critique="approved", approved=True
    else avg < 8 and rev+1 >= 3
        C->>C: forced approve
    else reject
        C->>C: critique=llm critique, approved=False
    end
    C-->>SR: {confidence_scores, critique, is_approved, revision_count}
    deactivate C

    Note over SR: t~24s<br/>[p2] critic -> end | avg=10.0 approved=True

    SR->>SR: decide() -> "end"
```

---

## 5. Rejection loop — Critic rejects once

```mermaid
sequenceDiagram
    autonumber
    participant SR as Supervisor/Router
    participant W as Writer
    participant C as Critic

    Note over SR: state: draft exists, critique="", rev=0

    SR->>C: decide() -> "critic"
    C->>C: llm.chat -> parse -> avg=6.5
    C->>C: rev+1=1 < 3, avg < 8 -> reject
    C-->>SR: critique="Add citations", approved=False, rev=1

    Note over SR: [p2] critic -> writer

    SR->>SR: decide() -> critique!="" AND not approved AND rev<3 -> "writer"
    SR->>W: invoke (revise mode)
    W->>W: writer_revise(draft, critique)
    W->>W: llm.chat
    W-->>SR: {"draft": revised, "critique": ""}
    Note over SR: critique cleared

    SR->>C: decide() -> "critic"
    C->>C: llm.chat -> parse -> avg=9.0
    C-->>SR: critique="approved", approved=True, rev=2

    Note over SR: [p2] critic -> end

    SR->>SR: decide() -> "end"
```

**Worst case:** every Critic pass rejects. `revision_count` goes
`0 -> 1 -> 2 -> 3`. At `rev=3`, `new_count >= MAX_REVISIONS` forces
approve. Total: 1 researcher + 3 writer + 3 critic.

```mermaid
flowchart LR
    R0["rev=0"] -->|Critic rejects| R1["rev=1"]
    R1 -->|Writer revises, Critic rejects| R2["rev=2"]
    R2 -->|Writer revises, Critic rejects| R3["rev=3<br/>FORCED APPROVE"]
    R3 --> End([END])

    style R3 fill:#ff9800,color:#fff
    style End fill:#4caf50,color:#fff
```

---

## 6. Memory layer call graph

```mermaid
graph TB
    subgraph CLI["cli.py"]
        Main["main()"]
        StoreCall["store(topic, draft, findings)"]
    end

    subgraph Res["agents/researcher.py"]
        REntry["researcher(state, llm)"]
        Recall["find_similar(topic)"]
    end

    subgraph Mem["tools/memory.py"]
        FS["find_similar()"]
        Ensure["ensure_schema()"]
        Embed["_embed(texts)"]
        Connect["_connect()"]
        StoreFn["store()"]
    end

    subgraph Ext["External"]
        Fastembed["fastembed<br/>BAAI/bge-small-en-v1.5"]
        PG[("Postgres<br/>reports, findings")]
    end

    Main --> REntry
    REntry --> Recall
    Recall --> FS
    FS --> Ensure
    FS --> Embed
    FS --> Connect
    FS -->|"SELECT ... <=> 0.35"| PG
    Embed --> Fastembed

    Main --> StoreCall
    StoreCall --> StoreFn
    StoreFn --> Ensure
    StoreFn --> Embed
    StoreFn --> Connect
    StoreFn -->|"INSERT reports"| PG
    StoreFn -->|"INSERT findings<br/>ON CONFLICT (url) DO NOTHING"| PG

    style PG fill:#2196f3,color:#fff
    style Fastembed fill:#2196f3,color:#fff
```

**Why best-effort:** every arrow into `memory.py` from `researcher.py`
or `cli.py` is wrapped in `try/except MemoryUnavailableError`. A dead
DB logs a warning and the run continues. The report is the product.

---

## 7. Tracing layer call graph

```mermaid
graph TB
    subgraph Pipeline["Pipeline operations"]
        L1["logged()<br/>node span"]
        L2["llm.chat()<br/>LLM span"]
        L3["search()<br/>search span"]
        L4["find_similar() / store()<br/>memory span"]
    end

    subgraph Tracer["tools/tracing.py"]
        Init["init_tracing()"]
        Span["span(name, **attrs)"]
    end

    subgraph Feenion["feenion 0.1.2"]
        Configure["feenion.configure()"]
        Ctx["feenion.span()<br/>context manager"]
        JSONL["JSONLExporter"]
        HTTP["HTTPExporter"]
    end

    subgraph Backends["Trace outputs"]
        File[("telemetry/traces.jsonl")]
        Server["feenion server<br/>http://localhost:8000"]
        UI["React dashboard<br/>http://localhost:8000"]
    end

    Init --> Configure
    Configure -->|"if no SERVER_URL"| JSONL
    Configure -->|"if SERVER_URL set"| HTTP

    L1 --> Span
    L2 --> Span
    L3 --> Span
    L4 --> Span

    Span -->|"_ENABLED=False"| Noop["yield None<br/>(no-op)"]
    Span -->|"_ENABLED=True"| Ctx
    Ctx --> JSONL
    Ctx --> HTTP

    JSONL --> File
    HTTP --> Server
    Server --> UI

    style File fill:#4caf50,color:#fff
    style Server fill:#4caf50,color:#fff
    style UI fill:#4caf50,color:#fff
```

**Span names in a typical run** (feenion 0.1.2 does not nest, so all
are top-level):

```
researcher              (node span)
  memory.find_similar   (recall)
  llm.chat              (query gen)
  search                (x1 per query)
  llm.chat              (summary, x1 per finding)
  ...
writer                  (node span)
  llm.chat              (draft)
critic                  (node span)
  llm.chat              (score)
memory.store            (after approval)
```

All spans share the same `session_id`, which equals the checkpoint
`thread_id`. That is the only grouping available.

---

## 8. Every exit point

```mermaid
flowchart TD
    Start["graph.invoke()"] --> Q1{"LLMUnavailableError?"}
    Q1 -->|yes| E1["exit 1<br/>stderr: 'error: LLM unavailable'"]
    Q1 -->|no| Q2{"SearchUnavailableError<br/>or ResearchError?"}
    Q2 -->|yes| E2["exit 1<br/>stderr: 'error: research failed'"]
    Q2 -->|no| Q3{"CriticError?"}
    Q3 -->|yes| E3["exit 2<br/>stderr: '[critic] FAILED'"]
    Q3 -->|no| Q4{"final.is_approved?"}
    Q4 -->|yes| Q5{"store raises<br/>MemoryUnavailableError?"}
    Q4 -->|no| E4["print report<br/>exit 0"]
    Q5 -->|yes| E5["log '[memory] FAILED'<br/>print report<br/>exit 0"]
    Q5 -->|no| E6["print report<br/>exit 0"]

    style E1 fill:#f44336,color:#fff
    style E2 fill:#f44336,color:#fff
    style E3 fill:#f44336,color:#fff
    style E4 fill:#4caf50,color:#fff
    style E5 fill:#ff9800,color:#fff
    style E6 fill:#4caf50,color:#fff
```

**Aborts (exit 1 or 2):** the run cannot produce a report.
**Degrades (exit 0):** the run produces a report; a side service is
down but the product is unaffected.

---

## 9. Failure modes and their handling

```mermaid
graph LR
    subgraph Aborts["Aborts (no report)"]
        A1["All LLM providers fail"]
        A2["Researcher: 0 queries"]
        A3["Researcher: 0 findings"]
        A4["Critic: 2x malformed JSON"]
    end

    subgraph Degrades["Degrades (report still ships)"]
        D1["DB down during recall"]
        D2["DB down during store"]
        D3["Tracing disabled"]
        D4["One search returns 0"]
        D5["One search call fails"]
    end

    A1 --> Exit1["exit 1"]
    A2 --> Exit1
    A3 --> Exit1
    A4 --> Exit2["exit 2"]
    D1 --> Log1["log warning<br/>continue"]
    D2 --> Log2["log stderr<br/>exit 0"]
    D3 --> Noop["no-op spans<br/>continue"]
    D4 --> Skip["next query"]
    D5 --> Skip

    style Aborts fill:#ffebee
    style Degrades fill:#e8f5e9
    style Exit1 fill:#f44336,color:#fff
    style Exit2 fill:#f44336,color:#fff
    style Log1 fill:#4caf50,color:#fff
    style Log2 fill:#4caf50,color:#fff
    style Noop fill:#4caf50,color:#fff
    style Skip fill:#4caf50,color:#fff
```

---

## 10. Data model

```mermaid
classDiagram
    class Finding {
        +str text
        +str url
    }

    class ConfidenceScores {
        +float coverage
        +float evidence
        +float structure
        +float clarity
        +float avg
    }

    class ResearchState {
        +str topic
        +list~Finding~ research_findings
        +str draft
        +str critique
        +ConfidenceScores confidence_scores
        +int revision_count
        +bool is_approved
        +str current_step
    }

    ResearchState --> Finding : research_findings
    ResearchState --> ConfidenceScores : confidence_scores
```

**The reducer.** `research_findings` is
`Annotated[list[Finding], add]`. When a node returns this key, LangGraph
runs `add(existing, returned)` — appends, does not overwrite. This is
why the Researcher returns only new findings (invariant 5). Returning
the full list would cause exponential duplication across revisions.

**The typed scorecard.** `ConfidenceScores` is `total=False` because
the initial state in `cli.py` passes `{}`. The Critic fills it.
`builder.py:_reason()` reads `avg` directly for the `[p2] critic` log
line.

---

## 11. Timing budget

A run targets under 30 seconds. Real measurements:

```mermaid
gantt
    title ResearchCrew run timing (typical, first-pass approval)
    dateFormat X
    axisFormat %S s

    section Startup
    get_llm + build_graph + init_tracing :0, 1

    section Researcher
    Recall from pgvector                 :1, 2
    Query generation (LLM)               :2, 3
    Search query 1                       :3, 6
    Summarize 1 (LLM)                    :6, 7
    Search query 2                       :7, 11
    Summarize 2 (LLM)                    :11, 12
    Search query 3                       :12, 15
    Summarize 3 (LLM)                    :15, 16
    Search query 4                       :16, 18
    Summarize 4 (LLM)                    :18, 19

    section Writer
    Draft generation (LLM)               :19, 24

    section Critic
    Score (LLM)                          :24, 26

    section Post-run
    Store to pgvector                    :26, 27
```

**Dominant cost:** search. `ddgs` returns in 2-5s per query, and the
Researcher runs up to 5 queries. `RESEARCH_BUDGET_S = 18` caps this. If
a search takes 6s, the Researcher stops at the next query boundary.

**Second cost:** the Writer's 3500-token output (4-6s on free tier).

**Cheapest:** the Critic (1-2s) because `max_tokens=800`.

---

## 12. Sequence of state changes

```mermaid
stateDiagram-v2
    [*] --> Empty
    Empty: research_findings=[]\ndraft=""\ncritique=""
    Empty --> HasFindings: researcher runs
    HasFindings: research_findings=[...]\ndraft=""\ncritique=""
    HasFindings --> HasDraft: writer runs
    HasDraft: research_findings=[...]\ndraft="..."\ncritique=""
    HasDraft --> Rejected: critic rejects\n(rev<3)
    HasDraft --> Approved: critic approves
    Rejected: research_findings=[...]\ndraft="..."\ncritique="..."\nrev=1
    Rejected --> HasDraft: writer revises
    Approved: research_findings=[...]\ndraft="..."\ncritique="approved"\nrev=N
    Approved --> [*]

    note right of Rejected
        Writer clears critique
        when revising, so state
        returns to HasDraft
    end note

    note right of Approved
        Store to pgvector here
    end note
```

The three invariants that make this state machine safe:

1. **Writer clears `critique`** after drafting. Without this, the state
   would stay in `Rejected` forever.
2. **Critic always writes non-empty `critique`.** Empty means "Critic
   has not run yet." Writing `""` on approval would loop back to Critic.
3. **Supervisor reads only presence/absence of `critique`.** It never
   parses the text. Deterministic.

Breaking any of these produces an infinite loop. Each is tested
explicitly in `tests/test_supervisor.py`.

---

## 13. What the user sees

```mermaid
flowchart LR
    A["python cli.py<br/>'quantum computing'"] --> B["Console output"]
    B --> C["[tracing] enabled<br/>exporter=JSONL or server_url"]
    B --> D["[memory] recalled=N<br/>distance_min=X.XX"]
    B --> E["[search] query=... results=N"]
    B --> F["[p2] researcher -> writer"]
    B --> G["[p2] writer -> critic"]
    B --> H["[critic] coverage=... avg=... approved=..."]
    B --> I["[p2] critic -> end"]
    B --> J["[checkpoint] thread=<tid>"]
    B --> K["Markdown report"]
    B --> L["confidence_scores:"]
    B --> M["[memory] stored findings=N"]

    C -.-> N["Trace file<br/>telemetry/traces.jsonl<br/>or http://localhost:8000"]
    K -.-> O["Saved to pgvector<br/>reports + findings tables"]

    style K fill:#4caf50,color:#fff
    style L fill:#4caf50,color:#fff
    style N fill:#2196f3,color:#fff
    style O fill:#2196f3,color:#fff
```

---

## 14. The whole system in one paragraph

`cli.py` builds an LLM client and a compiled graph, initializes tracing,
and invokes the graph with a blank `ResearchState`. `decide()` routes
the state to the Researcher, which recalls prior findings from pgvector,
generates search queries, runs live web searches, summarizes each
snippet with the LLM, and appends `{text, url}` findings to state. The
router sends the state to the Writer, which drafts a Markdown report
citing only those URLs. The router sends the state to the Critic, which
scores the draft on four dimensions, approves or rejects, and increments
the revision counter. If rejected and under the cap, the router sends
the state back to the Writer for a revision. When approved or capped,
the router sends to END. `cli.py` then prints the report and
`confidence_scores`, and persists the report and its findings to pgvector
so a later similar topic recalls them. Every step emits a span, either
to `telemetry/traces.jsonl` or to a self-hosted feenion server. Memory
and tracing failures are logged and ignored; LLM, research, and critic
failures abort with a non-zero exit code.