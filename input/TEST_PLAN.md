# INPUT MODULE TEST PLAN

The only active connector is Google Calendar. Tests cover the calendar sync path only.

---

## 1. Calendar Sync — Happy Path

- **Trigger:** `POST /api/sync` with a valid JWT while Google Calendar token is present
- **Expected:** Response contains `{"status": "ok", "synced": {"events": N}}` where N ≥ 0
- **Check:** `GET /api/context` — `events` array contains today's meetings

---

## 2. Missing Google Calendar Token

- **Trigger:** Remove or rename `gcal_token.json`, then call `POST /api/sync`
- **Expected:** Sync completes without crashing (warning logged, 0 events ingested)
- **Check:** API returns 200 with `{"events": 0}`, not a 500

---

## 3. Repeated Sync (Idempotency)

- **Trigger:** Call `POST /api/sync` twice in a row
- **Expected:** No duplicate events in the DB — `INSERT OR REPLACE` deduplicates by event ID
- **Check:** `GET /api/context` — event count is stable, not doubled

---

## 4. Background Sync Loop

- **Trigger:** Start the API server (`uvicorn api.main:app --reload`)
- **Expected:** Logs show `Auto-sync starting for user=...` and `Auto-sync complete for user=...` within 30 seconds of startup
- **Check:** Server logs only — no assertion needed

---

## Note on Notion

Notion connectors are archived and not tested. If re-enabling, restore files from
`input/connectors/_archived/` and `input/normalizers/_archived/` and update `ingestion_service.py`.
