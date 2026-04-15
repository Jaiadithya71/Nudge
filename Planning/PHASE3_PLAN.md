# Phase 3: The System Knows Your People

> Prerequisite: Phase 2 (patterns + recurring tasks)
> Goal: Surface contact relationships, detect relationship decay, generate social nudges.
> When complete: The system manages your relationships, not just your tasks.

---

## Current State

- Google Contacts sync is **working** — contacts are in SQLite and ChromaDB
- `contacts` table has: id, name, email, last_interaction, importance_score
- Contacts appear in `UserContext` but are **never forwarded to the LLM** (dropped in `_context_to_llm_dict()`)
- No dashboard UI for contacts
- No nudges related to contacts
- `last_interaction` is set at sync time and **never updated** based on calendar meetings or user actions

---

## Workstreams

### WS10: Contact Dashboard

**Purpose:** Show contacts on the dashboard, allow manual importance tagging.

**What to build:**

1. **Dashboard section: "People"**
   - List contacts grouped by importance (high/medium/low or starred/unstarred)
   - Show: name, email, last interaction date, days since last interaction
   - Click to expand: edit importance, add notes
   - Search/filter by name

2. **API endpoint:** `GET /api/contacts` (thin wrapper over context.contacts, but with sorting/filtering)

3. **Importance tagging:** `PATCH /api/contacts/{id}` — update `importance_score`
   - Add to `Memory/memory.py`: `update_contact(user_id, contact_id, updates)`

4. **Contact notes:** Optional free-text field per contact
   - Add `notes TEXT` column to contacts table
   - Useful for: "Met at conference", "Prefers email over phone", etc.

**Files to create/modify:**

| File | Change |
|------|--------|
| `Memory/schema.sql` | Add `notes TEXT` column to contacts |
| `Memory/memory.py` | Add `update_contact()` |
| `api/routes/contacts.py` | NEW — GET list, PATCH update |
| `api/main.py` | Register contacts router |
| `Dashboard/components/ContactList.tsx` | NEW — contact list with importance tags |
| `Dashboard/app/page.tsx` | Add "People" section |
| `Dashboard/lib/api.ts` | Add contact API functions |
| `Dashboard/types/index.ts` | Update Contact type |

---

### WS11: Relationship Decay Detection

**Purpose:** Detect contacts you're losing touch with and generate "reach out" nudges.

**What to build:**

1. **Decay detector:** `Memory/relationship_detector.py`
   ```python
   def detect_decaying_relationships(user_id: str) -> list[dict]:
       """
       Find contacts where days_since_last_interaction exceeds the threshold
       based on their importance level.
       
       Thresholds:
         importance >= 0.8 (high):   14 days
         importance >= 0.5 (medium): 30 days
         importance < 0.5 (low):     90 days
       
       Returns list of {contact_id, name, days_since, importance, suggested_action}
       """
   ```

2. **Update `last_interaction` from calendar events:**
   - After Google Calendar sync, match event attendees against contact emails
   - Update `last_interaction` for any matching contact
   - This makes decay detection accurate without manual logging

3. **New nudge type: `social`**
   - Add to `Remind/nudge_engine.py` message templates
   - Priority: low (don't compete with task nudges)
   - Message: "You haven't connected with {name} in {days} days. Reach out?"
   - Max 1 social nudge per day

4. **Wire into orchestrator:**
   - Run decay detection in the evening job (reflection time = good time for social awareness)
   - If decaying contacts found, inject `needs_social_nudge` signal into insight
   - Nudge engine picks it up and generates the social nudge

**Files to create/modify:**

| File | Change |
|------|--------|
| `Memory/relationship_detector.py` | NEW — decay detection logic |
| `Memory/memory.py` | Add `update_contact_interaction()` |
| `input/ingestion_service.py` | After event sync, update contact last_interaction from attendees |
| `Remind/nudge_engine.py` | Add `social` nudge type with templates |
| `Orchestrator/orchestrator.py` | Run decay detection in evening job, inject signal |

---

### WS12: Meeting Prep Context

**Purpose:** When you have a meeting today with someone in your contacts, show relevant context.

**What to build:**

1. **Match today's calendar attendees to contacts:**
   - After sync, cross-reference event attendee emails with contacts table
   - Store matches as event metadata or in a join table

2. **Dashboard: meeting prep cards**
   - In the "Today" calendar section, show contact info under each event
   - "Meeting with John Smith (john@example.com) — last met 15 days ago"
   - If the contact has notes, show them

3. **Forward events + contacts to LLM:**
   - Modify `_context_to_llm_dict()` to include:
     ```python
     "today_events": [
         {"title": "1:1 with John", "time": "2pm", "attendee": "John Smith", "last_met": "March 5"}
     ]
     ```
   - Enables insights: "You have a meeting with John today — you haven't spoken in 2 weeks"

**Files to modify:**

| File | Change |
|------|--------|
| `Orchestrator/orchestrator.py` | Enhance `_context_to_llm_dict()` to include events and contacts |
| `Dashboard/components/CalendarView.tsx` | Show attendee info from contacts |
| `Memory/memory.py` | Add `match_attendees_to_contacts()` helper |

---

## Phase 3 Success Criteria

1. Contacts visible on the dashboard with importance tags
2. `last_interaction` auto-updates from calendar events (not just initial sync)
3. "Reach out" nudges fire for neglected high-importance contacts
4. Today's meeting attendees show contact context on the dashboard
5. LLM receives event and contact context, generating socially-aware insights
6. Social nudges respect rate limits (max 1/day, don't compete with task nudges)
