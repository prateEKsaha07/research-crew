# Project Overview

**Name:** ResearchCrew
**Tagline:** Four AI agents. One cited report.
**Repo root:** `research-crew/`
**Platform:** Windows, Python 3.12.2, PowerShell, venv
**Working directory for CLI:** `D:\research-crew\rc-core`
**Current phase:** 4 — Real Critic
**Latest tag:** `v0.4-jiro`

## Mission

Topic in → structured Markdown report out (≤30 seconds, ≥3 real clickable citations). Multi-agent LangGraph pipeline. 100% free / self-hostable stack. No paid APIs, no cloud vector DBs, no proprietary locked models.

## What It Does

A user submits a research topic. Four specialized agents collaborate through an iterative refinement loop:

- **Supervisor** — rule-based router (no LLM). Decides who works next based on state.
- **Researcher** — generates search queries, retrieves evidence, produces cited findings.
- **Writer** — drafts a 900–1400 word Markdown report with inline citations. Revises on critique.
- **Critic** — scores the draft across a rubric, requests revisions, or approves.

The Writer ↔ Critic loop runs until the Critic approves or a hard cap of 3 revisions is reached.

## PoC Acceptance Criteria

- API accepts a topic
- Returns Markdown with ≥3 real clickable citations in ≤30 seconds
- Full observability trace visible
- `docker compose up` works
- Similar second topic demonstrates memory recall
- Phases 0–7 merged and tagged `v1.0-poc`

## Repo Layout
research-crew/
├── .gitignore
├── README.md
├── context.md # multi-file split in this folder
├── docker-compose.yml # Phase 7
├── rc-core/ # backend
│ ├── cli.py # CLI entry
│ ├── requirements.txt
│ ├── .env.example
│ ├── agents/
│ ├── graph/
│ ├── prompts/
│ ├── tools/
│ ├── api/ # Phase 6
│ ├── tests/
│ └── Dockerfile # Phase 7
└── rc-web/ # frontend (Phase 6+)

text

## Naming Rules

- `rc-core` = backend, `rc-web` = frontend
- CLI entry is `rc-core/cli.py` (not `main.py` — reserved for `api/main.py` in Phase 6)
- All Python module paths are relative to `rc-core/`
- All console output is ASCII (`->` not `→`, `-` not `─`) for Windows PowerShell compatibility

## Related Docs

- Architecture → `01-architecture.md`
- Agents → `02-agents.md`
- Graph and State → `03-graph-and-state.md`
- Tools → `04-tools.md`
- Prompts → `05-prompts.md`
- Tech Stack → `06-tech-stack.md`
- Conventions → `07-conventions.md`
- Known Limitations → `08-known-limitations.md`
- Roadmap → `09-roadmap.md`