# ORCHESTRATOR — IMPLEMENTATION GUIDE

## Step 1: Scheduler Setup

Use simple loop:

while True:
    check time
    trigger jobs
    sleep

---

## Step 2: Job Definitions

### Morning Job
- build context
- generate insight
- generate 1-2 nudges

---

### Midday Job
- check inactivity
- generate activation nudge

---

### Evening Job
- build context
- generate reflection nudge

---

## Step 3: Pipeline Execution

context = memory.build_user_context(user_id)
insight = llm.generate_insight(context)
nudges = nudge.generate_nudges(insight, context, history, preferences)

---

## Step 4: State Management

Track:
- last run time
- nudges count
- last nudge timestamp

---

## Step 5: Rate Limiting

- max nudges per day
- min gap between nudges (e.g. 2 hours)