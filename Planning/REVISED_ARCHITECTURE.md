# Nudge — Revised Architecture (MCP + Chat + Dashboard)

> Drafted: 2026-04-17
> Status: Proposal — awaiting decision on whether to adopt
> Supersedes original Phase 3-7 plans (now deleted from Planning/)

---

## Why This Revision

The user tested Google Gemini's Personal Intelligence and found the personalization compelling. But Gemini's consumer app is a closed box — no API for Personal Intelligence, no proactive nudges, no dashboard, no custom logic.

The insight: **Gemini's personalization is just "LLM + access to your Google data."** We can replicate that with any LLM + MCP servers that expose the same data as tools.

**LLM choice is pluggable.** Architecture doesn't lock to Gemini. Claude, GPT, open-source models (Llama/Mistral), or local inference all work through the same MCP interface. Start with whatever's cheapest/most available, swap later without rewriting tools or integrations.

What we gain:
- Chat interface (like Gemini app)
- Dashboard (progress view)
- Push notifications (proactive)
- Extensibility (plug in any MCP server)
- Data ownership (your SQLite, your vectors)

What we give up:
- Zero-setup magic of the consumer app
- Whatever Google adds to Gemini in the future

---

## The New Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Next.js PWA — already built)                 │
│  ┌──────────────┐  ┌──────────────────────────────────┐ │
│  │  Dashboard   │  │  Chat Interface (NEW)            │ │
│  │  (existing)  │  │  Natural language task planning, │ │
│  │              │  │  accountability, Q&A             │ │
│  └──────────────┘  └──────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │ REST + WebSocket (streaming)
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI — already built)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Existing    │  │  Chat Router │  │  MCP Bridge   │  │
│  │  Routes      │  │  (NEW)       │  │  (NEW)        │  │
│  │  tasks,      │  │  streaming,  │  │  spawns &     │  │
│  │  goals,      │  │  history,    │  │  multiplexes  │  │
│  │  nudges,     │  │  session     │  │  MCP servers  │  │
│  │  push, etc.  │  │              │  │               │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
│         ↓                 ↓                  ↓          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  SQLite (source of truth)  +  ChromaDB (memory)  │   │
│  │  existing tables + chat_messages, chat_sessions  │   │
│  └──────────────────────────────────────────────────┘   │
└────┬────────────────────────┬───────────────────────────┘
     ↓                        ↓
┌─────────────┐    ┌──────────────────────────────────────┐
│ LLM API (pluggable)  │    │  MCP Servers (tools the LLM calls)   │
│  (brain)    │◄──►│  ┌────────────────────────────────┐  │
│             │    │  │ Google Calendar MCP            │  │
│ function    │    │  │ Google Tasks MCP               │  │
│ calling →   │    │  │ Gmail MCP (Phase 3+)           │  │
│ MCP tools   │    │  │ Google Drive MCP (Phase 4+)    │  │
│             │    │  │ Memory MCP (custom — ChromaDB) │  │
│             │    │  │ Nudge MCP (custom — schedule)  │  │
│             │    │  │ Notification MCP (custom)      │  │
│             │    │  └────────────────────────────────┘  │
└─────────────┘    └──────────────────────────────────────┘
```

---

## What Stays From Phase 1

Everything. The revision is additive, not a rewrite.

| Component | Fate |
|---|---|
| FastAPI backend | **Keep** — add chat routes and MCP bridge |
| SQLite source of truth | **Keep** — add `chat_messages`, `chat_sessions` tables |
| ChromaDB vector store | **Keep** — expose via Memory MCP server |
| Per-user isolation | **Keep** — MCP servers respect user_id boundary |
| Orchestrator + scheduler | **Keep** — calls MCP tools for nudge delivery |
| Nudge engine (Remind/) | **Keep** — now informed by chat context |
| Web Push + Telegram | **Keep** — wrapped as Notification MCP |
| Dashboard UI | **Keep** — add chat tab alongside task/goal views |
| Google Calendar connector | **Replace** — use Google Calendar MCP server |
| Google Contacts connector | **Replace** — use Google People MCP server |

---

## What's Genuinely New

### 1. Chat Interface
- New tab on the dashboard
- Streaming responses via SSE or WebSocket
- Chat history persisted per user
- LLM has access to ALL MCP tools during chat

### 2. MCP Bridge
A new service layer that:
- Spawns and manages MCP server processes
- Routes LLM tool calls to the right MCP server
- Enforces authorization (user can't access another user's data)
- Handles MCP server discovery and registration

### 3. Custom MCP Servers
Three we build ourselves:
- **Memory MCP** — exposes ChromaDB semantic search and the `behavior_patterns` table
- **Nudge MCP** — LLM can schedule nudges ("Remind me at 4pm")
- **Notification MCP** — LLM can send messages via Web Push/Telegram

### 4. LLM Tool-Calling Loop (provider-agnostic)
Replaces the current one-shot `generate_insight()` with a conversational loop:
```
user message → LLM (via adapter) with MCP tool schemas
             → LLM decides: call MCP tool OR respond
             → If tool: execute via MCP bridge, feed result back
             → Repeat until LLM responds with text
             → Stream response to user
