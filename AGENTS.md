# Sisyphus — Self-Evolving AI Agent

Sisyphus is a self-evolving AI agent that gets smarter over time.
It starts with persistent memory and grows toward skill generation,
cross-session learning, and autonomous improvement.

**Origin**: Evolved from opencode's Sisyphus orchestrator, inspired by
OpenClaw (multi-channel gateway + plugin architecture) and Hermes Agent
(self-improving learning loop + memory system).

## Project Structure

```
sisyphus/
├── AGENTS.md              ← This file: project guide for AI agents
├── pyproject.toml
├── src/sisyphus/
│   ├── memory/            ← Persistent memory system (current focus)
│   │   ├── store.py       ← File-based memory store (INDEX.md + topics)
│   │   ├── recall.py      ← Retrieval (LLM-powered, then semantic)
│   │   ├── extraction.py  ← Background extraction agent
│   │   └── cli.py         ← CLI interface
│   └── skill/             ← Skill auto-generation (future)
├── tests/
│   ├── conftest.py
│   └── test_store.py
└── docs/
    ├── ADR-001-memory-architecture.md
    ├── research-openclaw.md
    └── research-hermes.md
```

## Development Principles

1. **TDD**: Red → Green → Refactor. Tests first, always.
2. **Small steps**: One capability per iteration.
3. **Simple over smart**: Files over databases, LLM over vector stores.
4. **Public repo**: Code in GitHub, data in `.omo/` (gitignored).

## Memory Architecture (v0.1)

```
~/.omo/memory/
├── INDEX.md              ← Always loaded: table of contents
├── project-context.md    ← Topic file (on-demand)
├── decisions.md          ← Topic file (on-demand)
└── lessons.md            ← Topic file (on-demand)
```

Inspired by Claude Code's file-based memory + Hermes Agent's frozen snapshot.
See `docs/ADR-001-memory-architecture.md` for full rationale.

## Evolution Roadmap

- v0.1 — File store + INDEX + CRUD ← **now**
- v0.2 — LLM-powered recall (semantic, not keyword)
- v0.3 — Background extraction agent
- v0.4 — Frozen snapshot → system prompt injection
- v0.5 — Lightweight semantic search
- v0.6 — Skill auto-generation from patterns
