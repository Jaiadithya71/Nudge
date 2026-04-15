# NUDGE ENGINE — SPEC.md

## 1. Purpose

Convert Insight + UserContext → Nudge(s)

This module decides:
- whether to nudge
- what type of nudge
- how strong the nudge should be
- what message to send

---

## 2. Scope

### DOES:
- Evaluate user state
- Apply rule-based decision logic
- Generate nudges using templates
- Enforce tone (70% strict, 30% supportive)

### DOES NOT:
- Access database directly
- Call external APIs
- Perform scheduling (handled by orchestrator)

---

## 3. Inputs

- Insight
- UserContext
- NudgeHistory
- Preferences

---

## 4. Core Pipeline

Insight + Context
      ↓
Decision Engine
      ↓
Priority Assignment
      ↓
Nudge Type Selection
      ↓
Message Generation (templates)
      ↓
Nudge Output