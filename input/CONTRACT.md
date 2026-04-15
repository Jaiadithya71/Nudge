# INPUT MODULE CONTRACT

## Overview

The Input module is the gateway for syncing **read-only external data** into the user's SQLite store.
It does not manage tasks or goals — those are written exclusively by the dashboard via the API.

**Active integrations:** Google Calendar
**Archived (not active):** Notion tasks, goals, contacts — see `connectors/_archived/`, `normalizers/_archived/`

---

## Exposed Operations

### `IngestionService(memory_module)`

Configured at API startup. Holds a reference to the `memory` module.

### `IngestionService.ingest_all(user_id: str)`

Fetches Google Calendar events for today, normalizes them, and writes to SQLite via `memory.ingest("events", ...)`.

- Never raises — failures are logged as warnings, the system continues from cached SQLite state
- Safe to call repeatedly (events use `INSERT OR REPLACE`)

---

## Dependencies

- `memory.ingest(entity_type, payload, user_id)` — the only write path
- Google Calendar credentials at `gcal_token.json` (path from `settings.yaml`)

---

## Output Contract

All output is routed into SQLite via `memory.ingest()`. No return value. The caller reads fresh data via `memory.build_user_context()`.
