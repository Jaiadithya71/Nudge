# LLM MODULE — TEST_PLAN.md

## 1. Unit Tests

### Test: Valid Output
- input valid context
- output matches Insight schema

---

### Test: Invalid JSON Handling
- simulate bad LLM output
- ensure retry works

---

### Test: Missing Fields
- remove fields
- validation should fail

---

## 2. Mock Mode Tests

- deterministic output
- same input → same output

---

## 3. Edge Cases

### Empty Context
- no tasks
- no goals

Expected:
- still valid Insight

---

### Large Input
- many tasks

Expected:
- truncation works
- performance maintained