# Zerodha: AI Financial Intelligence Platform

An AI-powered financial intelligence and portfolio analytics platform for Indian equity markets.

## Architecture Overview

- **Frontend**: React, Vite, TypeScript, Tailwind CSS
- **Backend**: Python 3.11, FastAPI, Pydantic, SQLAlchemy 2.0
- **Database**: SQLite with Write-Ahead Logging (WAL) and async connection management
- **Testing**: pytest (backend), Vitest & Testing Library (frontend)
- **Cost Policy**: ₹0 additional spend (local processing, mocks, zero paid APIs)

## Planned Project Structure

```text
Zerodha-AI-Intelligence-New/
├── backend/          # FastAPI application, database layer, tests, MCP server
│   └── docs/         # Feature documentation (e.g., AI_REASONING_ENDPOINT.md)
├── frontend/         # React + Vite TypeScript web client
├── .gitignore        # Git ignore rules for Python, Node, DBs, and secrets
└── README.md         # Project documentation
```

## Documentation

- [AI Reasoning Endpoint & Architecture](backend/docs/AI_REASONING_ENDPOINT.md)

## Status

Phase 06: AI Reasoning Engine — Substep 6.4 (AI Reasoning Service & REST Endpoint) completed.

