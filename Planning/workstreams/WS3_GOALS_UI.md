# WS3: Goal Management Dashboard

> Priority: P1 — Important
> Dependencies: None
> Estimated scope: 5 files changed, 1 new component

---

## Problem

Goals exist in the database schema, backend API (create + update), and TypeScript types — but the dashboard has zero UI for them. The context API returns `goals[]` but it's never displayed. Users can't create, view, or manage goals.

Additionally, the goals API is missing a DELETE endpoint, and the context endpoint returns goals but there's no way to link tasks to goals visually.

---

## What To Do

### Change 1: Add DELETE goal endpoint

**File:** `api/routes/goals.py`

Add a delete endpoint after the update endpoint:

```python
@router.delete("/goals/{goal_id}", status_code=204)
def delete(goal_id: str, user_id: str = Depends(get_current_user)):
    result = delete_goal(user_id, goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")
```

Update the import at the top to include `delete_goal`:
```python
from api.services.task_service import create_goal, update_goal, delete_goal
```

**File:** `api/services/task_service.py`

Add the `delete_goal` function:

```python
def delete_goal(user_id: str, goal_id: str) -> bool:
    try:
        deleted = mem.delete_goal(user_id, goal_id)
        if deleted:
            logger.info("[goal] Deleted: user=%s id=%s", user_id, goal_id)
        return deleted
    except Exception as e:
        logger.error("[goal] Delete failed: user=%s id=%s error=%s", user_id, goal_id, e)
        return False
```

**File:** `Memory/memory.py`

Check if `delete_goal(user_id, goal_id)` exists. If not, add it following the same pattern as `delete_task()`. It should:
1. DELETE FROM goals WHERE id = goal_id
2. Also SET goal_id = NULL on any tasks that reference this goal
3. Return True if a row was deleted

### Change 2: Add `deleteGoal` and `updateGoal` to frontend API

**File:** `Dashboard/lib/api.ts`

Add these functions (createGoal already exists at line 125):

```typescript
export const updateGoal = async (
  goalId: string,
  updates: { title?: string; description?: string; priority?: string }
): Promise<Goal> => {
  const res = await axios.patch(`${BASE_URL}/goals/${goalId}`, updates, {
    headers: authHeaders(),
  });
  return res.data;
};

export const deleteGoal = async (goalId: string): Promise<void> => {
  await axios.delete(`${BASE_URL}/goals/${goalId}`, { headers: authHeaders() });
};
```

### Change 3: Create GoalList component

**File:** `Dashboard/components/GoalList.tsx` (NEW FILE)

Build a component that:
- Displays goals grouped by priority (high, medium, low)
- Each goal row shows: title, description (truncated), priority badge, task count linked to it
- Click to expand: edit title, description, priority
- Delete button with confirmation
- Shows linked task titles under each goal (from the `tasks` prop filtered by `goal_id`)

**Design guidelines (match existing style):**
- Use the same rounded-xl card style as `TaskList.tsx`
- Priority badges: high = red dot, medium = yellow dot, low = green dot
- Expand/collapse pattern: same as TaskRow in TaskList.tsx
- Save/Cancel buttons: same styling as TaskList.tsx

**Props interface:**
```typescript
interface Props {
  goals: Goal[];
  tasks: Task[];  // to show linked tasks per goal
  onGoalsChanged: () => void;
}
```

### Change 4: Add GoalList + quick-add goal to dashboard

**File:** `Dashboard/app/page.tsx`

1. Import GoalList and createGoal/deleteGoal from api
2. Add a "Goals" section between "Tasks" and "Today" sections
3. Add a quick-add input for goals (same pattern as task quick-add)
4. Pass `context.goals` and `context.tasks` to GoalList

The goals section should look like:

```tsx
<Section title="Goals" loading={contextLoading} error={contextError}>
  <div className="flex gap-2 mb-4">
    <input
      type="text"
      value={goalAdd}
      onChange={(e) => setGoalAdd(e.target.value)}
      onKeyDown={(e) => e.key === "Enter" && handleGoalAdd()}
      placeholder="What are you working toward?"
      className="flex-1 text-sm border border-gray-200 rounded-xl px-4 py-2.5 focus:outline-none focus:border-black"
    />
    <button
      onClick={handleGoalAdd}
      disabled={addingGoal || !goalAdd.trim()}
      className="text-sm px-5 py-2.5 bg-black text-white rounded-xl hover:bg-gray-800 disabled:opacity-40 transition-colors font-medium"
    >
      {addingGoal ? "..." : "+ Add"}
    </button>
  </div>
  {context && (
    <GoalList
      goals={context.goals}
      tasks={context.tasks}
      onGoalsChanged={fetchContext}
    />
  )}
</Section>
```

### Change 5: Add goal selector to TaskRow

**File:** `Dashboard/components/TaskList.tsx`

In the expanded editor section of TaskRow, add a goal selector dropdown between "Due date" and "Remind me at". This allows linking a task to a goal.

```tsx
{/* Goal link */}
<div className="space-y-1">
  <label className="text-xs font-medium text-gray-500">Linked goal</label>
  <select
    value={goalId}
    onChange={(e) => setGoalId(e.target.value)}
    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-black bg-white"
  >
    <option value="">None</option>
    {goals.map((g) => (
      <option key={g.id} value={g.id}>{g.title}</option>
    ))}
  </select>
</div>
```

This requires passing `goals` down through the component chain:
- `page.tsx` → `TaskList` (add `goals` prop)
- `TaskList` → `TaskGroup` (pass through)
- `TaskGroup` → `TaskRow` (pass through)

And saving `goal_id` in `saveEdits()`.

---

## What NOT To Do

- Do NOT create a separate goals page/route — keep it on the main dashboard
- Do NOT add sub-goals or goal hierarchies
- Do NOT add progress tracking or percentage completion
- Do NOT modify the `goals` database schema — it already has all needed columns

---

## Files Touched

| File | Change |
|------|--------|
| `Memory/memory.py` | Add `delete_goal()` if missing |
| `api/services/task_service.py` | Add `delete_goal()` function |
| `api/routes/goals.py` | Add DELETE endpoint |
| `Dashboard/lib/api.ts` | Add `updateGoal()`, `deleteGoal()` |
| `Dashboard/components/GoalList.tsx` | NEW — goal list with CRUD |
| `Dashboard/components/TaskList.tsx` | Add goal selector dropdown to TaskRow |
| `Dashboard/app/page.tsx` | Add Goals section, quick-add, import GoalList |

---

## Acceptance Criteria

1. Dashboard shows a "Goals" section with quick-add input
2. Can create a goal with just a title (priority defaults to "medium")
3. Can expand a goal to edit title, description, priority
4. Can delete a goal (with confirmation)
5. Deleting a goal nullifies `goal_id` on all linked tasks
6. Task expanded editor shows a dropdown to link the task to a goal
7. Goal card shows how many tasks are linked to it
8. Empty state: "No goals yet. Add one above."
9. No page reload required — all operations update via `fetchContext()`
