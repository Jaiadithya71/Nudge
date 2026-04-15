# MEMORY MODULE — CONTRACT.md

## Public APIs

### build_user_context
Input: user_id
Output: UserContext

### log_action
Input: user_id, action dict
Output: None

### ingest
Input: entity_type, payload, user_id

### semantic_search
Input: user_id, query
Output: list

## Rules
- Always require user_id
- Deterministic outputs
- No schema leakage
