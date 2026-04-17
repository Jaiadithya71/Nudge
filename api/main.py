import os
import time
import threading
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

# sys.path must be patched before any core module imports
import api.dependencies  # noqa: F401

from api.routes import auth, context, insight, nudges, actions, system, sync, telegram, evaluation, tasks, goals, preferences, push, search

load_dotenv()

logger = logging.getLogger(__name__)

_SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "900"))  # default 15 min


def _start_scheduler():
    """Start the orchestrator scheduler in a background daemon thread."""
    user_id = os.environ.get("APP_USER_ID", "jai")
    mode = os.environ.get("LLM_MODE", "mock")
    try:
        import orchestrator as orch
        logger.info("Starting scheduler for user=%s mode=%s", user_id, mode)
        orch.run_scheduler(user_id, mode=mode, poll_interval_seconds=60)
    except Exception as exc:
        logger.error("Scheduler crashed: %s", exc)


def _start_telegram_polling():
    """
    Start Telegram long-polling in a daemon thread.
    Enabled when TELEGRAM_USE_POLLING=true (default for local dev — no ngrok needed).
    Skipped automatically if TELEGRAM_BOT_TOKEN is not set.
    """
    user_id = os.environ.get("APP_USER_ID", "jai")
    try:
        import notification_service as ns
        ns.start_polling(user_id)
    except Exception as exc:
        logger.error("Telegram polling crashed: %s", exc)


def _start_sync_loop():
    """
    Periodic background sync — runs ingest_all every SYNC_INTERVAL_SECONDS.
    Keeps Google Calendar events fresh. Tasks and goals are dashboard-managed (SQLite only).
    Runs immediately on startup, then on the configured interval.
    """
    user_id = os.environ.get("APP_USER_ID", "jai")
    try:
        import memory as mem
        from input.ingestion_service import IngestionService
        svc = IngestionService(mem)
    except Exception as exc:
        logger.error("Sync loop failed to initialise: %s", exc)
        return

    # Wait 10s after startup before first sync so the server is fully ready
    time.sleep(10)
    while True:
        try:
            logger.info("Auto-sync starting for user=%s", user_id)
            svc.ingest_all(user_id)
            logger.info("Auto-sync complete for user=%s", user_id)
        except Exception as exc:
            logger.warning("Auto-sync error (will retry in %ds): %s", _SYNC_INTERVAL_SECONDS, exc)
        time.sleep(_SYNC_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sync thread — runs ingest_all immediately then every 15 min
    ts = threading.Thread(target=_start_sync_loop, name="nudge-sync", daemon=True)
    ts.start()
    logger.info("Sync thread started (interval=%ds)", _SYNC_INTERVAL_SECONDS)

    # Scheduler thread — fires morning/midday/evening jobs at their scheduled times
    t = threading.Thread(target=_start_scheduler, name="nudge-scheduler", daemon=True)
    t.start()
    logger.info("Scheduler thread started (tid=%s)", t.ident)

    # Telegram polling thread — enabled by default when TELEGRAM_BOT_TOKEN is set
    # Set TELEGRAM_USE_POLLING=false to disable (e.g. when using webhook mode)
    use_polling = os.environ.get("TELEGRAM_USE_POLLING", "true").lower() not in ("false", "0", "no")
    has_token   = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    if use_polling and has_token:
        tp = threading.Thread(target=_start_telegram_polling, name="nudge-telegram", daemon=True)
        tp.start()
        logger.info("Telegram polling thread started")
    elif has_token:
        logger.info("Telegram polling disabled — using webhook mode")
    else:
        logger.info("Telegram not configured — set TELEGRAM_BOT_TOKEN to enable")

    yield
    # Shutdown: daemon threads exit automatically when main process exits


app = FastAPI(
    title="Nudge AI System API",
    description="Intelligence Engine bridging Memory, LLM inference, and behaviour Nudging.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — locked to the configured frontend origin
_frontend = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes
app.include_router(auth.router,    prefix="/api")

# Protected routes (all require Bearer JWT)
app.include_router(context.router, prefix="/api", tags=["Context"])
app.include_router(insight.router, prefix="/api", tags=["Insight"])
app.include_router(nudges.router,  prefix="/api", tags=["Nudges"])
app.include_router(actions.router, prefix="/api", tags=["Actions"])
app.include_router(system.router,     prefix="/api", tags=["System"])
app.include_router(sync.router,       prefix="/api", tags=["Sync"])
app.include_router(telegram.router,   prefix="/api", tags=["Telegram"])
app.include_router(evaluation.router, prefix="/api", tags=["Evaluation"])
app.include_router(tasks.router,       prefix="/api", tags=["Tasks"])
app.include_router(goals.router,       prefix="/api", tags=["Goals"])
app.include_router(preferences.router, prefix="/api", tags=["Preferences"])
app.include_router(push.router,        prefix="/api", tags=["Push"])
app.include_router(search.router,      prefix="/api", tags=["Search"])


@app.get("/")
def health_check():
    return {"status": "online", "message": "Nudge API is running."}


# Normalize SW action types to match what the evaluation endpoint counts
_SW_ACTION_TYPE_MAP = {
    "acknowledged_nudge": "acknowledged",
    "snoozed_nudge":      "snoozed",
}


@app.post("/api/sw-action")
async def sw_action(request: Request):
    """
    Log a nudge action from the service worker (no JWT required).
    The nudge_id serves as proof of legitimacy — only the notification recipient has it.
    """
    body = await request.json()
    action = body.get("action", "")
    metadata = body.get("metadata", {})

    if not action or not metadata.get("nudge_id"):
        raise HTTPException(status_code=400, detail="action and metadata.nudge_id required")

    user_id = os.environ.get("APP_USER_ID", "jai")
    import memory as mem

    # Store the normalised type so the evaluation endpoint can count it correctly
    stored_action = _SW_ACTION_TYPE_MAP.get(action, action)
    mem.log_action(user_id, {
        "action_type": stored_action,
        "entity_type": "nudge",
        "entity_id":   metadata.get("nudge_id", ""),
        "metadata":    metadata,
    })

    logger.info(
        "[action] Logged: %s, nudge_id=%s, source=%s",
        action, metadata.get("nudge_id"), metadata.get("source"),
    )
    return {"status": "logged"}
