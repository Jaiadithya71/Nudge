"use client";

import { Nudge, NudgeAction } from "@/types";

export default function NudgeCard({
  nudge,
  onAction,
}: {
  nudge: Nudge;
  onAction: (action: NudgeAction) => void;
}) {
  return (
    <div className="border p-4 rounded-xl shadow-sm space-y-2">
      <p className="font-medium">{nudge.message}</p>

      <div className="text-sm text-gray-500">
        {nudge.type} • {nudge.priority}
        {nudge.timing && ` • ${nudge.timing}`}
      </div>

      <div className="flex gap-4 pt-1">
        <button
          className="text-sm text-blue-500 hover:text-blue-700 transition-colors"
          onClick={() => onAction("acknowledged_nudge")}
        >
          Acknowledge
        </button>
        <button
          className="text-sm text-yellow-500 hover:text-yellow-700 transition-colors"
          onClick={() => onAction("snoozed_nudge")}
        >
          Snooze
        </button>
        <button
          className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
          onClick={() => onAction("ignored_nudge")}
        >
          Ignore
        </button>
      </div>
    </div>
  );
}
