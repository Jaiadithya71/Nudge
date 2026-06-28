# Implementation Plan: Dual-Laptop Sync Architecture (Dev & Server Laptops)

This plan details how to set up your always-on **Server Laptop** (Windows) and synchronize it with your **Dev Laptop** (this Windows machine). 

---

## 1. Dual-Laptop Architecture Overview

```
 ┌─────────────────────────┐               ┌─────────────────────────┐
 │       DEV LAPTOP        │               │      SERVER LAPTOP      │
 │ (Your Active Workstation)│               │    (Always-On Windows)  │
 ├─────────────────────────┤               ├─────────────────────────┤
 │ • Edit bot code         │               │ • Runs cloud_bot.py 24/7│
 │ • Run local tests       │               │ • Runs Antigravity IDE  │
 │ • Write to Google Drive │               │ • Reads Google Drive    │
 └───────────┬─────────────┘               └─────────────▲───────────┘
             │                                           │
       (Push Code)                                  (Pull Code)
             ▼                                           │
 ┌─────────────────────────┐                             │
 │    GITHUB REPOSITORY    │─────────────────────────────┘
 │ (github.com/../Nudge)   │
 └─────────────────────────┘
             ▲
             │ (Push Progress Update)
             │
 ┌─────────────────────────┐
 │      TELEGRAM BOT       │◄─── logs progress from your phone 24/7
 └─────────────────────────┘
```

### Sync Mechanisms
1. **Codebase & Roadmap (`complex_accountability_plan.md`):** Synced via **GitHub**.
   * When you edit code on your **Dev Laptop**, you push to GitHub, and pull the updates on the **Server Laptop**.
   * When you log progress on Telegram from your phone, the bot on the **Server Laptop** pulls latest, updates `complex_accountability_plan.md` locally, commits, and pushes it back to GitHub.
   * To see the updated plan on your **Dev Laptop**, you run `git pull`.
2. **SQLite Database (`sastra_data.db`):** Synced via **Google Drive**.
   * Google Drive desktop sync client keeps the SQLite database synced between both laptops automatically, allowing the server bot to query updated student records.
3. **Remote Control:** Chrome Remote Desktop allows you to securely access the **Server Laptop's** visual desktop from your phone at any time.

---

## 2. Initial Migration & Setup Steps

### Step 1: Initial Laptop Server Provisioning
1. Set the **Server Laptop** power options to **Never Sleep** when plugged in.
2. Install **Chrome Remote Desktop** on the Server Laptop and configure mobile access.
3. Install the **Google Drive Desktop App** on the Server Laptop to mount your drive.

### Step 2: Codebase Transfer
1. On the **Server Laptop**, open PowerShell/Command Prompt.
2. Clone the repository from GitHub:
   ```cmd
   git clone https://github.com/Jaiadithya71/Nudge.git C:\Users\jaiad\Personal_Work_Related\Personal Projects\Nudge
   ```
3. Set up the virtual environment and install requirements:
   ```cmd
   cd C:\Users\jaiad\Personal_Work_Related\Personal Projects\Nudge
   python -m venv venv
   call venv\Scripts\activate.bat
   pip install -r bot\requirements.txt
   ```

### Step 3: Secrets & Database Setup
1. Copy the `.env` file from the Dev Laptop to the Server Laptop's `bot/` folder (transfer via Google Drive, CRD file share, or USB).
2. Ensure the SQLite database `sastra_data.db` is moved to a shared path in **Google Drive** (e.g., `G:\My Drive\Data extraction project\local_data_pipeline\sastra_data.db`) or copy it to the exact same local folder on the Server Laptop:
   `C:\Users\jaiad\Personal_Work_Related\Personal Projects\Data extraction project\local_data_pipeline\sastra_data.db`

---

## 3. Code Modifications

#### [MODIFY] [cloud_bot.py](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/cloud_bot.py)
* Add import of `message_queue` methods.
* Update `handle_message` to check for `>` command prefix.
  * Direct commands (`> git status`, `> screenshot`, etc.) are processed immediately using `dispatch_command` from `command_handlers.py` and output is sent back (including handling photo tuples for screenshots).
  * Normal messages are written to the inbox using `message_queue.write_to_inbox(text)` and the bot replies: `"🧠 Sent to Antigravity. Processing..."`.
* Add `/online` command handler showing the health of the Antigravity instance (`get_antigravity_health()`) and bot uptime.
* Register `outbox_monitor_job` using `application.job_queue` in the bot application. The job checks `telegram_outbox.json` every 10 seconds for any `ready` messages and delivers them to your Telegram chat.

#### [NEW] [run_bot.bat](file:///C:/Users/jaiad/Personal_Work_Related/Personal%20Projects/Nudge/bot/run_bot.bat)
A batch script to easily run the bot on the Server Laptop:
```batch
@echo off
cd /d "%~dp0.."
call venv\Scripts\activate.bat
python bot\cloud_bot.py
pause
```

---

## 4. Verification Plan

### Manual Verification
1. Verify Chrome Remote Desktop connection from your mobile phone.
2. Test a direct command `> screenshot` on Telegram. The Server Laptop should execute it natively, take a screenshot of its real display, and send it to your phone.
3. Test queue routing by sending a normal message, seeing it queue in `telegram_inbox.json` on the Server Laptop, having Antigravity process it, write to `telegram_outbox.json`, and the bot deliver it back to Telegram.
4. Test Git sync: log progress via the bot, verify it pushes to GitHub, and run `git pull` on your Dev Laptop to see the updated markdown file.
