# Remote Accountability Agent: Project Specification

This document details the objectives, architecture, and configuration steps for the **Git-Synced Remote Accountability Agent** (the remote counterpart to Antigravity).

---

## 1. Project Objectives
*   **Proactive Accountability:** Automatically push weekly audit notifications to your phone's lock screen on Sunday nights.
*   **24/7 Availability:** Allow you to log progress and query status from your phone even when your laptop is powered off or disconnected.
*   **Zero-Cost Setup:** Utilize free-tier cloud resources, free GitHub repositories, and Gemini API Free Tier to avoid subscription fees.
*   **Secure Remote Action:** Enable command execution (like running test suites or checking git status) without exposing your laptop to open ports or tunneling risks.

---

## 2. System Architecture

The following diagram illustrates the flow of messages between your phone and your laptop when your laptop is offline versus online:

```mermaid
flowchart TD
    subgraph Mobile Phone
        A[Telegram App]
    end
    
    subgraph Cloud Gateway (Always On)
        B[Telegram Bot Server]
        C[Gemini 1.5 Flash - Free Tier]
    end

    subgraph GitHub
        D[(Private Repository)]
    end

    subgraph Local Laptop
        E[Local Daemon Script]
        F[(Next_Move Plan.md)]
        G[Command Shell / Git Status]
    end

    A <-->|1. Chat & Button Clicks| B
    B <-->|2. Parse Request| C
    B <-->|3. Commit Changes| D
    E <-->|4. Auto-Pull & Sync| D
    E <-->|5. Update File| F
    E <-->|6. Run Whitelisted Cmds| G
```

---

## 3. Core Features

### A. Proactive Audit Loop
*   At a scheduled time (e.g., Sunday 9:00 PM IST), the Cloud Bot sends a structured Telegram message listing your current week's targets (from [complex_accountability_plan.md](file:///c:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Next_Move/complex_accountability_plan.md)).
*   It displays interactive inline buttons (e.g., `[Pass]`, `[Fail]`, `[Reschedule]`) for quick response on your phone.
*   Once you answer, the bot writes the results directly into the weekly audit table.

### B. Natural Language Command Processing
You do not need to memorize commands. You can text the bot in plain English. The Gemini API translates your intent:
*   *"I just studied Japanese for 1 hour"* $\rightarrow$ Bot adds `1.0` to the study hours cell.
*   *"Show me my goals for this week"* $\rightarrow$ Bot reads the markdown file and formats the weekly targets as a chat message.
*   *"Check if my tests are passing"* $\rightarrow$ Bot queues a command. Once the laptop comes online, the daemon runs the test command and messages the test output/screenshot back to you.

---

## 4. Step-by-Step Setup Guide

### Phase 1: Telegram Bot Registration
1. Open Telegram on your phone or desktop and search for `@BotFather`.
2. Send the command `/newbot` and follow the instructions to choose a name and username.
3. Save the **HTTP API Bot Token** provided by BotFather.
4. Search for your bot username in Telegram and click **Start**.

### Phase 2: Private GitHub Repository
1. Initialize a Git repository inside `C:\Users\jaiad\Personal_Work_Related\Personal Projects\Nudge` if you haven't already.
2. Create a new **private** repository on GitHub.
3. Push your local files to GitHub.
4. Go to your GitHub Account Settings $\rightarrow$ **Developer Settings** $\rightarrow$ **Personal Access Tokens (Tokens classic)** $\rightarrow$ Generate a token with `repo` scope. Save this token.

### Phase 3: Cloud Bot Deployment (Always-On)
1. We will write the `cloud_bot.py` script.
2. Create a free account on **Render** (or Railway).
3. Connect your GitHub repository to Render and configure it as a **Web Service** or **Background Worker**.
4. Set up the Environment Variables on Render:
   * `TELEGRAM_BOT_TOKEN`
   * `GEMINI_API_KEY` (Free Tier key from Google AI Studio)
   * `GITHUB_PAT` (Your Personal Access Token)

### Phase 4: Local Laptop Daemon Configuration
1. We will write the `local_sync.py` script.
2. Configure Windows Task Scheduler on your laptop to run `run_sync.bat` every time you log in.
3. The script will run silently in the background, checking for new commits from the cloud bot and updating your files.
