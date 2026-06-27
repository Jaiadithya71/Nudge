# Project Handover Guide: Nudge (Remote Accountability Agent)

This document serves as the master guide for the developer agent tasked with implementing **Project Nudge**. It details the objectives, architecture, codebase structure, and reusable modules from `Project_Mirror_Unified`.

---

## 1. Project Overview & Objective
The goal of **Nudge** is to build a **Git-Synced, Telegram-based Remote Accountability Agent** that keeps the user (Jaiadithya A) on track with his Tokyo Tech Career Execution Plan in [complex_accountability_plan.md](file:///c:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Next_Move/complex_accountability_plan.md).

The agent must support:
1.  **Proactive Weekly Audits:** Pinging the user's Telegram every Sunday night at 9:00 PM IST with weekly milestones, using interactive buttons for replies.
2.  **Conversational Loggers:** Accepting natural language inputs from the user (e.g., *"studied Japanese for 2 hours today"*, *"did 3 LeetCode problems"*) and updating the local Markdown tables automatically.
3.  **Laptop Command Execution:** Executing basic whitelisted terminal commands (e.g., `git status`, running tests) and messaging back the outputs/screenshots.
4.  **24/7 Queueing:** Handling messages sent when the laptop is turned off, queueing them in Telegram, and processing them automatically when the laptop boots up.

---

## 2. System Architecture & Sync Loop

The bot operates on a **split-architecture** (Cloud + Local Laptop) bridged via **Git/GitHub**:

```
📱 Phone (Telegram) <---> ☁️ Cloud Bot Daemon (Always On) 
                               │
                               ▼ (Commits changes to GitHub)
                       🐙 GitHub Private Repository
                               ▲
                               │ (Auto-pulls & runs local scripts)
                       💻 Local Laptop Daemon (Windows Task Scheduler)
                               │
                               ▼ (Reads / Writes)
                       📄 complex_accountability_plan.md
```

### Flow of Offline Messages:
1.  User texts the bot while the laptop is offline.
2.  Telegram stores the unread messages in the cloud queue.
3.  When the laptop boots up, the local `local_sync.py` script starts:
    *   It fetches unread messages from the Telegram bot.
    *   It uses the **Gemini 1.5 Flash Free Tier** (via the Google Gen AI SDK) to parse the user's intent.
    *   It modifies [complex_accountability_plan.md](file:///c:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Next_Move/complex_accountability_plan.md) locally on the laptop.
    *   It pushes the updated file to GitHub, keeping both sides perfectly in sync.

---

## 3. Reusable Assets (Copied from Project Mirror)

We have copied the best components from `Project_Mirror_Unified` into the [reusable_assets/](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/reusable_assets) folder. The developer agent should leverage these directly:

### A. Personality and Guardrails
*   **Location:** [reusable_assets/identity_kernel/](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/reusable_assets/identity_kernel)
*   **Files:** 
    *   [personality.yaml](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/reusable_assets/identity_kernel/personality.yaml): Sets the "Mirror" assistant voice (concise, direct, semi-formal, avoids filler phrases).
    *   [logic_gates.yaml](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/reusable_assets/identity_kernel/logic_gates.yaml): Restricts the agent's actions (e.g., calendar focus blocks, spend thresholds, draft-before-send policies).
*   **Developer Directive:** Use these parameters in your LLM system prompt so the Nudge agent maintains the exact identity and safety boundaries established in the Mirror project.

### B. Sync Adapters & Clients
*   **Location:** [reusable_assets/integrations/](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/reusable_assets/integrations)
*   **Files:**
    *   [notion_client.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/reusable_assets/integrations/notion_client.py): Notion integration engine for sync operations.
    *   [gcal_client.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/reusable_assets/integrations/gcal_client.py): Google Calendar integration client.
*   **Developer Directive:** When the user requests to expand the Nudge agent to sync tasks or schedules with Google Calendar or Notion, reuse these pre-built API integrations instead of writing them from scratch.

---

## 4. Target Directory Structure

The developer agent must construct the codebase in this layout:

```
C:\Users\jaiad\Personal_Work_Related\Personal Projects\Nudge\
├── HANDOVER.md                     # This file
├── remote_agent_spec.md            # User-facing project specification
├── implementation_plan.md          # Step-by-step developer task list
├── reusable_assets/                # Reference assets from Project Mirror
│   ├── identity_kernel/
│   └── integrations/
└── bot/                            # Target codebase directory
    ├── cloud_bot.py                # Always-on Cloud Bot code
    ├── local_sync.py               # Laptop boot/sync daemon
    ├── requirements.txt            # Python dependencies
    ├── .env.example                # Shell template for secrets
    └── run_sync.bat                # Windows Task Scheduler trigger script
```

---

## 5. Implementation Specifications

### A. Cloud Bot (`cloud_bot.py`)
*   Should run a Telegram bot instance using `python-telegram-bot` (v20+).
*   Integrates the new Google Gen AI SDK:
    ```python
    from google import genai
    client = genai.Client()
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Your prompt here'
    )
    ```
*   Upon receiving an audit response or logging event, it uses `GitPython` to pull, commit, and push changes to the private GitHub repository.

### B. Local Daemon (`local_sync.py`)
*   Triggered on Windows startup/login via `run_sync.bat`.
*   Performs an initial `git pull`.
*   Polls the Telegram bot endpoint for unread messages (acting as the consumer of the offline queue).
*   Scrapes/reads local information:
    *   Git commit counts in the showcase project directories (like `This-or-That`).
    *   Optionally fetches LeetCode submission counts via public endpoints.
*   Fires updates back to the Telegram channel: *"Boot-up sequence completed. All items synced."*

---

## 6. How to Start Execution (For the Developer Agent)
1.  Read [remote_agent_spec.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/remote_agent_spec.md) and [implementation_plan.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/implementation_plan.md) to align on verification criteria.
2.  Begin by creating the `bot/requirements.txt` and setting up the Git repository structure for the `Nudge` directory.
3.  Write the `cloud_bot.py` and `local_sync.py` scripts sequentially, referencing the code in `reusable_assets/` for standard structures.
