# Phase 4: Recurring Life Management

> Prerequisite: Phase 2 (recurring tasks), Phase 3 (contacts/calendar context)
> Goal: The system manages periodic life obligations — health, finance, home, social.
> When complete: You never forget a renewal, appointment, or recurring chore.

---

## Why This Phase Exists

Phase 2 adds basic recurring tasks ("Buy groceries every Sunday"). This phase turns that into a life management system — categorized, anticipatory, and calendar-aware.

---

## Workstreams

### WS13: Life Domains

**Purpose:** Categorize tasks and recurring obligations into life areas.

**What to build:**

1. **Domain taxonomy:**
   | Domain | Examples |
   |--------|---------|
   | Health | Dentist, eye exam, prescriptions, gym |
   | Finance | Insurance renewal, tax filing, bill payments |
   | Home | Groceries, cleaning, maintenance, repairs |
   | Work | Recurring reports, 1:1 prep, timesheet |
   | Social | Birthday reminders, call parents, meetups |
   | Personal | Hobbies, learning goals, self-care |

2. **Schema addition:**
   ```sql
   ALTER TABLE tasks ADD COLUMN domain TEXT;
   -- Values: 'health', 'finance', 'home', 'work', 'social', 'personal', null
   ```

3. **Dashboard:** Domain filter/tabs in the task list. Color-coded domain badges.

4. **Domain-aware nudges:** "You have 3 overdue Health tasks" vs. generic "3 tasks overdue"

---

### WS14: Anticipatory Nudges

**Purpose:** Remind before due, not after overdue.

**What to build:**

1. **New nudge type: `anticipatory`**
   - Fires X days before due date
   - Lead time based on domain defaults:
     - Finance: 14 days ("Insurance renewal is in 2 weeks")
     - Health: 7 days ("Dentist appointment next week")
     - Home: 1 day ("Groceries tomorrow")

2. **Schema addition:**
   ```sql
   ALTER TABLE tasks ADD COLUMN lead_days INTEGER DEFAULT 0;
   -- 0 = no anticipatory nudge, only standard behavior
   -- 7 = start nudging 7 days before due_date
   ```

3. **Orchestrator change:** In the morning job, check for tasks where `due_date - lead_days <= today` and inject anticipatory signals.

---

### WS15: Calendar-Aware Task Scheduling

**Purpose:** Suggest when to do tasks based on calendar availability.

**What to build:**

1. **Free slot detection:** From Google Calendar events, find gaps > 30 minutes
2. **Suggestion engine:** "You have a free hour at 2pm — good time for 'Call dentist'?"
3. **This is a nudge message enhancement, not an auto-scheduler.** The system suggests, the user decides.
4. **Requires:** Phase 3's event forwarding to LLM context

---

## Phase 4 Success Criteria

1. Tasks have domain categorization visible in the dashboard
2. Anticipatory nudges fire before due dates (not just after overdue)
3. Lead times are configurable per task or default by domain
4. System can identify free calendar slots and suggest task scheduling
5. Life domains show completion rates: "Finance: 3/5 tasks done this month"
