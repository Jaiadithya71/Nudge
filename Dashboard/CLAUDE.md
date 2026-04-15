# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Commands

```bash
npm run dev      # Start dev server (localhost:3000)
npm run build    # Production build
npm run start    # Start production server
npm run lint     # Run ESLint
```

There are no automated tests — manual verification is done against a running backend (`uvicorn api.main:app --reload` in the parent `Nudge/` directory).

## Architecture

This is the frontend for **Nudge** — a personal reminder and behavioral nudge system. The dashboard is the primary control centre: all task/goal management happens here. It is also a **Progressive Web App (PWA)** installable on Android, with Web Push notifications as the primary delivery channel.

**All pages are Client Components** (`"use client"`). There is no SSR — data is fetched client-side on mount and refreshed by polling.

### PWA Setup

The dashboard ships as an installable Android PWA:
- `public/manifest.json` — app manifest (name, icons, display mode)
- `public/sw.js` — service worker that handles push events and shows notifications
- `app/layout.tsx` — links the manifest and registers theme-color

To receive push notifications, the user clicks "Enable push notifications" in the header. This registers the service worker, subscribes to Web Push using the VAPID public key from the backend, and saves the subscription via `POST /api/push/subscribe`.

Icons required (not yet generated — add to `public/`):
- `icon-192.png` — 192×192 px
- `icon-512.png` — 512×512 px

### Data Flow

```
Dashboard mounts → checks localStorage for JWT token → redirects to /login if absent
    │
    ├─ GET /api/context   (tasks + calendar)   — polls every 30s
    ├─ GET /api/insight   (AI summary)         — polls every 60s
    └─ GET /api/nudges    (behavioral nudges)  — polls every 10s

Task added → POST /api/tasks → task row auto-expands for nudge config
User saves nudge config → PATCH /api/tasks/{id}
Push notification arrives → service worker shows Android notification
```

### Key Modules

| Path | Purpose |
|------|---------|
| `lib/api.ts` | All Axios calls; injects `Authorization: Bearer <token>`; includes push subscription API |
| `lib/auth.ts` | `getToken()`, `setToken()`, `clearToken()` — JWT stored in `localStorage` |
| `types/index.ts` | Shared types: `Task`, `Event`, `Context`, `Insight`, `Nudge`, `NudgeAction` |
| `app/page.tsx` | Main dashboard — owns all state, polling, nudge actions, new-task auto-expand |
| `app/login/page.tsx` | Calls `POST /api/auth/login`, stores token, redirects to `/` |
| `components/TaskList.tsx` | Task CRUD UI; `newTaskId` prop auto-expands nudge config on new task |
| `components/PushSetup.tsx` | Handles service worker registration + push permission + subscription save |
| `components/SettingsPanel.tsx` | Global nudge preferences (times, max count, gap, strictness) |

### Styling

Tailwind CSS v4 — uses `@tailwindcss/postcss` plugin (not the classic `tailwindcss` PostCSS plugin). Theme variables are declared in `app/globals.css` with `@theme inline`.

### API Contract

Backend response shapes are documented in `FRONTEND_BACKEND_COMMS.md`. The `types/index.ts` types must match these exactly. When the backend adds or changes fields, update `types/index.ts` first, then the consuming component.
