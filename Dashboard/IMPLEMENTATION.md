# 🚀 WEB INTERFACE — IMPLEMENTATION GUIDE

---

# 1. 🎯 OBJECTIVE

Build a **web dashboard** that connects to the backend API and allows the user to:

* View daily context (tasks + calendar)
* View AI-generated insights
* View and interact with nudges
* Provide feedback (log actions)

---

# 2. 🧠 ROLE IN ARCHITECTURE

---

## System Position

```text
User (Browser)
    ↓
Next.js Frontend  ← YOU ARE BUILDING THIS
    ↓
API Layer (FastAPI)
    ↓
Core System (Memory + LLM + Nudge Engine)
```

---

## Responsibilities

### ✅ DOES:

* Fetch data from API
* Display structured information
* Allow user interaction (feedback loop)
* Provide real-time visibility

### ❌ DOES NOT:

* Run AI logic
* Store long-term data
* Perform heavy computation

---

# 3. 🧱 TECH STACK

---

* Next.js (App Router)
* React (hooks)
* Axios (API calls)
* TailwindCSS (styling)

---

# 4. 📂 FINAL FOLDER STRUCTURE

---

```text
app/
  page.tsx

components/
  NudgeCard.tsx
  InsightCard.tsx
  TaskList.tsx
  CalendarView.tsx

lib/
  api.ts

types/
  index.ts
```

---

# 5. 🔌 API CONTRACT (MANDATORY)

---

Base URL:

```text
http://localhost:8000/api
```

---

## Endpoints Used

---

### GET /context

Returns:

* tasks
* calendar events

---

### GET /insight

Returns:

* summary
* observations

---

### GET /nudges

Returns:

* list of nudges

---

### POST /log-action

Used for:

* user feedback
* interaction logging

---

# 6. 🧩 STEP-BY-STEP IMPLEMENTATION

---

# STEP 1 — DEFINE TYPES

---

File: `types/index.ts`

```ts
export type Task = {
  title: string;
  status: string;
};

export type Event = {
  title: string;
  start_time: string;
  end_time: string;
};

export type Context = {
  tasks: {
    pending: Task[];
    overdue: Task[];
  };
  calendar_events: Event[];
};

export type Insight = {
  summary: string;
  key_observations: string[];
};

export type Nudge = {
  type: string;
  message: string;
  priority: string;
};
```

---

# STEP 2 — API INTEGRATION

---

File: `lib/api.ts`

```ts
import axios from "axios";

const BASE_URL = "http://localhost:8000/api";

export const getContext = async (userId: string) => {
  const res = await axios.get(`${BASE_URL}/context`, {
    params: { user_id: userId },
  });
  return res.data;
};

export const getInsight = async (userId: string) => {
  const res = await axios.get(`${BASE_URL}/insight`, {
    params: { user_id: userId },
  });
  return res.data;
};

export const getNudges = async (userId: string) => {
  const res = await axios.get(`${BASE_URL}/nudges`, {
    params: { user_id: userId },
  });
  return res.data;
};

export const logAction = async (payload: any) => {
  await axios.post(`${BASE_URL}/log-action`, payload);
};
```

---

# STEP 3 — BUILD COMPONENTS

---

## 3.1 NudgeCard.tsx

```tsx
export default function NudgeCard({ nudge, onAction }) {
  return (
    <div className="border p-4 rounded-xl shadow-sm space-y-2">
      <p className="font-medium">{nudge.message}</p>

      <div className="text-sm text-gray-500">
        {nudge.type} • {nudge.priority}
      </div>

      <button
        className="text-blue-500 text-sm"
        onClick={() => onAction(nudge)}
      >
        Acknowledge
      </button>
    </div>
  );
}
```

---

## 3.2 InsightCard.tsx

```tsx
export default function InsightCard({ insight }) {
  return (
    <div className="border p-4 rounded-xl">
      <h2 className="font-semibold">Insight</h2>
      <p>{insight.summary}</p>
    </div>
  );
}
```

---

## 3.3 TaskList.tsx

```tsx
export default function TaskList({ tasks }) {
  return (
    <div>
      <h2 className="font-semibold">Tasks</h2>

      <ul>
        {tasks.pending.map((t, i) => (
          <li key={i}>{t.title}</li>
        ))}
      </ul>
    </div>
  );
}
```

---

## 3.4 CalendarView.tsx

```tsx
export default function CalendarView({ events }) {
  return (
    <div>
      <h2 className="font-semibold">Today</h2>

      <ul>
        {events.map((e, i) => (
          <li key={i}>
            {e.title} ({e.start_time} - {e.end_time})
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

# STEP 4 — MAIN DASHBOARD

---

File: `app/page.tsx`

```tsx
"use client";

import { useEffect, useState } from "react";
import { getContext, getInsight, getNudges, logAction } from "@/lib/api";

import NudgeCard from "@/components/NudgeCard";
import InsightCard from "@/components/InsightCard";
import TaskList from "@/components/TaskList";
import CalendarView from "@/components/CalendarView";

export default function Dashboard() {
  const [context, setContext] = useState(null);
  const [insight, setInsight] = useState(null);
  const [nudges, setNudges] = useState([]);

  const userId = "jai";

  const fetchData = async () => {
    const ctx = await getContext(userId);
    const ins = await getInsight(userId);
    const nud = await getNudges(userId);

    setContext(ctx);
    setInsight(ins);
    setNudges(nud);
  };

  useEffect(() => {
    fetchData();

    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (nudge) => {
    await logAction({
      user_id: userId,
      action: "acknowledged_nudge",
      metadata: { message: nudge.message },
    });
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Assistant</h1>

      {insight && <InsightCard insight={insight} />}

      {context && (
        <>
          <TaskList tasks={context.tasks} />
          <CalendarView events={context.calendar_events} />
        </>
      )}

      <div>
        <h2 className="text-xl font-semibold">Nudges</h2>
        {nudges.map((n, i) => (
          <NudgeCard key={i} nudge={n} onAction={handleAction} />
        ))}
      </div>
    </div>
  );
}
```

---

# 7. 🔄 DATA FLOW

---

```text
Frontend → GET /context
Frontend → GET /insight
Frontend → GET /nudges

User Action → POST /log-action
```

---

# 8. 🧪 TESTING CHECKLIST

---

### UI Loads

* page renders without crash

---

### Data Loads

* tasks visible
* events visible
* nudges visible

---

### Interaction Works

* clicking “Acknowledge” triggers API

---

### Polling Works

* data refreshes every 10s

---

# 9. 🚀 MVP COMPLETION CRITERIA

---

System is complete when:

* UI displays real data
* nudges are visible and actionable
* user actions are logged
* system updates dynamically

---

# 10. 🔥 FUTURE EXTENSIONS

---

* push notifications
* mobile PWA
* nudge snooze/ignore
* behavior analytics
* personalization UI

---

# 11. 🧠 KEY PRINCIPLE

---

This UI is NOT a dashboard.

It is:

> **the control interface for a behavioral intelligence system**

---
