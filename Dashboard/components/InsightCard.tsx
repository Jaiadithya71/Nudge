import { Insight } from "@/types";

export default function InsightCard({ insight }: { insight: Insight }) {
  const signals = insight.decision_signals;
  const activeFlags = signals
    ? (Object.entries(signals) as [string, boolean][])
        .filter(([, v]) => v)
        .map(([k]) => k.replace(/_/g, " "))
    : [];

  return (
    <div className="border p-4 rounded-xl space-y-3">
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
          Summary
        </p>
        <p className="text-sm">{insight.summary}</p>
      </div>

      {insight.key_observations?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Key Observations
          </p>
          <ul className="list-disc list-inside space-y-1">
            {insight.key_observations.map((obs, i) => (
              <li key={i} className="text-sm">
                {obs}
              </li>
            ))}
          </ul>
        </div>
      )}

      {insight.behavior_flags?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {insight.behavior_flags.map((flag, i) => (
            <span
              key={i}
              className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full"
            >
              {flag}
            </span>
          ))}
        </div>
      )}

      {activeFlags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {activeFlags.map((flag, i) => (
            <span
              key={i}
              className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full"
            >
              {flag}
            </span>
          ))}
        </div>
      )}

      {insight.goal_alignment && (
        <p className="text-xs text-gray-400">
          Goal alignment:{" "}
          <span className="font-medium text-gray-600">
            {Math.round(parseFloat(insight.goal_alignment) * 100)}%
          </span>
        </p>
      )}
    </div>
  );
}
