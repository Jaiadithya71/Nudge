# Nudge — Railway Deployment Guide

> Get the system running 24/7 on Railway so you can use it from your phone anywhere.

---

## Important: What Must Happen Before Deploying

**WS-DEPLOY must be done first.** The frontend has 2 hardcoded `localhost` URLs that must be made configurable. Assign an agent with this brief:

> Make the API URL configurable in 3 files:
> 1. `Dashboard/lib/api.ts` line 5 — replace `"http://localhost:8000/api"` with `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"`
> 2. `Dashboard/public/sw.js` line 5 — read API_BASE from a URL query parameter: `const params = new URL(self.location.href).searchParams; const API_BASE = params.get("api") || "http://localhost:8000/api";`
> 3. `Dashboard/components/PushSetup.tsx` — when registering the service worker, pass the API URL as a query param: find the `navigator.serviceWorker.register("/sw.js")` call and change it to `navigator.serviceWorker.register(\`/sw.js?api=${encodeURIComponent(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api")}\`)`
> 4. Verify: `npm run dev` still works locally with no env var set (falls back to localhost). Test that push notification registration still works.

Once WS-DEPLOY is done, proceed below.

---

## Railway Architecture

Railway runs services from a GitHub repo. You'll deploy 2 services from the same repo:

```
Railway Project: "nudge"
├── Service 1: nudge-api     (Python, FastAPI)
│   └── Runs: uvicorn api.main:app --host 0.0.0.0 --port $PORT
│   └── Has: Volume mounted at /app/Memory/data (SQLite + ChromaDB persistence)
│
└── Service 2: nudge-web     (Node.js, Next.js)
    └── Runs: npm run build && npm run start
    └── Env: NEXT_PUBLIC_API_URL=https://nudge-api-production-xxxx.up.railway.app/api
```

---

## Step-by-Step Setup

### 1. Create a `requirements.txt` at the project root

Railway needs a single requirements file. Create `requirements.txt` in the Nudge root:

```
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
pydantic>=2.0.0
chromadb>=0.4.0
google-genai>=1.0.0
python-dotenv>=1.0.0
pywebpush>=2.0.0
requests>=2.28.0
python-jose[cryptography]>=3.3.0
pyyaml>=6.0.0
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
google-api-python-client>=2.0.0
```

### 2. Create a `Procfile` at the project root (for the API service)

```
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

### 3. Push to GitHub

If not already a git repo:

```bash
cd /path/to/Nudge
git init
git add -A
git commit -m "Initial commit for Railway deployment"
git remote add origin https://github.com/YOUR_USERNAME/nudge.git
git push -u origin main
```

**IMPORTANT:** Add these to `.gitignore` before pushing:

```
.env
gcal_token.json
gcal_credentials.json
Memory/data/
Dashboard/.next/
Dashboard/node_modules/
__pycache__/
*.pyc
```

### 4. Create Railway Account and Project

1. Go to https://railway.app — sign up with GitHub
2. Click "New Project"
3. Select "Deploy from GitHub Repo" → pick your nudge repo

### 5. Deploy the API Service (nudge-api)

Railway will auto-detect Python from `requirements.txt`. Configure it:

**Settings tab:**
- Service name: `nudge-api`
- Root directory: `/` (the project root)
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

**Variables tab — add all environment variables:**

```
GEMINI_API_KEY=<your key>
JWT_SECRET_KEY=<your key>
APP_USER_ID=jai
APP_PASSWORD=<your password>
FRONTEND_URL=<will be set after frontend deploys>
LLM_MODE=real
SYNC_INTERVAL_SECONDS=900
TELEGRAM_BOT_TOKEN=<your token>
TELEGRAM_CHAT_ID=<your chat id>
VAPID_PRIVATE_KEY=<your key>
VAPID_PUBLIC_KEY=<your key>
VAPID_EMAIL=mailto:jaiadithya2020@gmail.com
PORT=8000
```

**Volume (CRITICAL for SQLite persistence):**
- Go to the service → Settings → Volumes
- Click "New Volume"
- Mount path: `/app/Memory/data`
- Size: 1 GB (more than enough)

Without a volume, Railway's filesystem is ephemeral — your SQLite database would be wiped on every deploy.

**After deploy, note the public URL.** It will look like:
`https://nudge-api-production-xxxx.up.railway.app`

### 6. Fix the Storage Path

The `settings.yaml` says `base_dir: "data"` which resolves relative to `Memory/`. On Railway, the volume is mounted at `/app/Memory/data`, so this should work as-is. But verify by checking the deploy logs.

If SQLite can't find the DB, you may need to set an env var:
```
NUDGE_DATA_DIR=/app/Memory/data
```
And update `Memory/db.py` to read from it. Check this during first deploy.

### 7. Deploy the Frontend Service (nudge-web)

In the same Railway project, click "+ New Service" → "GitHub Repo" → same repo.

**Settings tab:**
- Service name: `nudge-web`
- Root directory: `/Dashboard`
- Build command: `npm install && npm run build`
- Start command: `npm run start -- -p $PORT`

**Variables tab:**

```
NEXT_PUBLIC_API_URL=https://nudge-api-production-xxxx.up.railway.app/api
PORT=3000
```

Replace the API URL with the actual URL from step 5.

**After deploy, note the public URL.** It will look like:
`https://nudge-web-production-xxxx.up.railway.app`

### 8. Update Backend CORS

