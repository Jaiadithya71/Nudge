# Nudge 🎯 (Project Mirror)

**Nudge** is a personal AI system designed to observe user behavior, synthesize context from Google Calendar and Google Contacts, generate insights via a Large Language Model, and deliver behavioral feedback. 

Development of the monolithic system was intentionally paused in Phase 1.5. This repository remains preserved as an **architecture blueprint, design case-study, and Model Context Protocol (MCP) implementation reference** exploring localized personal context loops.

---

## 💡 The "Why": The Core Vision

The core objective of Nudge was to experiment with building a **digital replica of a physical persona**—a persistent background agent that understands the user's daily chores, connections, schedules, and long-term goals. The philosophical end goal was to explore personal continuity: keeping a digital duplicate alive that can manage routines, represent the user, and act as a form of virtual life extension.

### The Engineering Challenges
Building a personal duplicate requires solving major architectural problems:
1. **The Context Length Dilemma:** AI coding agents consume massive amounts of tokens when trying to debug distributed codebases. To address this, Nudge was divided into decoupled, isolated layers (Memory, Input, Orchestrator, LLM Module) coordinated via strict schemas.
2. **Brittle Sync Integrations:** Early iterations relied on bi-directional Notion database sync. In practice, building custom granular sync layers over external SaaS APIs proved highly brittle, unreliable for real-time CRUD operations, and difficult to test.
3. **The Data Silo Trap:** Building custom background sync daemons to pull calendar and contact data locally is a redundant effort now that hyperscalers (such as Google via its native Personal Intelligence Workspace extensions) provide native, platform-level RAG directly over users' personal apps.

---

## 🏗️ The "What": System Architecture

Nudge implements a time-driven loop that decouples data ingestion, decision mapping, and proactive action:

$$\text{Observe} \longrightarrow \text{Understand} \longrightarrow \text{Decide} \longrightarrow \text{Act}$$

```
Dashboard (Next.js Control Panel) ◄──[FastAPI REST API]──► SQLite & ChromaDB
                                                              │
Google Calendar & Contacts ──[Ingestion Service]──────────────┤
                                                              ▼
                                                        User Context
                                                              │
                                                              ▼
Telegram ◄──[Notification Service]◄──[Nudge Engine]◄── LLM Insight (Gemini)
Browser PWA (Web Push)
```

### Component Overview
* **Data Layer (`app/Memory/`):** Implements multi-tenancy by isolating databases under `Memory/data/{user_id}/mirror.db` (SQLite) and vector data under `Memory/data/{user_id}/chroma/` (ChromaDB).
* **Intelligence Layer (`app/llm_module/`):** Generates structured insights using Gemini LLM models. It extracts goals, tasks, recent actions, and behavior patterns, validating the LLM's output against strict Pydantic schemas.
* **Decision Engine (`app/Remind/`):** A rules-based engine that maps boolean signals from the LLM (e.g., `needs_correction`, `needs_activation`) into high/medium/low priority nudges.
* **Delivery Layer (`app/notification_service.py`):** Delivers nudges proactively using **Web Push** (browser notifications for the Next.js PWA) and **Telegram** (featuring inline button callbacks to log user response actions).
* **MCP Extension (`mcp_servers/tasks_server/`):** Exposes tasks, goals, and user context directly to external client LLMs via standard Model Context Protocol tools.

---

## ⚙️ The "How": Engineering Mechanics

### 1. Dynamic Nudge Generation
Instead of invoking the LLM for every notification, Nudge executes a single daily cycle:
1. The **Morning Job** queries the SQLite database, flattens the user's context, and passes it to the LLM.
2. The LLM returns a structured JSON payload containing high-level `decision_signals`.
3. The backend uses these signals to generate a pool of candidate nudges (the **Nudge Bank**) and caches them.
4. Throughout the day, the system delivers cached nudges or triggers task-specific alerts using Python rule evaluations (no further LLM calls required).

### 2. Python Path Bootstrapping
To keep modules modular without requiring package distribution setup, the system relies on runtime `sys.path` patching. Entrypoints (such as `app/main.py` or the API routers) insert relative sibling folders into the path at startup, permitting clean imports across sub-folders.

---

## 🛑 Project Status & Reflection

**Status:** *Archived / Active Development Paused*

During the development of Phase 1.5, we pivoted the engineering of Nudge toward building a standalone **Tasks MCP Server** (`mcp_servers/tasks_server/`) to allow external client LLMs (like Claude Desktop) to interface directly with our local databases over the Model Context Protocol. We continued building and refining this setup.

However, after using Google’s native **Personal Intelligence** extensions directly inside core applications (such as Gmail, Calendar, and Drive), the overhead of maintaining a custom, siloed data synchronization and scheduling layer felt increasingly redundant. The native, platform-level RAG executed data synthesis far more seamlessly than a custom, siloed build could achieve. Consequently, we chose to pause active development and preserve Nudge as an open-source case study in modular context design, localized storage isolation, and early MCP tool implementations.

---

<details>
<summary>📂 Historical Setup & Running Commands (Archived)</summary>

### Running CLI Dry-Run
```bash
# Run with Mock LLM responses (default)
python app/main.py

# Run with real Gemini API model
python app/main.py --real
```

### Starting Servers
* **Backend:** `uvicorn --app-dir app api.main:app --reload`
* **Frontend:** `cd Dashboard && npm run dev`
* **Tasks MCP Server:** `python -m mcp_servers.tasks_server.server`

### Testing
```bash
# Unit tests
python -m pytest app/Memory/tests/
python -m pytest app/Orchestrator/tests/
python -m pytest app/llm_module/tests/
python -m pytest app/Remind/test_nudge_engine.py

# API integration tests (requires live server)
python -m pytest app/tests/test_full_system.py
```
</details>
