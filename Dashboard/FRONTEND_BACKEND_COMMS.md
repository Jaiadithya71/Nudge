# Frontend ↔ Backend Communication Summary

## Overview

The frontend is a **Next.js 16 App Router** application (React 19, TypeScript, TailwindCSS) that communicates with a **FastAPI** backend running at `http://localhost:8000/api`.

All HTTP communication is handled by **Axios** via a centralized API layer in `lib/api.ts`. The main dashboard (`app/page.tsx`) is a Client Component that fetches all data on mount and polls every 10 seconds.

---

## Base URL

```
http://localhost:8000/api
```

All requests include a `user_id` query param (currently hardcoded to `"jai"`).

---

## API Functions — `lib/api.ts`

### `getContext(userId: string)`

- **Method:** `GET`
- **Endpoint:** `/context?user_id={userId}`
- **Returns:** `Context`
- **Used by:** `Dashboard` → passes `context.tasks` to `TaskList`, `context.calendar_events` to `CalendarView`

Expected response shape:
```json
{
  "tasks": {
    "pending": [{ "title": "...", "status": "..." }],
    "overdue":  [{ "title": "...", "status": "..." }]
  },
  "calendar_events": [
    { "title": "...", "start_time": "...", "end_time": "..." }
  ]
}
```

---

### `getInsight(userId: string)`

- **Method:** `GET`
- **Endpoint:** `/insight?user_id={userId}`
- **Returns:** `Insight`
- **Used by:** `Dashboard` → passes to `InsightCard`

Expected response shape:
```json
{
  "summary": "...",
  "key_observations": ["...", "..."]
}
```

---

### `getNudges(userId: string)`

- **Method:** `GET`
- **Endpoint:** `/nudges?user_id={userId}`
- **Returns:** `Nudge[]`
- **Used by:** `Dashboard` → maps over array, renders one `NudgeCard` per nudge

Expected response shape:
```json
[
  {
    "type": "...",
    "message": "...",
    "priority": "..."
  }
]
```

---

### `logAction(payload)`

- **Method:** `POST`
- **Endpoint:** `/log-action`
- **Body:** JSON
- **Used by:** `Dashboard.handleAction` — called when the user clicks "Acknowledge" on a nudge
- **Returns:** nothing (fire-and-forget)

Request body shape:
```json
{
  "user_id": "jai",
  "action": "acknowledged_nudge",
  "metadata": {
    "message": "<nudge message text>"
  }
}
```

---

## Data Flow

```
Dashboard mounts
    │
    ├─ getContext("jai")  →  GET /api/context?user_id=jai
    ├─ getInsight("jai")  →  GET /api/insight?user_id=jai
    └─ getNudges("jai")   →  GET /api/nudges?user_id=jai
            │
            ▼
    State updated → components re-render

Every 10 seconds:
    └─ fetchData() repeats all three GET requests

User clicks "Acknowledge" on a NudgeCard:
    └─ logAction(...)  →  POST /api/log-action
```

---

## TypeScript Types — `types/index.ts`

| Type | Fields |
|------|--------|
| `Task` | `title: string`, `status: string` |
| `Event` | `title: string`, `start_time: string`, `end_time: string` |
| `Context` | `tasks: { pending: Task[], overdue: Task[] }`, `calendar_events: Event[]` |
| `Insight` | `summary: string`, `key_observations: string[]` |
| `Nudge` | `type: string`, `message: string`, `priority: string` |

These types are shared across all components and the API layer. The backend responses must conform to these shapes exactly for the UI to render correctly.

---

## Component → Data Mapping

| Component | Data Source | API Endpoint |
|-----------|-------------|--------------|
| `InsightCard` | `insight` state | `GET /insight` |
| `TaskList` | `context.tasks` | `GET /context` |
| `CalendarView` | `context.calendar_events` | `GET /context` |
| `NudgeCard` | item from `nudges` array | `GET /nudges` |
| *(acknowledge button)* | — | `POST /log-action` |

---

## Polling Behaviour

- On mount: all three GET requests fire in sequence (`getContext` → `getInsight` → `getNudges`)
- A `setInterval` re-runs the same fetch sequence every **10,000ms (10s)**
- The interval is cleared on component unmount via the `useEffect` cleanup return

---

## Notes for Backend

- All GET requests send `user_id` as a **query parameter**, not in the body or headers
- The `POST /log-action` body is `application/json`
- `InsightCard` currently only renders `summary` — `key_observations` is fetched but not yet displayed in the UI
- `TaskList` currently only renders **pending** tasks — overdue tasks are in the type but not rendered yet
- There is no authentication or token handling — all requests are unauthenticated