Go back to the **nudge-api** service variables and set:

```
FRONTEND_URL=https://nudge-web-production-xxxx.up.railway.app
```

Redeploy the API service (Railway auto-redeploys on variable change).

### 9. Handle Google OAuth Token

This is the tricky part. Google OAuth tokens are stored in `gcal_token.json` — a file on disk. On Railway:

**Option A: Upload token manually (simplest)**

1. Railway has a shell feature: go to your nudge-api service → click "Shell"
2. Upload `gcal_token.json` and `gcal_credentials.json` to the app root:
   ```bash
   # From the Railway shell, paste the file contents
   cat > /app/gcal_token.json << 'EOF'
   <paste contents of your local gcal_token.json>
   EOF
   
   cat > /app/gcal_credentials.json << 'EOF'
   <paste contents of your local gcal_credentials.json>
   EOF
   ```

**Problem:** These files live on the ephemeral filesystem, not the volume. They'll be wiped on redeploy. To fix this permanently, either:
- Store them on the volume (`/app/Memory/data/`) and update `settings.yaml` token_file path
- Or store the token JSON as an environment variable and modify the connectors to read from env

**Option B: Store as env vars (more robust)**

Set these env vars on the API service:
```
GOOGLE_TOKEN_JSON=<entire contents of gcal_token.json as one line>
GOOGLE_CREDENTIALS_JSON=<entire contents of gcal_credentials.json as one line>
```

Then modify `input/connectors/calendar_connector.py` and `google_contacts_connector.py` to check for the env var first, write to a temp file, and use that. This is a small code change an agent can handle.

**Option C: Skip Google sync for now**

The system works without Google Calendar/Contacts — tasks and goals are dashboard-managed. You can deploy without the Google token and add it later. Sync will log warnings but nothing breaks.

---

## Railway Costs

Railway's pricing (as of 2026):

| Tier | Cost | What You Get |
|------|------|-------------|
| Trial | Free ($5 credit) | Enough for ~2 weeks of testing |
| Hobby | $5/month | 8 GB RAM, always-on, volumes |
| Pro | $20/month | More resources (you don't need this) |

**For Nudge:** The Hobby plan at $5/month is what you need. The API service uses ~200MB RAM (Python + ChromaDB). The frontend uses ~150MB. Both fit comfortably.

The free trial gives you enough time to test. If it works, upgrade to Hobby.

---

## Post-Deploy Verification

Once both services are running:

### From your laptop:
```bash
# Check API health
curl https://nudge-api-production-xxxx.up.railway.app/

# Run the test suite against the live server
# (temporarily update BASE in tests/test_full_system.py to the Railway URL)
python -X utf8 tests/test_full_system.py
```

### From your phone:
1. Open `https://nudge-web-production-xxxx.up.railway.app` in Chrome
2. Login with your credentials
3. Chrome should prompt "Add to Home Screen" → install the PWA
4. Click "Enable push notifications" → allow
5. Create a test task with nudge_time set to 2 minutes from now
6. Wait → push notification should arrive on your phone
7. Tap "Done" → check Railway API logs for `[action] Logged: acknowledged_nudge`

### Check scheduler is running:
In Railway dashboard → nudge-api → Logs, you should see:
```
Scheduler thread started
Sync thread started
Scheduler started for user=jai (mode=real)
```

---

## Custom Domain (Optional, Later)

If you want `nudge.yourdomain.com` instead of the Railway-generated URL:

1. Railway → Service → Settings → Domains → Custom Domain
2. Add your domain, Railway gives you a CNAME record
3. Add the CNAME in your DNS provider
4. Railway auto-provisions HTTPS via Let's Encrypt

---

## What Can Go Wrong

| Problem | Symptom | Fix |
|---------|---------|-----|
| SQLite lost on redeploy | Tasks disappear after deploy | Volume not mounted. Check Settings → Volumes. Mount at `/app/Memory/data` |
| CORS errors in browser | Dashboard shows network errors | `FRONTEND_URL` env var doesn't match the actual frontend URL. Update it. |
| Push notifications don't arrive | No notification on phone | Check VAPID keys are set. Check browser granted permission. Test with `POST /api/push/test`. |
| Google sync fails | Warnings in logs | Expected if tokens aren't uploaded. System works without it. |
| Scheduler doesn't fire | No morning/midday/evening nudges | Check logs for "Scheduler started". If missing, the startup lifespan hook may have failed. |
| Service sleeps/restarts | Nudges stop for hours | Railway Hobby plan keeps services alive. Free tier may sleep. Upgrade to Hobby ($5/month). |

---

## Deployment Checklist

```
[ ] WS-DEPLOY done (URLs configurable, not hardcoded)
[ ] requirements.txt created at project root
[ ] Procfile created at project root
[ ] .gitignore updated (no secrets, no data, no node_modules)
[ ] Code pushed to GitHub
[ ] Railway account created
[ ] nudge-api service deployed with all env vars
[ ] Volume mounted at /app/Memory/data
[ ] nudge-web service deployed with NEXT_PUBLIC_API_URL set
[ ] FRONTEND_URL updated on API service to match frontend URL
[ ] Google OAuth tokens handled (option A/B/C)
[ ] Tested: login from phone browser
[ ] Tested: create task from phone
[ ] Tested: push notification received on phone
[ ] Tested: notification action (Done/Later) logged
[ ] PWA installed on phone home screen
```
