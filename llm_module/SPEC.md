# LLM MODULE — SPEC.md

## 1. Purpose

Convert UserContext → Insight

This module is responsible for:
- interpreting user behavior
- identifying patterns
- evaluating goal alignment
- generating structured reasoning

---

## 2. Scope

### DOES:
- Build prompt templates
- Call LLM (or mock mode)
- Parse output into Insight
- Enforce tone (70% strict, 30% supportive)

### DOES NOT:
- Access databases
- Generate nudges
- Handle UI

---

## 3. Core Flow

UserContext
  ↓
Preprocess
  ↓
Build Prompt
  ↓
LLM Call
  ↓
Parse JSON
  ↓
Validate
  ↓
Insight

---

## 4. Prompt Strategy (Option 1)

Simple template-based prompting.

Example:

"You are a behavioral analyst and performance coach.

Analyze:
- goals
- task behavior
- recent actions

Be:
- 70% direct and corrective
- 30% constructive

Output JSON in Insight format."

---

## 5. Constraints

- Must return valid JSON
- Must match Insight schema exactly
- Must support mock mode