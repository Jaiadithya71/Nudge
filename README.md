# Nudge 🎯 (Project Mirror)

**Nudge** is a personal AI system that observes your behavior, builds context from Google Calendar and Google Contacts, generates insights via a Large Language Model, and delivers proactive behavioral nudges to a **PWA (Android)** or via **Telegram** as a fallback.

It implements a continuous feedback loop designed to help you align daily actions with long-term goals:
$$\text{Observe} \longrightarrow \text{Understand} \longrightarrow \text{Decide} \longrightarrow \text{Act} \longrightarrow \text{Learn}$$

---

## 🗺️ Quick Onboarding Checklist
If you are new to the repo, follow these 4 steps to get the system running in under 5 minutes:
1. **Setup Env:** Copy `.env` configurations (see [Backend Setup](#1-backend-setup--configuration)).
2. **Local Dry-Run:** Execute `python app/main.py` in `MOCK` mode. If this passes, your local SQLite databases and engines are initialized correctly.
3. **Boot Backend:** Run `uvicorn --app-dir app api.main:app --reload` to start the API and orchestrator thread.
4. **Boot Frontend:** Run `npm run dev` inside `/Dashboard` and login using your `.env` credentials (`jai` / `nudge-admin-password`).

---

## 🏗️ Architecture & Module Layout

Nudge is designed with a modular structure that isolates data storage, intelligence, logic selection, and delivery channels:

```
Dashboard (Next.js PWA) ──[FastAPI REST API]──► SQLite & ChromaDB
                                                      │
Google Calendar & Contacts ──[Ingestion Service]──────┤
                                                      ▼
                                                User Context
                                                      │
                                                      ▼
Telegram ◄──[Notification Service]◄──[Nudge Engine]◄── LLM Insight (Gemini)
Browser PWA (Web Push)
```

| Component / Module | Role | Key Technology | Key Exports / Entrypoints |
|:---|:---|:---|:---|
| **`app/Memory/`** | Multi-tenant isolated database & vector storage | SQLite, ChromaDB, Pydantic v2 | `build_user_context()`, `log_action()`, `ingest()` |
| **`app/llm_module/`** | LLM client wrapper & prompt templates | `google-genai` (Gemini), Mock API | `generate_insight(context, mode)` |
| **`app/Remind/`** | Rules-based behavioral nudge selection engine | Python | `generate_nudges(insight, context, history, preferences)` |
| **`app/Orchestrator/`**| Schedulers & pipeline coordinators | Python | `run_job()`, `run_scheduler()` |
| **`app/input/`** | External data synchronizers | Google Calendar & People APIs | `IngestionService.ingest_all(user_id)` |
| **`app/api/`** | REST API Backend | FastAPI & Uvicorn | Routes under `/api/` prefix |
| **`mcp_servers/`** | Model Context Protocol servers | MCP SDK | Tasks server entrypoint |
| **`Dashboard/`** | Control center panel & task list PWA | Next.js, React, Tailwind CSS | Next.js Page components |

---

## ⚠️ Core Concept: The Python Path Bootstrap

Unlike standard packaged Python projects, Nudge's modules are not installed as packages. Instead, **`sys.path` is patched at runtime** to allow sibling directories to import each other. 
* Whenever you create a new entrypoint or script in a subfolder, you must inject the module directory paths at the very top before other imports (refer to the path setup code block at the top of [app/main.py](file:///c:/Users/Jaiadithya/Personal_Work_Related/Nudge/app/main.py)).
* Editors (like VS Code or PyCharm) might show broken imports unless you set `app/` and its subdirectories as source roots.

---

## 💾 Storage & Data Isolation

* **Isolated Databases:** Each user's database is separated. Upon login/seeding, SQLite databases are generated at `app/Memory/data/{user_id}/mirror.db`.
* **Chroma Vector Stores:** Vector databases are initialized at `app/Memory/data/{user_id}/chroma/` to embed tasks, goals, events, and contacts.
* **Logs:** Engine logs are directed to `data/mirror.log`.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Optional] Google Cloud Platform credentials for Calendar and Contacts sync.

---

### 1. Backend Setup & Configuration

Clone the repository and install the dependencies:
```bash
# Install Python dependencies
pip install -r requirements.txt
```

Create a `.env` file in the root directory and configure the environment:
```ini
# Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key
LLM_MODE=mock  # Set to "real" to make live Gemini calls

# Authentication
APP_USER_ID=jai
APP_PASSWORD=your-dashboard-password
JWT_SECRET_KEY=your-secure-jwt-secret

# Delivery Channels
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-personal-chat-id
TELEGRAM_USE_POLLING=true

# Web Push Keys (Run scripts/generate_vapid_keys.py to generate)
VAPID_PUBLIC_KEY=your-vapid-public-key
VAPID_PRIVATE_KEY=your-vapid-private-key
VAPID_EMAIL=mailto:your-email@example.com
```

To configure Google integration, place your OAuth credentials file in the root directory as `gcal_credentials.json`.

---

### 2. Frontend Setup

Install Next.js dependencies:
```bash
cd Dashboard
npm install
```

---

## 🏃 Running the System

### Run the Dry-Run Cycle (CLI Mode)
You can test the entire pipeline (Context Ingestion → LLM Insight → Nudge Generation → Delivery Mock) locally:
```bash
# Run with Mock LLM responses (default)
python app/main.py

# Run with real Gemini API model
python app/main.py --real
```

### Start the Backend Server (FastAPI)
Run the FastAPI development server from the root directory:
```bash
uvicorn --app-dir app api.main:app --reload
```
The interactive API documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Start the Frontend Server (Next.js)
Start the Next.js dev server:
```bash
cd Dashboard
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to view your control panel.

### Run the Tasks MCP Server
Expose your task list directly to Claude Desktop or external LLMs over the Model Context Protocol:
```bash
python -m mcp_servers.tasks_server.server
```

---

## 🧪 Running Tests

The test suite contains module-level tests and full API integration tests:

```bash
# Run unit tests on components
python -m pytest app/Memory/tests/
python -m pytest app/Orchestrator/tests/
python -m pytest app/llm_module/tests/
python -m pytest app/Remind/test_nudge_engine.py

# Run the full system integration test (requires live server running)
python -m pytest app/tests/test_full_system.py
```

---

## 🗺️ Project Roadmap

- **Phase 1 ✅ (Complete):** Reliable reminder tool. Tasks/goals CRUD dashboard, rules-based nudge engine, Web Push, Telegram, and standard test suite.
- **Phase 2 ⏳ (Next):** The System Learns. Behavioral pattern recognition engine, dynamic strictness adaptations, recurring tasks manager, and effectiveness statistics panel.
- **Phase 3 📅 (Planned):** Conversational MCP Bridge. Dynamic chat console on the dashboard, Google Calendar/Tasks MCP integrations, and LLM tool adapters.
