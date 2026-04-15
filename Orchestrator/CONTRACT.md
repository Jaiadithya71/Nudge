# ORCHESTRATOR — CONTRACT.md

## Core Function

run_scheduler(user_id: str)

---

## Internal Calls

1. memory.build_user_context()
2. llm.generate_insight()
3. nudge.generate_nudges()

---

## Job Execution

run_job(user_id, job_type)

job_type:
- morning
- midday
- evening
- event

---

## State Tracking

{
  "last_run": timestamp,
  "nudges_sent_today": int,
  "last_nudge_time": timestamp
}