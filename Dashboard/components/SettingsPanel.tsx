"use client";

import { useState } from "react";
import { Preferences, savePreferences } from "@/lib/api";

export default function SettingsPanel({
  prefs,
  onSaved,
}: {
  prefs: Preferences;
  onSaved: (updated: Preferences) => void;
}) {
  const [form, setForm] = useState({
    morning_time:       prefs.morning_time,
    midday_time:        prefs.midday_time,
    evening_time:       prefs.evening_time,
    max_nudges_per_day: prefs.max_nudges_per_day,
    min_gap_hours:      prefs.min_gap_hours,
    strictness:         prefs.strictness,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved]   = useState(false);

  const set = (key: string, value: string | number) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const updated = await savePreferences(form);
      onSaved(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Nudge times */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Nudge Schedule
        </p>
        <div className="grid grid-cols-3 gap-3">
          {[
            { key: "morning_time", label: "Morning" },
            { key: "midday_time",  label: "Midday"  },
            { key: "evening_time", label: "Evening" },
          ].map(({ key, label }) => (
            <div key={key} className="flex flex-col gap-1">
              <label className="text-xs text-gray-400">{label}</label>
              <input
                type="time"
                value={form[key as keyof typeof form] as string}
                onChange={(e) => set(key, e.target.value)}
                className="text-sm border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-black"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Limits */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Limits
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Max nudges / day</label>
            <input
              type="number"
              min={1} max={20}
              value={form.max_nudges_per_day}
              onChange={(e) => set("max_nudges_per_day", parseInt(e.target.value) || 1)}
              className="text-sm border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-black"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Min gap between nudges (hours)</label>
            <input
              type="number"
              min={0} max={24} step={0.5}
              value={form.min_gap_hours}
              onChange={(e) => set("min_gap_hours", parseFloat(e.target.value) || 0)}
              className="text-sm border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-black"
            />
          </div>
        </div>
      </div>

      {/* Tone */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Tone
        </p>
        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-xs text-gray-400">
            <span>Supportive</span>
            <span>{Math.round(form.strictness * 100)}% strict</span>
            <span>Strict</span>
          </div>
          <input
            type="range"
            min={0} max={1} step={0.1}
            value={form.strictness}
            onChange={(e) => set("strictness", parseFloat(e.target.value))}
            className="w-full accent-black"
          />
          <p className="text-xs text-gray-400">
            {form.strictness <= 0.3
              ? "Mostly encouraging, gentle reminders"
              : form.strictness <= 0.6
              ? "Balanced — mix of supportive and direct"
              : "Direct and firm — calls out delays clearly"}
          </p>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="text-sm px-4 py-1.5 bg-black text-white rounded hover:bg-gray-800 disabled:opacity-40 transition-colors"
      >
        {saving ? "Saving…" : saved ? "Saved ✓" : "Save preferences"}
      </button>
    </div>
  );
}
