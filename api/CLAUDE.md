# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **API layer** for the Nudge system (also called "Project Mirror") -- a FastAPI service that exposes the internal intelligence pipeline (Memory, LLM, Nudge Engine, Orchestrator) as REST endpoints. The API is a thin wrapper; all business logic lives in sibling modules at the parent directory level.

## Running the Server

```bash
# From the parent Nudge/ directory (not api/):
uvicorn api.main:app --reload
```

The server runs at `http://127.0.0.1:8000`. OpenAPI docs are at `/docs`.

## Running Tests

Tests are integration tests that require the server to be running:

```bash
# From the parent Nudge/ directory:
python test_api.py
```

There is no pytest setup; tests use `requests` against `http://127.0.0.1:8000/api`.

## Architecture

### Module dependency chain

```
API (this repo)
  -> dependencies.py patches sys.path to import sibling modules
  -> services/orchestrator_service.py is the sole bridge to core modules
  -> routes/ are thin HTTP wrappers that call orchestrator_service functions
```

### How sys.path bridging works

`dependencies.py` adds the parent directory and specific sibling module directories (`Memory`, `llm_module`, `Remind`, `Orchestrator`) to `sys.path`. Every file that needs core modules must import `api.dependencies` first (see `orchestrator_service.py` line 4).

### Core sibling modules (outside this directory)

- `Memory/` - user context building, action logging, ChromaDB vector store
- `llm_module/` - LLM inference (insight generation), supports `mode="mock"` and `mode="real"`
- `Remind/` - nudge engine (`nudge_engine`)
- `Orchestrator/` - pipeline orchestration (`run_job`)
- `input/` - ingestion service (Google Calendar sync only; Notion connectors archived in `input/connectors/_archived/`)

### Request flow

All routes funnel through `services/orchestrator_service.py` which calls core modules directly:
- `GET /api/context` -> `orchestrator_service.get_context()` -> Memory module
- `GET /api/insight` -> `orchestrator_service.get_insight()` -> Memory + LLM
- `GET /api/nudges` -> `orchestrator_service.get_nudges()` -> Memory + LLM + Nudge Engine
- `POST /api/log-action` -> `orchestrator_service.log_action()` -> Memory module
- `POST /api/run-cycle` -> `orchestrator_service.run_cycle()` -> Full Orchestrator pipeline
- `POST /api/tasks`, `PATCH /api/tasks/{id}`, `DELETE /api/tasks/{id}` -> task_service -> SQLite
- `POST /api/goals`, `PATCH /api/goals/{id}` -> task_service -> SQLite
- `GET /api/preferences`, `POST /api/preferences` -> Memory module
- `GET /api/push/vapid-public-key` -> returns VAPID public key for PWA subscription
- `POST /api/push/subscribe` -> saves browser push subscription to SQLite
- `POST /api/push/unsubscribe` -> removes push subscription
- `GET /api/evaluation/today` -> nudge effectiveness metrics
- `POST /api/sync` -> Google Calendar + Contacts sync

### Schemas

Pydantic models live in `schemas/base.py`. Currently defines `ActionRequest` and `CycleRequest`. All GET endpoints take `user_id` as a query parameter; `mode` defaults to `"mock"`.

### Configuration

Global config is in `../settings.yaml` (storage paths, Google Calendar config, logging). Secrets are in `../.env`. Notion DB IDs are commented out in settings.yaml — Notion is not active.
