# ORCHESTRATOR MODULE — SPEC.md

## 1. Purpose

Coordinate the entire system lifecycle:

- trigger data ingestion
- build user context
- generate insights
- generate nudges
- enforce timing and limits

---

## 2. Scope

### DOES:
- schedule jobs (time-based)
- execute pipelines
- manage per-user execution
- track system state

### DOES NOT:
- store user data (memory module handles that)
- generate insights (LLM module)
- generate nudges (nudge engine)

---

## 3. Core Responsibilities

1. Scheduler (time-based triggers)
2. Pipeline Executor
3. State Manager
4. Rate Limiter

---

## 4. System Loop

Observe → Understand → Decide → Act → Learn

---

## 5. Job Types

### 1. Morning Job
- build context
- generate insight
- generate planning nudges

---

### 2. Midday Check
- detect inactivity
- trigger activation nudges

---

### 3. Evening Reflection
- evaluate day
- generate reflection nudges

---

### 4. Event-Based Trigger (optional)
- task overdue
- meeting completed