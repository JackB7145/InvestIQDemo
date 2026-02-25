# InvestIQ Demo — Claude Code Guidelines

## Project Overview

InvestIQ is a full-stack AI investment assistant with a multi-agent LangGraph backend and a streaming Next.js frontend.

```
InvestIQDemo/
├── chatBotMicroservice/   # Python · FastAPI · LangGraph · Ollama
└── investiqdemo/          # Next.js 16 · React 19 · TypeScript · MUI · Recharts
```

## Running the Project

Three terminal windows are required:

```bash
# Terminal 1 — Ollama LLM server (default port 11434)
ollama serve

# Terminal 2 — Python API (port 8000)
cd chatBotMicroservice
uvicorn main:app --reload --port 8000

# Terminal 3 — Next.js frontend (port 3000)
cd investiqdemo
npm run dev
```

## Architecture

```
Browser (Next.js :3000)
    │  POST /api/chat  (streaming)
    ▼
Next.js API Route (route.ts)
    │  POST http://localhost:8000/chat  (streaming proxy)
    ▼
FastAPI (:8000)
    │
    ▼
LangGraph Multi-Agent Graph
    project_manager
         │
    ┌────┴────┐
  thinker  researcher   ← parallel fan-out
    └────┬────┘
    display_agent
         │
    response_agent
         │
      validator ──fail──▶ project_manager (max 2 retries)
         │
        END
```

## Rules

Detailed rules are in [`.claude/rules/`](./.claude/rules/) — automatically loaded by Claude Code:

| File | Covers |
|------|--------|
| [`.claude/rules/python.md`](./.claude/rules/python.md) | FastAPI, LangGraph, Python conventions |
| [`.claude/rules/typescript.md`](./.claude/rules/typescript.md) | Next.js, React, TypeScript conventions |
| [`.claude/rules/ai-agents.md`](./.claude/rules/ai-agents.md) | Multi-agent design, state management, prompting |
| [`.claude/rules/git.md`](./.claude/rules/git.md) | Commit messages, branching, PRs |

## Non-Negotiables

- **Never** commit secrets, API keys, or `.env` files.
- **Never** disable CORS restrictions without explicit approval.
- **Never** add dependencies without updating `requirements.txt` or `package.json`.
- **Always** keep streaming end-to-end: do not buffer responses in the proxy layer.
- **Always** run `npm run lint` before committing frontend changes.
