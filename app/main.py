"""
main.py -- Nudge System Entry Point
====================================
Runs a full end-to-end dry-run cycle for a demo user in MOCK mode:

    1. Seeds the user's memory with sample goals, tasks, actions, and patterns
    2. Runs the MORNING job  → context + LLM insight + planning nudges
    3. Runs the MIDDAY job   → inactivity check + activation nudge
    4. Runs the EVENING job  → reflection nudges

Usage:
    python main.py              # full dry-run (mock mode)
    python main.py --real       # real Gemini API (requires GEMINI_API_KEY in .env)
    python main.py --user alice # specify a custom user ID

Folder layout expected at runtime (siblings of this file, under app/):
    Memory/         memory.py, db.py, vector_db.py, models.py, schema.sql
    llm_module/     llm_module/__init__.py, ...
    Remind/         nudge_engine.py
    Orchestrator/   orchestrator.py, state.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import io

# ---------------------------------------------------------------------------
# Path bootstrap — make all sibling module folders importable
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent

# Force UTF-8 stdout on Windows so special chars don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_MODULE_PATHS = [
    str(_ROOT / "Memory"),
    str(_ROOT / "llm_module"),
    str(_ROOT / "Remind"),
    str(_ROOT / "Orchestrator"),
]
for _p in _MODULE_PATHS:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Imports (after path setup)
# ---------------------------------------------------------------------------
import memory as mem
import orchestrator as orch

# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

_DIVIDER = "=" * 60
_BOLD    = ""
_RESET   = ""
_GREEN   = ""
_YELLOW  = ""
_CYAN    = ""
_RED     = ""
_GRAY    = ""


def _header(title: str) -> None:
    print(f"\n{_DIVIDER}")
    print(f"  {title}")
    print(f"{_DIVIDER}")


def _section(label: str) -> None:
    print(f"\n>> {label}")


def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def _warn(msg: str) -> None:
    print(f"  [!!]  {msg}")


def _nudge_block(nudges: list[dict], job: str) -> None:
    if not nudges:
        _warn(f"No nudges generated for {job} job.")
        return
    for i, n in enumerate(nudges, 1):
        print(f"\n  Nudge #{i}")
        print(f"  {'Type':<12}: {n.get('type', '-')}")
        print(f"  {'Priority':<12}: {n.get('priority', '-').upper()}")
        print(f"  {'Timing':<12}: {n.get('timing', '-')}")
        print(f"  {'Message':<12}: \"{n.get('message', '-')}\"")


# ---------------------------------------------------------------------------
# Seed data is now handled dynamically by the IngestionService inside the
# orchestrator via input connectors.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Run the full cycle
# ---------------------------------------------------------------------------

def run_cycle(user_id: str, mode: str) -> None:
    preferences = {
        "max_nudges_per_day": 6,   # bumped up so all 3 jobs can fire
        "strictness": 0.7,
        "allowed_time_windows": [],
        "min_gap_hours": 0,        # no gap enforcement during dry-run
    }

    jobs = [
        ("morning", "MORNING JOB  -- Context -> Insight -> Planning Nudges"),
        ("midday",  "MIDDAY JOB   -- Inactivity Check -> Activation Nudge"),
        ("evening", "EVENING JOB  -- Context -> Insight -> Reflection Nudges"),
    ]

    for job_type, label in jobs:
        _header(label)
        try:
            nudges = orch.run_job(
                user_id=user_id,
                job_type=job_type,
                mode=mode,
                preferences=preferences,
            )
            _nudge_block(nudges, job_type)
        except Exception as exc:
            _warn(f"Job '{job_type}' raised an exception: {exc}")
            import traceback
            traceback.print_exc()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Nudge System — end-to-end dry-run")
    parser.add_argument("--real",  action="store_true", help="Use real Gemini API (requires GEMINI_API_KEY)")
    parser.add_argument("--user",  default="jai",  help="User ID to run the cycle for (default: jai)")
    parser.add_argument("--no-seed", action="store_true", help="Skip memory seeding (use existing data)")
    args = parser.parse_args()

    mode    = "real" if args.real else "mock"
    user_id = args.user

    _header("NUDGE SYSTEM -- FULL CYCLE DRY-RUN")
    print(f"  User    : {user_id}")
    print(f"  Mode    : {mode.upper()}")
    print(f"  Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not args.no_seed:
        _header("EXTERNAL DATA SYNC")
        # Initialize context directly so the orchestrator runs the new IngestionService
        pass
    else:
        _warn("Skipping external sync (--no-seed flag set)")

    _section("Verifying memory context...")
    try:
        ctx = mem.build_user_context(user_id)
        ctx_data = ctx.model_dump() if hasattr(ctx, "model_dump") else ctx
        _ok(f"Goals             : {len(ctx_data.get('goals', []))}")
        _ok(f"Tasks             : {len(ctx_data.get('tasks', []))}")
        _ok(f"Events            : {len(ctx_data.get('events', []))}")
        _ok(f"Recent actions    : {len(ctx_data.get('recent_actions', []))}")
        _ok(f"Behavior patterns : {len(ctx_data.get('behavior_patterns', []))}")
    except Exception as exc:
        _warn(f"build_user_context failed: {exc}")
        import traceback; traceback.print_exc()
        sys.exit(1)

    run_cycle(user_id, mode)

    _header("DRY-RUN COMPLETE")
    print(f"  All jobs executed for user '{user_id}'.")
    print(f"  Run with --real to use the live Gemini API.\n")


if __name__ == "__main__":
    main()
