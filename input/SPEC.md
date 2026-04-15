# INPUT MODULE SPECIFICATION

## Purpose

The Input module syncs external data sources into SQLite so the LLM has fresh context.

**Active sources: Google Calendar (events) + Google People API (contacts).**
Tasks and goals are managed via the dashboard — they are not pulled from any external source.

> Notion connectors (tasks, goals, contacts) are archived in `input/connectors/_archived/`
> and `input/normalizers/_archived/`. They are not loaded or executed.

---

## Subsystem Layout

1. **Connectors (`input/connectors/`)**
   - `calendar_connector.py` — fetches today's events from Google Calendar API
   - `google_contacts_connector.py` — fetches contacts from Google People API (same OAuth token)

2. **Normalizers (`input/normalizers/`)**
   - `calendar_normalizer.py` — maps raw GCal event fields to SQLite `events` schema
   - `contact_normalizer.py` — maps Google People API fields to SQLite `contacts` schema

3. **Ingestion Service (`ingestion_service.py`)**
   - `IngestionService.ingest_all(user_id)` — calls `_ingest_events()` then `_ingest_contacts()`
   - Each entity written via `memory.ingest(entity_type, payload, user_id)`

---

## Data Flow

```
API startup / POST /api/sync
        ↓
IngestionService.ingest_all(user_id)
        ├─ CalendarConnector.fetch_events() → normalize_events() → memory.ingest("events", ...)
        └─ GoogleContactsConnector.fetch_contacts() → normalize_contacts() → memory.ingest("contacts", ...)
        ↓
memory.build_user_context() → LLM context includes today's events + contacts
```

---

## Sync Trigger

- **Automatic**: `api/main.py` runs `ingest_all` in a background thread every 15 minutes
- **Manual**: `POST /api/sync` (authenticated) triggers an immediate sync

---

## Google OAuth Note

Both connectors share `gcal_token.json`. The token must have been authorized with both scopes:
- `https://www.googleapis.com/auth/calendar`
- `https://www.googleapis.com/auth/contacts`

If the contacts scope is missing from the token, re-run the OAuth flow with both scopes.
