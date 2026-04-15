# Nudge — Deployment Guide

> How to get the system running on your phone, accessible from anywhere.

---

## The Problem

Right now everything runs on `localhost`. Your phone can only reach it when on the same WiFi. For the system to be useful as a daily tool, the backend must be accessible from the internet so:
- Push notifications fire even when you're not home
- The dashboard loads on your phone anywhere
- The scheduler runs 24/7 (not just when your laptop is open)

---

## Option Comparison

| Option | Cost | Always-on? | Setup Time | HTTPS? | Best For |
|--------|------|-----------|-----------|--------|----------|
| **Cloudflare Tunnel** | Free | Only when laptop is running | 15 min | Yes (auto) | Quick testing |
| **Oracle Cloud Free Tier** | Free forever | Yes | 1-2 hours | Yes (manual) | Long-term free hosting |
| **Hetzner/DigitalOcean VPS** | ~$4/month | Yes | 30 min | Yes (Let's Encrypt) | Simplest reliable hosting |
| **Raspberry Pi at home** | ~$50 one-time | Yes (if always plugged in) | 1-2 hours | Needs tunnel for external access | If you want full local control |

---

## Recommended Path: Start Testing Now, Deploy Later

### Stage 1: Cloudflare Tunnel (test from phone immediately)

This gives you a real HTTPS URL accessible from anywhere, tunneled to your laptop. Free. No server needed. URL is stable (unlike ngrok).

**Prerequisites:**
- Cloudflare account (free)
- `cloudflared` installed

**Setup:**

```bash
# 1. Install cloudflared
# Windows: download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
# Or: winget install Cloudflare.cloudflared

# 2. Login once
cloudflared tunnel login

# 3. Create a named tunnel (stable URL)
cloudflared tunnel create nudge

# 4. Start tunnels for both backend and frontend
# Terminal 1 — Backend tunnel
cloudflared tunnel --url http://localhost:8000 --name nudge-api

# Terminal 2 — Frontend tunnel  
cloudflared tunnel --url http://localhost:3000 --name nudge-web
```

This gives you URLs like:
- `https://nudge-api-xxxx.trycloudflare.com` (backend)
- `https://nudge-web-xxxx.trycloudflare.com` (frontend)

**Then update 3 places:**

1. `.env` — set `FRONTEND_URL=https://nudge-web-xxxx.trycloudflare.com`
2. `Dashboard/lib/api.ts` line 5 — set `BASE_URL` to the backend tunnel URL
3. `Dashboard/public/sw.js` line 5 — set `API_BASE` to the backend tunnel URL

Restart both servers. Open the frontend URL on your phone. Install as PWA. Done.

**Limitation:** Only works while your laptop is running. Close the laptop → backend dies → no notifications.

---

### Stage 2: Always-on Server (when you're ready to rely on it daily)

When you've confirmed the system is useful (after 1-2 weeks of testing via tunnel), move to a server.

**Cheapest always-on option: Oracle Cloud Free Tier**

- 1 GB RAM, 1 CPU — enough for SQLite + FastAPI + Next.js
- Free forever (not trial — actually free)
- Based in your region

**What you'd deploy:**

```
Server (Ubuntu 22.04):
  /opt/nudge/                    ← entire repo
  systemd services:
    nudge-api.service            ← uvicorn api.main:app --host 0.0.0.0 --port 8000
    nudge-web.service            ← cd Dashboard && npm run start -- -p 3000
  caddy (reverse proxy):
    nudge.yourdomain.com → :3000  (frontend)
    api.nudge.yourdomain.com → :8000  (backend)
    Auto-HTTPS via Let's Encrypt
```

**What needs to change in code for deployment:**

| File | Current | Change To |
|------|---------|-----------|
| `Dashboard/lib/api.ts:5` | `http://localhost:8000/api` | Read from `NEXT_PUBLIC_API_URL` env var |
| `Dashboard/public/sw.js:5` | `http://localhost:8000/api` | Needs to be set at build time or passed via query param on SW registration |
| `.env` `FRONTEND_URL` | `http://localhost:3000` | `https://nudge.yourdomain.com` |
| `api/main.py` CORS | Reads from `FRONTEND_URL` | Already correct — just update `.env` |

**The ideal code change (do this before any deployment):**

Make the API URL configurable instead of hardcoded:

`Dashboard/lib/api.ts`:
```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
```

`Dashboard/public/sw.js`:
```javascript
// Read from query param passed during registration
const params = new URL(self.location.href).searchParams;
const API_BASE = params.get("api") || "http://localhost:8000/api";
```

`Dashboard/components/PushSetup.tsx` (where SW is registered):
```typescript
const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
navigator.serviceWorker.register(`/sw.js?api=${encodeURIComponent(apiUrl)}`);
```

This is a small pre-deployment workstream — 3 files, no logic changes.

---

## What Stage Can You Start Testing?

**Right now. Today.** Here's the order:

### Immediate (no deployment needed):
1. Start using the system on your laptop browser
2. Create real tasks, set real nudge times, use it for a few days
3. This generates the `user_actions` data that Phase 2 needs
4. Run `tests/test_full_system.py` to confirm everything works

### This week (Cloudflare Tunnel):
1. Install `cloudflared`
2. Update the 3 hardcoded URLs
3. Open on your phone, install as PWA
4. Use it for real — get push notifications anywhere
5. **This is the stage where you find out if the system is actually useful**

### After 1-2 weeks of real use:
1. You'll have enough `user_actions` data for Phase 2's pattern detection
2. You'll know which features matter and which are noise
3. If it's useful → move to always-on server
4. If it's not → the tunnel saved you from deploying something prematurely

---

## What Needs to Work for Phone Testing

| Feature | Works on tunnel? | Notes |
|---------|-----------------|-------|
| Dashboard (tasks, goals) | Yes | Full CRUD |
| Push notifications | Yes | HTTPS required — tunnel provides it |
| Notification actions (Done/Later) | Yes | sw.js hits the backend tunnel URL |
| Telegram notifications | Yes | Telegram connects to your bot regardless of where the backend is |
| Google Calendar sync | Yes | Backend calls Google API directly |
| Scheduler (morning/midday/evening) | Yes, while laptop is on | Dies when laptop sleeps |
| Per-task scheduled nudges | Yes, while laptop is on | Same limitation |

**The only thing a tunnel can't do:** Run while your laptop is off. The scheduler and push notification delivery require the backend to be running. This is why you eventually need an always-on server — but NOT for initial testing.

---

## Pre-Deployment Workstream (WS-DEPLOY)

**Before any deployment, make the API URL configurable. This is a 3-file change:**

| File | Change |
|------|--------|
| `Dashboard/lib/api.ts` | Replace hardcoded URL with `process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000/api"` |
| `Dashboard/public/sw.js` | Read API URL from query param instead of hardcoded constant |
| `Dashboard/components/PushSetup.tsx` | Pass API URL as query param when registering service worker |

**Acceptance criteria:**
1. `npm run dev` with no env var → still works on localhost (default)
2. `NEXT_PUBLIC_API_URL=https://api.example.com npm run dev` → frontend hits remote backend
3. Push notification actions (Done/Later) hit the correct backend URL
4. No hardcoded `localhost` remains in source files (except as fallback defaults)

**This workstream can be done by an agent right now — it's independent of Phase 2.**
