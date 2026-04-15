"use client";

import { useState } from "react";
import { Goal, Task } from "@/types";
import { updateGoal, deleteGoal } from "@/lib/api";

interface Props {
  goals: Goal[];
  tasks: Task[];
  onGoalsChanged: () => void;
}

const PRIORITY_ORDER = ["high", "medium", "low"];

const PRIORITY_DOT: Record<string, string> = {
  high:   "bg-red-400",
  medium: "bg-yellow-400",
  low:    "bg-green-400",
};

export default function GoalList({ goals, tasks, onGoalsChanged }: Props) {
  if (goals.length === 0) {
    return <p className="text-sm text-gray-400">No goals yet. Add one above.</p>;
  }

  const sorted = [...goals].sort(
    (a, b) => PRIORITY_ORDER.indexOf(a.priority) - PRIORITY_ORDER.indexOf(b.priority)
  );

  return (
    <ul className="space-y-2">
      {sorted.map((g) => (
        <GoalRow
          key={g.id}
          goal={g}
          linkedTasks={tasks.filter((t) => t.goal_id === g.id)}
          onGoalsChanged={onGoalsChanged}
        />
      ))}
    </ul>
  );
}

function GoalRow({ goal, linkedTasks, onGoalsChanged }: {
  goal: Goal;
  linkedTasks: Task[];
  onGoalsChanged: () => void;
}) {
  const [expanded, setExpanded]   = useState(false);
  const [title, setTitle]         = useState(goal.title);
  const [description, setDesc]    = useState(goal.description ?? "");
  const [priority, setPriority]   = useState(goal.priority ?? "medium");
  const [saving, setSaving]       = useState(false);
  const [deleting, setDeleting]   = useState(false);

  const collapse = () => setExpanded(false);

  const saveEdits = async () => {
    setSaving(true);
    try {
      const updates: Record<string, string> = {};
      if (title !== goal.title) updates.title = title;
      if (description !== (goal.description ?? "")) updates.description = description;
      if (priority !== goal.priority) updates.priority = priority;
      if (Object.keys(updates).length > 0) {
        await updateGoal(goal.id, updates);
        onGoalsChanged();
      }
    } finally {
      setSaving(false);
      collapse();
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete goal "${goal.title}"? Linked tasks will be unlinked.`)) return;
    setDeleting(true);
    try {
      await deleteGoal(goal.id);
      onGoalsChanged();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <li className={`rounded-xl border transition-colors ${expanded ? "border-gray-300 bg-gray-50" : "border-gray-100 bg-white"}`}>
      <div className="flex items-start gap-3 p-3">
        <span className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${PRIORITY_DOT[goal.priority] ?? "bg-gray-300"}`} />

        <button
          onClick={() => expanded ? collapse() : setExpanded(true)}
          className="flex-1 min-w-0 text-left"
        >
          <p className="text-sm leading-snug text-gray-900">{goal.title}</p>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <span className="text-xs text-gray-400 capitalize">{goal.priority}</span>
            {linkedTasks.length > 0 && (
              <span className="text-xs text-blue-500">
                {linkedTasks.length} task{linkedTasks.length > 1 ? "s" : ""}
              </span>
            )}
            {goal.description && (
              <span className="text-xs text-gray-400 truncate max-w-xs">{goal.description}</span>
            )}
          </div>
        </button>

        <button
          onClick={handleDelete}
          disabled={deleting}
          className="text-gray-300 hover:text-red-400 transition-colors p-1 shrink-0"
        >
          {deleting ? "…" : "✕"}
        </button>
      </div>

      {expanded && (
        <div className="px-3 pb-4 space-y-4 border-t border-gray-100 pt-3">
          {/* Title */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500">Title</label>
            <input
              type="text"
              value={title}
              autoFocus
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveEdits()}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-black"
            />
          </div>

          {/* Description */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Optional context"
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-black"
            />
          </div>

          {/* Priority */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500">Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-black bg-white"
            >
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {/* Linked tasks */}
          {linkedTasks.length > 0 && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500">Linked tasks</label>
              <ul className="space-y-1">
                {linkedTasks.map((t) => (
                  <li key={t.id} className="text-xs text-gray-500 flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.status === "completed" ? "bg-green-400" : t.status === "overdue" ? "bg-red-400" : "bg-gray-300"}`} />
                    {t.title}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={saveEdits}
              disabled={saving}
              className="flex-1 py-2 bg-black text-white text-sm rounded-lg hover:bg-gray-800 disabled:opacity-40 transition-colors"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={collapse}
              className="px-4 py-2 text-sm text-gray-400 hover:text-gray-600 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
