# Phase 6: The System Acts

> Prerequisite: Phases 1-5 (reliable reminders, learning, relationships, intelligence)
> Goal: The system takes actions on your behalf — with your authorization.
> When complete: From assistant to agent.

---

## Why This Is Last (Among Active Phases)

Acting on behalf of the user requires:
- **Trust:** The user must trust the system's judgment (built over months of accurate nudges)
- **Context:** The system must deeply understand the user (Phase 5)
- **Reversibility:** Actions must be undoable or require confirmation

If you skip to this phase, you get an agent that acts on shallow understanding — that's how you break things.

---

## Possible Actions (In Order of Risk)

### Low Risk (Implement First)
| Action | Mechanism | Reversible? |
|--------|-----------|-------------|
| Auto-schedule task into calendar | Google Calendar API create event | Yes — delete event |
| Draft a "thinking of you" message | Generate text, show for approval | Yes — user reviews before sending |
| Create a task from an insight | "LLM noticed X → suggests task Y" | Yes — delete task |
| Snooze all low-priority nudges during focus time | Suppress delivery, don't log | Yes — nudges resume after |

### Medium Risk (Implement Second)
| Action | Mechanism | Reversible? |
|--------|-----------|-------------|
| Send a scheduled message | Telegram/email API | No — needs confirmation |
| Reschedule a meeting | Google Calendar API update | Notify attendees |
| Reorder groceries | Integration with delivery service | Requires payment auth |

### High Risk (Design Only, Don't Build Yet)
| Action | Mechanism | Reversible? |
|--------|-----------|-------------|
| Reply to an email | Gmail API | No |
| Submit a form | Browser automation | No |
| Make a purchase | Payment API | No |

---

## Architecture Needed

### Action Authorization Framework
```python
class ActionRequest:
    action_type: str          # "schedule_task", "send_message", "draft_email"
    description: str          # human-readable: "Schedule 'Call dentist' for Tuesday 2pm"
    target: dict              # action-specific payload
    confidence: float         # system's confidence this is the right action (0-1)
    requires_confirmation: bool  # true for irreversible actions
    auto_approved: bool       # true only for low-risk + high-confidence
```

### Action Execution Pipeline
```
LLM Insight → Suggests Action → ActionRequest created
    → If auto_approved: execute immediately, log to audit
    → If requires_confirmation: show in dashboard for user approval
    → User approves → execute → log to audit
    → User rejects → log rejection, learn from it
```

### Audit Log
Every automated action logged to a new table:
```sql
CREATE TABLE action_log (
    id TEXT PRIMARY KEY,
    action_type TEXT,
    description TEXT,
    target_json TEXT,
    status TEXT,          -- 'proposed', 'approved', 'executed', 'rejected', 'failed'
    executed_at TIMESTAMP,
    user_approved BOOLEAN,
    created_at TIMESTAMP
);
```

---

## Phase 6 Success Criteria

1. System can auto-schedule a task into Google Calendar (with confirmation)
2. System can draft a "reach out" message and show it for approval
3. All automated actions are logged in an audit table
4. User can see pending action proposals in the dashboard
5. Rejected actions feed back into the learning loop (Phase 2)
6. No irreversible action is taken without explicit user confirmation
