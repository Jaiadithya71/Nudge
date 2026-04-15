# MEMORY MODULE — SPEC.md

## Purpose
Single source of truth for user data, behavior, and semantic memory.

## Responsibilities
- Data ingestion
- Storage (SQLite + Vector DB)
- Action logging
- Pattern detection
- Build UserContext

## Isolation
Each user has:
data/{user_id}/
  - mirror.db
  - chroma/
  - media/

No shared DB or cross-user access.

## Core Functions
- build_user_context(user_id)
- log_action(user_id, action)
- ingest(entity_type, payload, user_id)

## Key Tables
- contacts
- tasks
- events
- goals
- user_actions
- behavior_patterns
- goal_alignment

## Output
Returns UserContext (strict schema)
