# 🚀 API LAYER — FULL SPECIFICATION & IMPLEMENTATION GUIDE

---

# 1. 🎯 PURPOSE

The API Layer exposes the internal intelligence system as a **service**.

It acts as the **single interface** between:

* Frontend (Web / Mobile / CLI)
* External inputs (user actions, integrations)
* Core system (Memory, LLM, Nudge Engine, Orchestrator)

---

# 2. 🧠 POSITION IN ARCHITECTURE

---

## Full System View

```
User (Web / Mobile / CLI)
        ↓
     API Layer   ← YOU ARE BUILDING THIS
        ↓
   Orchestrator
        ↓
Memory → LLM → Nudge Engine
        ↓
    Data Storage
```

---

## Responsibilities

### ✅ DOES:

* expose REST endpoints
* validate input/output
* orchestrate module calls
* provide real-time access to system state

### ❌ DOES NOT:

* implement business logic (delegated to modules)
* store raw data
* perform heavy processing

---

# 3. 🧱 TECH STACK

---

## Recommended:

* Python + FastAPI
* Uvicorn (server)
* Pydantic (validation)

---

## Why FastAPI:

* async support
* automatic OpenAPI docs
* strong typing
* easy integration with your Python modules

---

# 4. 📂 FOLDER STRUCTURE

---

```
api/
├── main.py              # FastAPI entry point
├── routes/
│   ├── context.py
│   ├── insight.py
│   ├── nudges.py
│   ├── actions.py
│   ├── system.py
│
├── schemas/
│   ├── context.py
│   ├── insight.py
│   ├── nudge.py
│   ├── action.py
│
├── services/
│   ├── orchestrator_service.py
│
└── dependencies.py      # shared objects
```

---

# 5. 🔌 CORE ENDPOINTS

---

# 5.1 GET /api/context

## Purpose:

Return current UserContext

---

## Flow:

```
API → MemoryEngine.build_user_context()
```

---

## Response:

```json
{
  "user_id": "jai",
  "tasks": {...},
  "goals": [...],
  "daily_summary": {...}
}
```

---

---

# 5.2 GET /api/insight

## Purpose:

Return latest insight

---

## Flow:

```
context → LLMEngine.generate_insight()
```

---

---

# 5.3 GET /api/nudges

## Purpose:

Return current nudges

---

## Flow:

```
context → insight → nudge_engine
```

---

---

# 5.4 POST /api/log-action (CRITICAL)

## Purpose:

Allow user to update system with real-time behavior

---

## Request:

```json
{
  "user_id": "jai",
  "action": "completed_task",
  "metadata": {
    "task": "Revise DSA"
  }
}
```

---

## Flow:

```
API → MemoryEngine.log_action()
```

---

## Impact:

* updates behavior tracking
* influences future nudges

---

---

# 5.5 POST /api/run-cycle

## Purpose:

Trigger full pipeline manually

---

## Flow:

```
Memory → LLM → Nudge Engine
```

---

---

# 6. 🧩 IMPLEMENTATION DETAILS

---

## main.py

```python
from fastapi import FastAPI
from routes import context, insight, nudges, actions, system

app = FastAPI()

app.include_router(context.router, prefix="/api")
app.include_router(insight.router, prefix="/api")
app.include_router(nudges.router, prefix="/api")
app.include_router(actions.router, prefix="/api")
app.include_router(system.router, prefix="/api")
```

---

---

## Example Route: context.py

```python
from fastapi import APIRouter
from dependencies import memory_engine

router = APIRouter()

@router.get("/context")
def get_context(user_id: str):
    return memory_engine.build_user_context(user_id)
```

---

---

## dependencies.py

```python
from memory.memory_engine import MemoryEngine
from llm.llm_engine import LLMEngine
from nudge.nudge_engine import NudgeEngine

memory_engine = MemoryEngine()
llm_engine = LLMEngine()
nudge_engine = NudgeEngine()
```

---

---

## orchestrator_service.py

```python
def run_full_cycle(user_id):
    context = memory_engine.build_user_context(user_id)
    insight = llm_engine.generate_insight(context)
    nudges = nudge_engine.generate_nudges(insight, context, {}, {})
    
    return {
        "context": context,
        "insight": insight,
        "nudges": nudges
    }
```

---

# 7. 🧪 VALIDATION & ERROR HANDLING

---

## Must Handle:

* missing user_id
* invalid payload
* LLM failure
* empty data

---

## Response Format:

```json
{
  "status": "error",
  "message": "Invalid user_id"
}
```

---

---

# 8. 🔐 FUTURE CONSIDERATIONS (NOT MVP)

---

* authentication (JWT)
* rate limiting
* multi-user scaling
* async background jobs

---

---

# 9. 🧪 TESTING PLAN

---

## Test 1: Context Endpoint

* returns valid structure

---

## Test 2: Insight Endpoint

* always returns valid JSON

---

## Test 3: Nudge Endpoint

* reflects decision signals

---

## Test 4: Log Action

* updates memory correctly

---

## Test 5: Full Cycle

* returns all 3: context, insight, nudges

---

---

# 10. 📦 DELIVERABLES

---

Engineer must provide:

* working FastAPI server
* all endpoints functional
* tested with Postman / curl
* OpenAPI docs available at:

```
/docs
```

---

---

# 11. 🧠 KEY PRINCIPLES

---

1. API layer is a thin wrapper
2. Business logic stays in modules
3. Strict contracts between layers
4. System must remain modular

---

---

# 12. 🚀 FINAL GOAL

---

Transform system from:

```
Internal pipeline
```

→

```
Externally accessible intelligence service
```

---