```

**LLM adapter layer** translates MCP tool schemas into each provider's function-calling format:
- Gemini: `tools=[FunctionDeclaration(...)]`
- Claude: `tools=[{"name":..., "input_schema":...}]`
- OpenAI: `tools=[{"type":"function", "function":{...}}]`
- Local (via Ollama/llama.cpp): prompt-based tool calling

Same MCP tool works across all. You pick the LLM by config, not code.

---

## Revised Phase Roadmap

### Phase 1 ✅ COMPLETE (Unchanged)
Reliable reminder tool. Dashboard, tasks, goals, push notifications, Telegram.

### Phase 2 — The System Learns (Unchanged, still next)
Behavior patterns, recurring tasks, effectiveness dashboard.
**Why unchanged:** This layer generates the personalization data that MCP servers expose later. Still foundational.

### Phase 3 — Chat + Core MCP Servers (NEW — was "contacts")
**Goal:** Add chat interface with Google integration via MCP.

Workstreams:
- **WS10 (revised)** — Chat UI on dashboard + chat API routes
- **WS11 (revised)** — MCP bridge service (spawn/route/auth)
- **WS12 (revised)** — Integrate Google Calendar MCP + Google Tasks MCP (replace current connectors)
- **WS13 (NEW)** — LLM adapter + tool-calling loop (provider-agnostic)

**Outcome:** You can chat with the system, and it can read/write your calendar and tasks.

### Phase 4 — Custom MCP Servers (NEW — was "recurring life")
**Goal:** Expose Nudge's internal capabilities as MCP servers for the LLM.

Workstreams:
- **WS14** — Memory MCP (ChromaDB semantic search, behavior patterns)
- **WS15** — Nudge MCP (LLM can schedule/cancel/modify nudges)
- **WS16** — Notification MCP (LLM can send push/Telegram)

**Outcome:** During chat, the LLM can query your history, schedule reminders, and send notifications — all by calling tools instead of you clicking buttons.

### Phase 5 — Extended Google Access (was "deep intelligence")
**Goal:** Give the LLM access to Gmail, Drive, Contacts via existing MCP servers.

Workstreams:
- **WS17** — Gmail MCP integration (read, search, draft)
- **WS18** — Google Drive MCP (read docs for context)
- **WS19** — Google People MCP (replaces current contacts sync)

**Outcome:** The LLM now has the same data access as Gemini's Personal Intelligence. Personalization parity.

### Phase 6 — Proactive Agent (was "the system acts")
**Goal:** LLM-driven proactive behavior (not just rule-based).

Workstreams:
- **WS20** — Scheduled LLM runs: morning brief, evening review, weekly planning
- **WS21** — Action authorization framework: LLM proposes, user approves, system executes
- **WS22** — Audit log for all automated actions

**Outcome:** The system acts on your behalf within boundaries you set.

### Phase 7 — Plugin Marketplace (was "extensibility")
**Goal:** Users and developers can add new MCP servers easily.

Workstreams:
- **WS23** — MCP server registry and config UI
- **WS24** — Data export/import (SQLite + ChromaDB)
- **WS25** — Plugin documentation and examples

---

## Key Technical Decisions

### D1. MCP server hosting
**Options:**
- (a) Spawn as subprocesses per request (simplest, high overhead)
- (b) Long-lived processes managed by the MCP bridge (better)
- (c) HTTP-based MCP servers (most scalable)

**Recommendation:** Start with (b) for built-in servers, use (c) for third-party.

### D2. Chat memory strategy
**Options:**
- (a) Full history in every prompt (expensive, hits token limits)
- (b) Sliding window (lose old context)
- (c) RAG over chat history via ChromaDB (best, uses existing infra)

**Recommendation:** (c) — embed every message, retrieve top-K relevant for each turn.

### D3. Tool calling model
**Options:**
- (a) Provider-native function calling (one implementation per LLM)
- (b) ReAct-style prompting (works with any LLM including local, but less reliable)
- (c) MCP standard + adapter layer that translates to each provider's format

**Recommendation:** (c) — MCP tools defined once, adapter translates for whichever LLM is configured. Keeps the door open for any provider (cloud or local).

### D4. Google Tasks as bridge layer
**Decision:** Make Google Tasks the synchronized layer between our SQLite and Google's ecosystem.
- User creates task in chat → LLM writes to both SQLite and Google Tasks via MCP
- User completes task in Google Tasks → syncs back to SQLite
- Benefit: native Android reminders fire even if our push system fails

---

## LLM Cost Budget

Moving from 1 call/day (Phase 1) to chat-driven usage is a cost shift.

| Usage | Estimated calls/day | Cost (cloud LLM at 2026 rates) |
|---|---|---|
| Scheduled jobs (unchanged) | 3 | negligible |
| Per-task nudges | 0 (rule-based) | 0 |
| Chat turns (active use) | 20-50 | ~$0.10-0.30/day |
| Background MCP tool calls | 10-30 | ~$0.05-0.15/day |

**Expected total:** $5-15/month with cloud LLMs. Could be $0 with local inference (Llama 3.x via Ollama).

**Mitigation options:**
- Use cheapest flash-tier model (Gemini Flash / Claude Haiku / GPT-4o-mini) for chat
- Reserve premium models (Gemini Pro / Claude Opus / GPT-4o) for weekly planning
- Run local model (Ollama + Llama 3.1 8B) for privacy-sensitive or high-volume use

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| MCP ecosystem immature, servers break | Medium | Pin specific versions, fork if needed |
| LLM function calling varies by provider | High | MCP adapter layer normalizes across providers |
| Chat usage blows through free tier | Medium | Per-user daily token caps, Flash by default |
| Scope creep into building all MCP servers | **Critical** | Use existing ones first. Build custom only after Phase 3 works end-to-end |
| Chat UX harder than expected | Medium | Start with simple turn-based, add streaming later |

---

## Migration Strategy

**Do NOT rewrite. Evolve.**

1. Finish Phase 2 first — behavior patterns have value regardless of chat
2. In Phase 3, add chat as a **new tab** on the dashboard — don't touch existing features
3. Replace Google Calendar connector with MCP server **only after** the MCP bridge is proven with one tool
4. Keep rule-based nudge engine — it's the reliability baseline. LLM-driven nudges are additive.

**Kill switches to preserve:**
- Every MCP tool must have a `--disabled` mode
- Mock mode must still work (no external APIs)
- Rule-based nudge engine runs independently of chat

---

## Invariants (True Across All Phases)

1. **Single user first.** Multi-user is an architecture property, not a product requirement.
2. **SQLite is the source of truth.** All external systems (including MCP servers) sync into it.
3. **LLM is called sparingly.** Free tier constraint. Cache aggressively.
4. **Mock mode must always work.** Every feature must be testable without API keys.
5. **The system must be useful without AI.** If LLM is down, tasks and reminders still work.
6. **Per-user data isolation.** Separate databases, separate vector stores. Enforced at MCP bridge layer.
7. **No silent failures.** Log everything. Fallback gracefully. Never crash the pipeline.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-10 | Archived Notion connectors | Notion CRUD was unreliable. SQLite is the source of truth. |
| 2026-04-12 | Dashboard is the control center | System must be self-contained. External dependencies reduce reliability. |
| 2026-04-14 | Phase 1 complete (5 workstreams) | Unified notifications, task-aware nudges, goal UI, SW actions, test suite. |
| 2026-04-17 | LLM-agnostic MCP architecture | Gemini's Personal Intelligence has no API. MCP + any LLM can replicate it. |
| 2026-04-17 | MCP spike validated (GREEN) | Filesystem MCP + Gemini tool calling worked end-to-end in 2 hours. See MCP_SPIKE_FINDINGS.md. |

---

## Decision Points

Before committing to this revision, decide:

1. **Is chat worth the cost increase?** $5-15/mo vs current ~$0/mo for LLM
2. **Are you OK replacing working Google connectors with MCP servers?** More complexity, less control
3. **Does Phase 2 still come first, or skip to Phase 3 (chat)?** Recommendation: Phase 2 first
4. **Build or buy MCP servers?** Start with community servers, build custom only when needed

---

## Next Concrete Steps If Adopted

1. Deploy Phase 1 to Railway (current priority — unchanged)
2. Use daily for 2 weeks to collect real data
3. Start Phase 2 (behavior patterns)
4. **Decision gate** — after Phase 2, re-evaluate this plan with real usage data
5. If greenlit, begin Phase 3 (chat + MCP bridge)

---

## Open Questions

- Which MCP servers are stable enough to use in production today?
- Which LLM providers have the best MCP support, and which need the adapter layer?
- How do we handle MCP server authentication (Google OAuth across multiple servers)?
- Should the chat session be per-day or persistent?

These need research before Phase 3 begins, not now.
