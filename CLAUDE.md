# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Nudge** (aka "Project Mirror") is a personal AI system that observes user behavior, builds context from Google Calendar and Google Contacts, generates insights via LLM, and delivers behavioral nudges via a **PWA (Android)** with Telegram as a fallback. It runs a time-driven loop: **Observe → Understand → Decide → Act → Learn**.

**Current phase:** Reliable reminder tool. Intelligence layer is in place but simplified. Primary focus is fast task creation, custom nudge messages per task, and trustworthy push delivery.

Tasks and goals are managed exclusively via the dashboard (SQLite). Notion integration was removed.

The system operates per-user with isolated memory, behavior modeling, and decision loops. It is NOT a chatbot or task manager — it's a continuous feedback system.

## Running the System

```bash
# Full dry-run cycle (mock LLM, demo user)
python main.py

# Real Gemini API mode
python main.py --real

# Custom user / skip data sync
python main.py --user alice --no-seed

# Start the FastAPI API server (from Nudge/ root)
uvicorn api.main:app --reload
# Docs at http://127.0.0.1:8000/docs
```

## Running Tests

```bash
# Module-level tests (each module has its own tests/ directory)
cd Memory && python -m pytest tests/
cd Orchestrator && python -m pytest tests/
cd llm_module && python -m pytest tests/

# Nudge engine tests (in Remind/)
python -m pytest Remind/test_nudge_engine.py

# Full API integration tests (requires running server)
python -m pytest tests/test_full_system.py
```

## Architecture

### Core Pipeline (per job cycle)

```
Dashboard (tasks/goals/preferences) → SQLite
Google Calendar → IngestionService → SQLite
Google Contacts → IngestionService → SQLite
SQLite → UserContext → LLM → Insight → Nudge Engine → Nudges
                                                           ├─► Web Push (Android PWA) [primary]
                                                           └─► Telegram [fallback]
```

### Module Layout

| Directory | Role | Key exports |
|-----------|------|-------------|
| `Memory/` | SQLite + ChromaDB storage, context building | `build_user_context()`, `log_action()`, `ingest()`, `semantic_search()` |
| `llm_module/llm_module/` | LLM inference (Gemini), mock mode support | `generate_insight(context, mode)` |
| `Remind/` | Rule-based nudge generation (max 2 per call) | `generate_nudges(insight, context, history, preferences)` |
| `Orchestrator/` | Scheduler + pipeline orchestration | `run_job()`, `run_scheduler()` |
| `input/` | Google Calendar sync only | `IngestionService.ingest_all(user_id)` |
| `Dashboard/` | Next.js control centre — tasks, goals, nudge config, preferences | All write ops go via FastAPI |
| `api/` | FastAPI REST layer (thin wrapper) | Routes under `/api` prefix |

### Module Import System

Modules are NOT installed as packages. Instead, `sys.path` is patched at runtime to make sibling directories importable:
- `main.py` adds `Memory/`, `llm_module/`, `Remind/`, `Orchestrator/` to `sys.path`
- `Orchestrator/orchestrator.py` does the same for its sibling dependencies
- `api/dependencies.py` does the same for the API layer

When adding new cross-module imports, follow this pattern.

### Job Types

The orchestrator runs three scheduled jobs and one on-demand type:
- **morning** (07:00) — full pipeline: context → insight → planning nudges
- **midday** (12:00) — inactivity detection → activation nudge (synthetic insight)
- **evening** (19:00) — context → insight → reflection nudges (lower strictness)
- **event** — on-demand trigger (overdue task, meeting done)

### Data Flow Between Modules

Memory returns Pydantic `UserContext` models. The orchestrator converts these via `_context_to_llm_dict()` (flat dict for LLM) and `_context_to_nudge_dict()` (JSON-serializable for nudge engine). For inventory of every module, table, and endpoint — see `Planning/SYSTEM_STATE.md`.

### Rate Limiting

Nudges are rate-limited by: daily max count, minimum time gap between nudges, and deduplication against recent nudge history (managed by `Orchestrator/state.py`).

## Configuration

- `settings.yaml` — storage paths, Google Calendar/Contacts config, logging (Notion block commented out)
- `.env` — API keys: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, JWT_SECRET_KEY, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_EMAIL
- Run `python scripts/generate_vapid_keys.py` once to generate VAPID keys for Web Push
- LLM mode controlled by `--real` / `--mock` flag (default: mock)

## Key Dependencies

- **pydantic** (v2+) for data models
- **chromadb** for vector memory
- **google-genai** for Gemini LLM calls
- **FastAPI + uvicorn** for the API layer
- **python-dotenv** for env loading
