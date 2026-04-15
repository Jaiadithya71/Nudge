# NUDGE ENGINE — TEST_PLAN.md

## Unit Tests

### Test 1: Overdue Task
Input: high severity procrastination
Output: correction nudge

### Test 2: Frequency Limit
Input: already 2 nudges sent
Output: no nudge

### Test 3: Time Window
Input: outside allowed time
Output: scheduled nudge

### Test 4: Tone
Ensure message contains:
- problem (strict)
- solution (supportive)

## Edge Cases
- empty insight
- conflicting priorities

## Performance
- decision < 50ms
