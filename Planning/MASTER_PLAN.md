# Nudge — Master Execution Plan

> Last updated: 2026-04-14
> Current phase: Phase 1 COMPLETE. Phase 2 is next.

---

## Document Map

Read these in order:

| Document | What It Covers |
|----------|---------------|
| **[SYSTEM_STATE.md](SYSTEM_STATE.md)** | Complete inventory of what exists: every module, table, endpoint, component — what works, what's empty, what's unused |
| **[VISION_TO_PRODUCT.md](VISION_TO_PRODUCT.md)** | How the original vision maps to 7 concrete phases, with invariants and a decision log |
| **[PHASE2_PLAN.md](PHASE2_PLAN.md)** | Next up: behavior learning, recurring tasks, effectiveness dashboard (WS6-WS9) |
| **[PHASE3_PLAN.md](PHASE3_PLAN.md)** | Contact relationships, decay detection, meeting prep, social nudges (WS10-WS12) |
| **[PHASE4_PLAN.md](PHASE4_PLAN.md)** | Life domains, anticipatory nudges, calendar-aware scheduling (WS13-WS15) |
| **[PHASE5_PLAN.md](PHASE5_PLAN.md)** | Deep intelligence: enriched LLM context, RAG, insight continuity, personality model (WS16-WS20) |
| **[PHASE6_PLAN.md](PHASE6_PLAN.md)** | The system acts: action authorization, auto-scheduling, audit log |
| **[PHASE7_PLAN.md](PHASE7_PLAN.md)** | Extensibility: plugin architecture, data export/import |
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | Hosting options comparison, pre-deployment code changes (WS-DEPLOY) |
| **[DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md)** | Step-by-step Railway deployment: 2 services, volumes, env vars, verification checklist |
| **[Initial_Vision.md](Initial_Vision.md)** | Original vision document — the north star |
| **[workstreams/](workstreams/)** | Phase 1 agent briefs (WS1-WS5) — completed, kept for reference |

---

## Phase Status

| Phase | Name | Status | Workstreams |
|-------|------|--------|-------------|
| 1 | Reliable Reminder Tool | **COMPLETE** ✅ | WS1-WS5 |
| 2 | The System Learns | **NEXT** | WS6-WS9 |
| 3 | The System Knows Your People | Planned | WS10-WS12 |
| 4 | Recurring Life Management | Planned | WS13-WS15 |
| 5 | Deep Intelligence | Planned | WS16-WS20 |
| 6 | The System Acts | Designed | Future |
| 7 | Extensibility & Data Ownership | Designed | Future |

---

## Phase 1: Reliable Reminder Tool ✅ COMPLETE

| # | Workstream | What It Did |
|---|-----------|-------------|
| WS1 | [Unified Notification Delivery](workstreams/WS1_NOTIFICATIONS.md) | Wired Web Push into delivery pipeline alongside Telegram |
| WS2 | [Task-Aware Nudge Messages](workstreams/WS2_SMART_NUDGES.md) | Nudges now reference actual task names, counts, and due dates |
| WS3 | [Goal Management Dashboard](workstreams/WS3_GOALS_UI.md) | Full goal CRUD on dashboard, task-to-goal linking, DELETE cascades |
| WS4 | [Service Worker Actions](workstreams/WS4_SW_ACTIONS.md) | Push notification "Done"/"Later" buttons log actions to backend |
| WS5 | [End-to-End System Verification](workstreams/WS5_VERIFICATION.md) | 27-test API suite + manual checklist |

---

## Phase 2: The System Learns (NEXT)

**Full plan: [PHASE2_PLAN.md](PHASE2_PLAN.md)**

| # | Workstream | Purpose | Depends On |
|---|-----------|---------|------------|
| WS6 | Action Analysis Engine | Analyze user_actions + nudge_log → write behavior_patterns | None |
| WS7 | Pattern-Informed Nudges | Nudge engine adapts based on detected patterns | WS6 |
| WS8 | Recurring Tasks | Tasks auto-recreate on a schedule | None |
| WS9 | Effectiveness Dashboard | Show the user their stats and patterns | None (benefits from WS6) |

**Recommended execution order:**
1. WS8 (Recurring Tasks) — most user-visible, simplest
2. WS6 (Action Analysis) — enables everything else
3. WS9 (Stats Dashboard) — can show data even before patterns exist
4. WS7 (Pattern-Informed Nudges) — the payoff

---

## Rules For All Agents (All Phases)

- Do NOT create new files unless explicitly instructed. Prefer editing existing files.
- Do NOT add comments, docstrings, or type annotations to code you didn't change.
- Do NOT refactor surrounding code or "improve" things outside scope.
- Do NOT change the `sys.path` patching pattern — it's intentional.
- Do NOT install new packages unless the workstream explicitly lists them.
- Follow the existing code style: no trailing summaries, minimal logging additions.
- Test every change manually using the commands in CLAUDE.md before marking done.
- Read the module's CONTRACT.md and SPEC.md before making changes.
- Read SYSTEM_STATE.md to understand what exists and what's empty.
