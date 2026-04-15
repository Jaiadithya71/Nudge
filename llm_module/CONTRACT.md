# LLM MODULE — CONTRACT.md

## 1. Public Interface

generate_insight(context: dict, mode="real") -> dict

---

## 2. Input Contract

Must match UserContext:

- goals
- tasks
- recent_actions
- behavior_patterns
- daily_summary

---

## 3. Output Contract

## Insight (JSON Output)
```json
{
  "insight_id": "uuid",
  "summary": "High-level summary...",
  "key_observations": ["obs1", "obs2"],
  "goal_alignment": "Analysis paragraph...",
  "behavior_flags": ["flag1"],
  "opportunity_areas": ["area1"],
  "decision_signals": {
    "needs_activation": false,
    "needs_correction": false,
    "goal_at_risk": false,
    "has_overdue_tasks": false
  }
}
```

---

## 4. Modes

### real
- calls actual LLM

### mock
- returns deterministic output
- used for testing

---

## 5. Guarantees

- always returns valid structure
- no missing fields
- retry on invalid LLM output