# Dogfooding Phase — Solo User Testing

**Stage:** Phase 1 (Solo Dogfooding) — experiencing the system as a real user, not testing APIs.

**Goal:** Answer — *"Does this system actually influence my day?"*

---

## Daily Log Template

```
DAY ___  [DATE]

Morning:
- Context correct (tasks/calendar): yes / no
- Insight useful: yes / no
- Nudges relevant: yes / no

Midday:
- Took action on a nudge: yes / no
- System felt reactive: yes / no

Evening:
- Reflection accurate: yes / no
- Would open it again tomorrow: yes / no

Notes:
-
```

---

## Phase 1 — Daily Routine

### Morning
- Does context reflect reality? (tasks + calendar correct?)
- Does the insight feel accurate or generic?
- Do nudges feel relevant?

### During the Day
- Complete a task → log action via dashboard
- Acknowledge or ignore nudges
- Notice: did nudges change based on your behavior?

### Evening
- Check reflection nudge and insight summary
- Does it reflect your actual day?

---

## Phase 2 — Edge Cases to Try

| Scenario | Expected Behavior |
|----------|-------------------|
| Do nothing all day | Activation nudges, stricter tone |
| Complete everything | Fewer nudges, positive reinforcement |
| Ignore nudges repeatedly | Escalation, tone shift (future) |

---

## Phase 3 — System Behavior Checks

- Add task in Notion → refresh → appears in UI?
- Add event in Google Calendar → reflected?
- Click Acknowledge → backend logs it → next nudges change?

---

## Red Flags to Watch

- **System feels static** → memory/insight problem
- **Nudges feel random** → decision signal problem
- **UI feels passive** → interaction design problem
- **You ignore it completely** → product value problem

---

## Success Criteria

1. You change behavior because of a nudge
2. You check it without being told
3. You feel: *"This understands what I'm doing"*

---

## After Testing (2–3 days)

Come back with:
- What felt useful
- What felt useless
- What you ignored

Next upgrades queued: push notifications, adaptive nudging, mobile experience.
