# NUDGE ENGINE — IMPLEMENTATION GUIDE

## Step 1: Decision Engine

Implement rules:

1. Overdue Tasks → HIGH priority correction
2. Low Completion Rate → MEDIUM productivity nudge
3. No Activity → Activation nudge

---

## Step 2: Priority Assignment

HIGH:
- overdue tasks
- off-track goals

MEDIUM:
- declining patterns

LOW:
- suggestions

---

## Step 3: Nudge Types

- correction
- reminder
- reflection
- activation

---

## Step 4: Message Templates

Example:

CORRECTION:
"You’ve delayed this multiple times. Let’s break it into something small and finish it today."

PRODUCTIVITY:
"You’re completing fewer tasks than usual. Focus on 1 high-impact task now."

ACTIVATION:
"You haven’t made progress today. Start with one small task to build momentum."

---

## Step 5: Tone Enforcement

Every message must:
- call out behavior (strict)
- offer action (supportive)

---

## Step 6: Limits

- max nudges/day
- avoid repetition