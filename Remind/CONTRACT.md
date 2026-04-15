# NUDGE ENGINE — CONTRACT.md

## Function

generate_nudges(
    insight: dict,
    user_context: dict,
    history: dict,
    preferences: dict
) -> list

### 1. Insight (from LLM)
```json
{
  "summary": "string",
  "behavior_flags": ["string"],
  "decision_signals": {
    "needs_activation": false,
    "needs_correction": false,
    "goal_at_risk": false,
    "has_overdue_tasks": false
  }
}
```

---

## Input Contracts

### insight
- must follow Insight schema

### user_context
- must follow UserContext schema

### history
{
  "nudges_sent_today": int,
  "last_nudge_time": "ISO",
  "recent_nudges": []
}

### preferences
{
  "strictness": 0.7,
  "max_nudges_per_day": 3
}

---

## Output

List of Nudge objects

---

## Guarantees

- max 2 nudges per call
- no duplicate nudges
- respect user limits