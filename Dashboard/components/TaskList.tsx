"use client";

import { useState } from "react";
import { Task, Goal } from "@/types";
import { updateTask, deleteTask } from "@/lib/api";

interface Props {
  tasks: Task[];
  goals?: Goal[];
  onTasksChanged: () => void;
  newTaskId?: string | null;
  onNewTaskConfigured?: () => void;
}

const NUDGE_PRESETS = [
  { label: "8 am",  value: "08:00" },
  { label: "12 pm", value: "12:00" },
  { label: "3 pm",  value: "15:00" },
  { label: "6 pm",  value: "18:00" },
  { label: "9 pm",  value: "21:00" },
];

const DAYS = [
  { label: "Mon", value: "mon" },
  { label: "Tue", value: "tue" },
  { label: "Wed", value: "wed" },
  { label: "Thu", value: "thu" },
  { label: "Fri", value: "fri" },
  { label: "Sat", value: "sat" },
  { label: "Sun", value: "sun" },
];

function parseTimes(raw: string | null): string[] {
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

function parseDays(raw: string | null): string[] {
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

function friendlyTime(hhmm: string): string {
  const preset = NUDGE_PRESETS.find((p) => p.value === hhmm);
  if (preset) return preset.label;
  // convert "14:30" → "2:30 pm"
  const [h, m] = hhmm.split(":").map(Number);
  const ampm = h >= 12 ? "pm" : "am";
  const hour = h % 12 || 12;
  return m === 0 ? `${hour} ${ampm}` : `${hour}:${String(m).padStart(2, "0")} ${ampm}`;
}

export default function TaskList({ tasks, goals = [], onTasksChanged, newTaskId, onNewTaskConfigured }: Props) {
  const overdue = tasks.filter((t) => t.status === "overdue");
  const pending = tasks.filter((t) => t.status === "pending");
  const done    = tasks.filter((t) => t.status === "completed");

  if (tasks.length === 0) {
    return <p className="text-sm text-gray-400">No tasks yet. Add one above.</p>;
  }

  return (
    <div className="space-y-5">
      {overdue.length > 0 && (
        <TaskGroup label="Overdue" labelClass="text-red-500" dotClass="bg-red-400"
          tasks={overdue} goals={goals} onTasksChanged={onTasksChanged}
          newTaskId={newTaskId} onNewTaskConfigured={onNewTaskConfigured} />
      )}
      {pending.length > 0 && (
        <TaskGroup label="Pending" labelClass="text-gray-400" dotClass="bg-gray-300"
          tasks={pending} goals={goals} onTasksChanged={onTasksChanged}
          newTaskId={newTaskId} onNewTaskConfigured={onNewTaskConfigured} />
      )}
      {done.length > 0 && (
        <TaskGroup label="Done" labelClass="text-green-500" dotClass="bg-green-400"
          tasks={done} goals={goals} onTasksChanged={onTasksChanged}
          newTaskId={newTaskId} onNewTaskConfigured={onNewTaskConfigured} />
      )}
    </div>
  );
}

function TaskGroup({ label, labelClass, dotClass, tasks, goals, onTasksChanged, newTaskId, onNewTaskConfigured }: {
  label: string; labelClass: string; dotClass: string;
  tasks: Task[]; goals: Goal[]; onTasksChanged: () => void;
  newTaskId?: string | null; onNewTaskConfigured?: () => void;
}) {
  return (
    <div>
      <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${labelClass}`}>
        {label} ({tasks.length})
      </p>
      <ul className="space-y-2">
        {tasks.map((t) => (
          <TaskRow
            key={t.id}
            task={t}
            goals={goals}
            dotClass={dotClass}
            onTasksChanged={onTasksChanged}
            startExpanded={t.id === newTaskId}
            onCollapsed={t.id === newTaskId ? onNewTaskConfigured : undefined}
          />
        ))}
      </ul>
    </div>
  );
}

function TaskRow({ task, goals, dotClass, onTasksChanged, startExpanded, onCollapsed }: {
  task: Task; goals: Goal[]; dotClass: string; onTasksChanged: () => void;
  startExpanded?: boolean; onCollapsed?: () => void;
}) {
  const initTimes = parseTimes(task.nudge_times).length > 0
    ? parseTimes(task.nudge_times)
    : task.nudge_time ? [task.nudge_time] : [];
  const initDays = parseDays(task.nudge_days);

  const [expanded, setExpanded]         = useState(startExpanded ?? false);
  const [nudgeMsg, setNudgeMsg]         = useState(task.nudge_message ?? "");
  const [dueDate, setDueDate]           = useState(task.due_date?.slice(0, 10) ?? "");
  const [goalId, setGoalId]             = useState(task.goal_id ?? "");
  const [selectedTimes, setSelectedTimes] = useState<string[]>(initTimes);
  const [customTime, setCustomTime]     = useState("");
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [selectedDays, setSelectedDays] = useState<string[]>(initDays);  // empty = every day
  const [nudgeEnabled, setNudgeEnabled] = useState((task.nudge_enabled ?? 1) === 1);
  const [saving, setSaving]             = useState(false);
  const [deleting, setDeleting]         = useState(false);

  const toggleTime = (value: string) => {
    setSelectedTimes((prev) =>
      prev.includes(value) ? prev.filter((t) => t !== value) : [...prev, value].sort()
    );
  };

  const addCustomTime = () => {
    if (!customTime) return;
    if (!selectedTimes.includes(customTime)) {
      setSelectedTimes((prev) => [...prev, customTime].sort());
    }
    setCustomTime("");
    setShowCustomInput(false);
  };

  const toggleDay = (value: string) => {
    setSelectedDays((prev) =>
      prev.includes(value) ? prev.filter((d) => d !== value) : [...prev, value]
    );
  };

  const allDays = selectedDays.length === 0;
  const setAllDays = () => setSelectedDays([]);

  const toggleStatus = async () => {
    const next = task.status === "completed" ? "pending" : "completed";
    try {
      await updateTask(task.id, { status: next });
      onTasksChanged();
    } catch { /* silent */ }
  };

  const collapse = () => {
    setExpanded(false);
    onCollapsed?.();
  };

  const saveEdits = async () => {
    setSaving(true);
    try {
      const updates: Record<string, string | number | null> = {};
      if (nudgeMsg !== (task.nudge_message ?? "")) updates.nudge_message = nudgeMsg;
      if (dueDate  !== (task.due_date?.slice(0, 10) ?? "")) updates.due_date = dueDate;
      if (goalId   !== (task.goal_id ?? "")) updates.goal_id = goalId || null;

      const timesJson = JSON.stringify(selectedTimes);
      if (timesJson !== (task.nudge_times ?? "[]")) updates.nudge_times = timesJson;
      // keep legacy nudge_time in sync with first entry for backward compat
      const primaryTime = selectedTimes[0] ?? "";
      if (primaryTime !== (task.nudge_time ?? "")) updates.nudge_time = primaryTime;

      const daysJson = JSON.stringify(selectedDays);
      if (daysJson !== (task.nudge_days ?? "[]")) updates.nudge_days = daysJson;

      const enabledInt = nudgeEnabled ? 1 : 0;
      if (enabledInt !== (task.nudge_enabled ?? 1)) updates.nudge_enabled = enabledInt;

      if (Object.keys(updates).length > 0) {
        await updateTask(task.id, updates);
        onTasksChanged();
      }
    } finally {
      setSaving(false);
      collapse();
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${task.title}"?`)) return;
    setDeleting(true);
    try {
      await deleteTask(task.id);
      onTasksChanged();
    } finally {
      setDeleting(false);
    }
  };

  // Summary line under the task title
  const timeSummary = initTimes.map(friendlyTime).join(", ");
  const daySummary = initDays.length === 0 ? "every day"
    : initDays.length === 7 ? "every day"
    : initDays.map((d) => DAYS.find((x) => x.value === d)?.label ?? d).join(", ");

  return (
    <li className={`rounded-xl border transition-colors ${expanded ? "border-gray-300 bg-gray-50" : "border-gray-100 bg-white"}`}>
      {/* Task row */}
      <div className="flex items-start gap-3 p-3">
        <button
          onClick={toggleStatus}
          className={`mt-0.5 w-5 h-5 rounded-full border-2 shrink-0 transition-all ${
            task.status === "completed"
              ? "bg-green-400 border-green-400"
              : "border-gray-300 hover:border-gray-500"
          }`}
          title="Toggle complete"
        />

        <button
          onClick={() => expanded ? collapse() : setExpanded(true)}
          className="flex-1 min-w-0 text-left"
        >
          <p className={`text-sm leading-snug ${task.status === "completed" ? "line-through text-gray-400" : "text-gray-900"}`}>
            {task.title}
          </p>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            {task.due_date && (
              <span className="text-xs text-gray-400">📅 {task.due_date.slice(0, 10)}</span>
            )}
            {timeSummary && (task.nudge_enabled ?? 1) === 1 && (
              <span className="text-xs text-blue-500">🔔 {timeSummary} · {daySummary}</span>
            )}
            {(task.nudge_enabled ?? 1) === 0 && (
              <span className="text-xs text-gray-300">silent</span>
            )}
            {!task.nudge_time && !task.nudge_times && !task.due_date && (
              <span className="text-xs text-gray-300">tap to configure</span>
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

      {/* Expanded editor */}
      {expanded && (
        <div className="px-3 pb-4 space-y-4 border-t border-gray-100 pt-3">

          {/* Due date */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500">Due date</label>
            <input
              type="date"
              value={dueDate}
              autoFocus
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-black"
            />
          </div>

          {/* Goal link */}
          {goals.length > 0 && (
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
          )}

          {/* Nudge times */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-500">
              Remind me at
              {selectedTimes.length > 0 && (
                <span className="ml-1 text-gray-400 font-normal">({selectedTimes.length} time{selectedTimes.length > 1 ? "s" : ""})</span>
              )}
            </label>
            <div className="flex flex-wrap gap-2">
              {NUDGE_PRESETS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => toggleTime(p.value)}
                  className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                    selectedTimes.includes(p.value)
                      ? "bg-black text-white border-black"
                      : "border-gray-200 text-gray-600 hover:border-gray-400"
                  }`}
                >
                  {p.label}
                </button>
              ))}
              <button
                onClick={() => setShowCustomInput((v) => !v)}
                className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                  showCustomInput
                    ? "bg-gray-100 border-gray-400 text-gray-700"
                    : "border-gray-200 text-gray-500 hover:border-gray-400"
                }`}
              >
                + custom
              </button>
            </div>

            {/* Custom time input */}
            {showCustomInput && (
              <div className="flex gap-2 items-center">
                <input
                  type="time"
                  value={customTime}
                  autoFocus
                  onChange={(e) => setCustomTime(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCustomTime()}
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-black"
                />
                <button
                  onClick={addCustomTime}
                  className="text-sm px-3 py-2 bg-black text-white rounded-lg"
                >
                  Add
                </button>
              </div>
            )}

            {/* Selected times as removable chips */}
            {selectedTimes.filter((t) => !NUDGE_PRESETS.find((p) => p.value === t)).length > 0 && (
              <div className="flex flex-wrap gap-1">
                {selectedTimes
                  .filter((t) => !NUDGE_PRESETS.find((p) => p.value === t))
                  .map((t) => (
                    <span key={t} className="inline-flex items-center gap-1 text-xs bg-black text-white px-2 py-1 rounded-full">
                      {friendlyTime(t)}
                      <button onClick={() => toggleTime(t)} className="hover:opacity-70">✕</button>
                    </span>
                  ))}
              </div>
            )}
          </div>

          {/* Weekday selector */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-500">On which days</label>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={setAllDays}
                className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                  allDays
                    ? "bg-black text-white border-black"
                    : "border-gray-200 text-gray-600 hover:border-gray-400"
                }`}
              >
                Every day
              </button>
              {DAYS.map((d) => (
                <button
                  key={d.value}
                  onClick={() => toggleDay(d.value)}
                  className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                    selectedDays.includes(d.value)
                      ? "bg-black text-white border-black"
                      : "border-gray-200 text-gray-600 hover:border-gray-400"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* Nudge message */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500">Notification message</label>
            <input
              type="text"
              value={nudgeMsg}
              onChange={(e) => setNudgeMsg(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveEdits()}
              placeholder="e.g. Stop avoiding this. 30 minutes. Do it now."
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-black"
            />
          </div>

          {/* Enable/disable toggle */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">
              {nudgeEnabled ? "Notifications on" : "Notifications off"}
            </span>
            <button
              onClick={() => setNudgeEnabled((v) => !v)}
              className={`w-10 h-6 rounded-full transition-colors relative shrink-0 ${
                nudgeEnabled ? "bg-black" : "bg-gray-200"
              }`}
            >
              <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                nudgeEnabled ? "translate-x-5" : "translate-x-1"
              }`} />
            </button>
          </div>

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
