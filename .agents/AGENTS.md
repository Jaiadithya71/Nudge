# Agent Context — Jaiadithya A

## Who I Am
- **Name:** Jaiadithya A
- **College:** SASTRA Deemed University
- **Goal:** Tokyo Tech career execution — targeting firms like Mercari, PayPay within 36 months
- **Career Plan:** See `complex_accountability_plan.md` (3-year roadmap with weekly tracking)

## My Data Sources

### Files on this machine
- **Career Plan:** `complex_accountability_plan.md` — read this for current progress, weekly targets, study hours
- **College Database:** `data/sastra_data.db` — SQLite database with student records, photos, academic info. Query with `bot/command_handlers.py`
- **Identity & Voice:** `reusable_assets/identity_kernel/personality.yaml` — the "Mirror" voice guidelines (concise, direct, semi-formal)

### Google Drive
- Accessible via `~/google_drive/` mount (rclone)
- Contains: resumes, project docs, certificates, coursework, personal documents

### Google Contacts
- My professional network and connections
- Accessible via Google People API (credentials in `.env`)

## How to Use This Context

When I ask you to:
- **Draft an email** → Read my plan and progress first, use professional but approachable tone
- **Write a LinkedIn post** → Reference real achievements from `complex_accountability_plan.md`
- **Look up a student** → Query `data/sastra_data.db` using the search term across all tables
- **Check my progress** → Read the current week's row in the accountability plan
- **Draft a cover letter** → Reference my goals, projects, and career plan
- **Check connections** → Use Google Contacts data

## Communication Style
- Semi-formal, concise, no filler phrases
- For professional outreach: respectful, specific, reference shared context
- For LinkedIn: confident but authentic, highlight real numbers/achievements

## Antigravity /schedule Cron (Server Laptop Role)

When you are running as the always-on agent inside the Antigravity session on the Server Laptop, you are configured with a `/schedule` cron that checks `bot/telegram_inbox.json` every 3 minutes.
For each pending message in the inbox:
1. Read the "text" field.
2. Process the query using your full capabilities (file access, SQLite DB query, web search, covers, resumes, contacts, etc.).
3. Formulate your response in accordance with the "Mirror" personality guidelines (concise, direct, semi-formal).
4. Import and call `mark_inbox_processed(msg_id)` from `bot/message_queue.py`.
5. Import and call `write_to_outbox(msg_id, response_text)` from `bot/message_queue.py`.

