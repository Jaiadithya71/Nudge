# Implementation Plan: Git-Synced Telegram Accountability Bot (Nudge Edition)

This plan details the steps to build a Git-Synced, Telegram-based Remote Accountability Agent that tracks your career goals in [complex_accountability_plan.md](file:///c:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Next_Move/complex_accountability_plan.md) and allows you to log progress and query status remotely from your phone.

---

## User Review Required

> [!IMPORTANT]
> **GitHub Configuration:** To enable the cloud bot to write directly to your roadmap, we will need to configure a GitHub repository for the `Nudge` folder. You will need to create a private GitHub repository and generate a Personal Access Token (PAT) with repository write permissions.
> Do NOT share this token in chat; we will configure it locally in a secured `.env` file that is git-ignored.

---

## Open Questions

*   **Hosting Platform:** Do you have a preferred free hosting provider for the Python cloud script? (We recommend **Render** or **Railway**, as they offer free tiers that support 24/7 background Python daemons).
*   **Telegram Bot Setup:** Have you created a Telegram Bot yet via BotFather? (If not, we will guide you through this 1-minute step).

---

## Proposed Changes

### Nudge Workspace

We will add a new `bot` folder containing the code for both the cloud gateway and the local sync process, along with a project specification markdown file.

---

#### [NEW] [remote_agent_spec.md](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/remote_agent_spec.md)
A document detailing the remote agent's objectives, architecture, data schemas, and operating commands.

#### [NEW] [cloud_bot.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/cloud_bot.py)
The Python script to be deployed to the cloud. It listens for incoming Telegram messages, uses the Gemini API (Free Tier) to parse them, and pushes commits containing updates to your private GitHub repository.

#### [NEW] [local_sync.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/local_sync.py)
The local Python daemon script running on your laptop. It pulls changes from GitHub, checks local status (e.g., git commits in showcase projects), and posts progress back to the cloud.

#### [NEW] [requirements.txt](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/requirements.txt)
Python package dependencies:
*   `python-telegram-bot` (for Telegram interface)
*   `google-genai` (for Gemini Free Tier integration)
*   `GitPython` (for programmatic git pull/push operations)
*   `python-dotenv` (for secure environment variables)

#### [NEW] [run_sync.bat](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/run_sync.bat)
A Windows Batch file to easily schedule the local sync process to run on startup or on a regular interval using Windows Task Scheduler.

---

## Verification Plan

### Automated & Manual Verification Steps
1.  **Dry-run local scripts:** Test `cloud_bot.py` locally on the laptop first to confirm it connects to the Telegram Bot API and parses messages correctly.
2.  **Git integration test:** Verify that `GitPython` can programmatically pull and commit changes to a test branch.
3.  **Proactive push test:** Simulate a cron trigger to verify that the bot successfully pushes a markdown-formatted message to your Telegram ID.
4.  **End-to-end flow:** Turn off the local script, send an offline message from the phone, turn the local script on, and verify the message queue is processed and the local Markdown files are updated.
