"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  syncData,
  getContext,
  getInsight,
  getNudges,
  logAction,
  createTask,
  createGoal,
  getPreferences,
  isUnauthorized,
  Preferences,
} from "@/lib/api";
import { getToken, clearToken } from "@/lib/auth";

import NudgeCard from "@/components/NudgeCard";
import InsightCard from "@/components/InsightCard";
import TaskList from "@/components/TaskList";
import GoalList from "@/components/GoalList";
import CalendarView from "@/components/CalendarView";
import SettingsPanel from "@/components/SettingsPanel";
import PushSetup from "@/components/PushSetup";

import { Context, Insight, Nudge, NudgeAction } from "@/types";

export default function Dashboard() {
  const router = useRouter();

  const [context, setContext] = useState<Context | null>(null);
  const [insight, setInsight] = useState<Insight | null>(null);
  const [nudges, setNudges] = useState<Nudge[]>([]);

  const [quickAdd, setQuickAdd]       = useState("");
  const [addingTask, setAddingTask]   = useState(false);
  const [newTaskId, setNewTaskId]     = useState<string | null>(null);
  const [goalAdd, setGoalAdd]         = useState("");
  const [addingGoal, setAddingGoal]   = useState(false);
  const [prefs, setPrefs]             = useState<Preferences | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [syncing, setSyncing]         = useState(false);
  const [contextLoading, setContextLoading] = useState(true);
  const [insightLoading, setInsightLoading] = useState(true);
  const [nudgesLoading, setNudgesLoading] = useState(true);

  const [contextError, setContextError] = useState<string | null>(null);
  const [insightError, setInsightError] = useState<string | null>(null);
  const [nudgesError, setNudgesError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  const handleUnauthorized = useCallback(() => {
    clearToken();
    router.replace("/login");
  }, [router]);

  const fetchContext = useCallback(async () => {
    try {
      const data = await getContext();
      setContext(data);
      setContextError(null);
    } catch (e) {
      if (isUnauthorized(e)) { handleUnauthorized(); return; }
      setContextError("Failed to load tasks and calendar.");
    } finally {
      setContextLoading(false);
    }
  }, [handleUnauthorized]);

  const fetchInsight = useCallback(async () => {
    try {
      const data = await getInsight();
      setInsight(data);
      setInsightError(null);
    } catch (e) {
      if (isUnauthorized(e)) { handleUnauthorized(); return; }
      setInsightError("Failed to load insight.");
    } finally {
      setInsightLoading(false);
    }
  }, [handleUnauthorized]);

  const fetchNudges = useCallback(async () => {
    try {
      const data = await getNudges();
      setNudges(data);
      setNudgesError(null);
    } catch (e) {
      if (isUnauthorized(e)) { handleUnauthorized(); return; }
      setNudgesError("Failed to load nudges.");
    } finally {
      setNudgesLoading(false);
    }
  }, [handleUnauthorized]);

  // On mount: load data immediately, sync in background
  useEffect(() => {
    if (!getToken()) return;
    // Show data right away from SQLite
    fetchContext();
    fetchInsight();
    fetchNudges();
    getPreferences().then(setPrefs).catch(() => {});
    // Sync calendar/contacts in background — doesn't block the UI
    setSyncing(false);
    syncData().catch(() => {});
  }, [handleUnauthorized, fetchContext, fetchInsight, fetchNudges]);

  // nudges: refresh every 60s
  useEffect(() => {
    const id = setInterval(fetchNudges, 60_000);
    return () => clearInterval(id);
  }, [fetchNudges]);

  // context: refresh every 60s
  useEffect(() => {
    const id = setInterval(fetchContext, 60_000);
    return () => clearInterval(id);
  }, [fetchContext]);

  // insight: refresh every 5 min (rarely changes)
  useEffect(() => {
    const id = setInterval(fetchInsight, 300_000);
    return () => clearInterval(id);
  }, [fetchInsight]);

  const handleManualSync = async () => {
    setSyncing(true);
    try {
      await syncData();
      await fetchContext();
    } catch (e) {
      if (isUnauthorized(e)) { handleUnauthorized(); return; }
    } finally {
      setSyncing(false);
    }
  };

  const handleNudgeAction = async (
    action: NudgeAction,
    index: number,
    nudge: Nudge
  ) => {
    await logAction({
      action,
      metadata: {
        message: nudge.message,
        type: nudge.type,
        priority: nudge.priority,
      },
    });
    setNudges((prev) => prev.filter((_, i) => i !== index));
  };

  const handleQuickAdd = async () => {
    if (!quickAdd.trim()) return;
    setAddingTask(true);
    try {
      const task = await createTask({ title: quickAdd.trim() });
      setQuickAdd("");
      await fetchContext();
      // Auto-expand the nudge config row for the newly created task
      setNewTaskId(task.id);
    } catch (e) {
      if (isUnauthorized(e)) { handleUnauthorized(); return; }
    } finally {
      setAddingTask(false);
    }
  };

  const handleGoalAdd = async () => {
    if (!goalAdd.trim()) return;
    setAddingGoal(true);
    try {
      await createGoal({ title: goalAdd.trim() });
      setGoalAdd("");
      await fetchContext();
    } catch (e) {
      if (isUnauthorized(e)) { handleUnauthorized(); return; }
    } finally {
      setAddingGoal(false);
    }
  };

  const handleLogout = () => {
    clearToken();
    router.replace("/login");
  };

  return (
    <div className="p-6 space-y-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Nudge</h1>
        <div className="flex items-center gap-4">
          <PushSetup />
          <button
            onClick={handleManualSync}
            className="text-sm text-gray-500 hover:text-black transition-colors"
          >
            Sync
          </button>
          <button
            onClick={() => setSettingsOpen((v) => !v)}
            className="text-sm text-gray-500 hover:text-black transition-colors"
            title="Nudge settings"
          >
            ⚙
          </button>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-black transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Settings slide-in panel */}
      {settingsOpen && (
        <div className="border border-gray-200 rounded-xl p-5 bg-gray-50 space-y-1">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">Nudge Settings</h2>
            <button
              onClick={() => setSettingsOpen(false)}
              className="text-xs text-gray-400 hover:text-black"
            >
              close
            </button>
          </div>
          {prefs ? (
            <SettingsPanel prefs={prefs} onSaved={(updated) => { setPrefs(updated); setSettingsOpen(false); }} />
          ) : (
            <p className="text-sm text-gray-400">Loading…</p>
          )}
        </div>
      )}

      <Section title="Insight" loading={insightLoading} error={insightError}>
        {insight && <InsightCard insight={insight} />}
      </Section>

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
            {addingGoal ? "…" : "+ Add"}
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

      <Section title="Tasks" loading={contextLoading} error={contextError}>
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={quickAdd}
            onChange={(e) => setQuickAdd(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleQuickAdd()}
            placeholder="What do you need to do?"
            className="flex-1 text-sm border border-gray-200 rounded-xl px-4 py-2.5 focus:outline-none focus:border-black"
          />
          <button
            onClick={handleQuickAdd}
            disabled={addingTask || !quickAdd.trim()}
            className="text-sm px-5 py-2.5 bg-black text-white rounded-xl hover:bg-gray-800 disabled:opacity-40 transition-colors font-medium"
          >
            {addingTask ? "…" : "+ Add"}
          </button>
        </div>
        {context && (
          <TaskList
            tasks={context.tasks}
            goals={context.goals}
            onTasksChanged={fetchContext}
            newTaskId={newTaskId}
            onNewTaskConfigured={() => setNewTaskId(null)}
          />
        )}
      </Section>

      <Section title="Today" loading={contextLoading} error={contextError}>
        {context && <CalendarView events={context.events} />}
      </Section>

      <Section title="Nudges" loading={nudgesLoading} error={nudgesError}>
        {nudges.length === 0 ? (
          <p className="text-sm text-gray-400">No nudges right now.</p>
        ) : (
          <div className="space-y-3">
            {nudges.map((n, i) => (
              <NudgeCard
                key={i}
                nudge={n}
                onAction={(action) => handleNudgeAction(action, i, n)}
              />
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({
  title,
  loading,
  error,
  children,
}: {
  title: string;
  loading: boolean;
  error: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <h2 className="text-xl font-semibold">{title}</h2>
      {loading ? (
        <p className="text-sm text-gray-400">Loading...</p>
      ) : error ? (
        <p className="text-sm text-red-500">{error}</p>
      ) : (
        children
      )}
    </div>
  );
}
