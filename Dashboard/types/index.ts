export type Task = {
  id: string;
  title: string;
  status: string;
  due_date: string | null;
  goal_id: string | null;
  nudge_message: string | null;
  nudge_time: string | null;       // legacy single HH:MM
  nudge_times: string | null;      // JSON array of HH:MM e.g. '["08:00","15:00"]'
  nudge_days: string | null;       // JSON array of day abbrevs e.g. '["mon","wed","fri"]'
  nudge_enabled: number | null;    // 1 = on, 0 = off
  last_modified: string | null;
  source: string | null;
  created_at: string;
};

export type Event = {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  created_at: string;
};

export type Goal = {
  id: string;
  title: string;
  description: string;
  priority: string;
  created_at: string;
};

export type Contact = {
  id: string;
  name: string;
  email: string;
  last_interaction: string | null;
  importance_score: number;
};

export type BehaviorPattern = {
  id: string;
  pattern_type: string;
  description: string;
  confidence: number;
  last_updated: string;
};

export type RecentAction = {
  id: string;
  action_type: string;
  entity_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type Context = {
  user_id: string;
  goals: Goal[];
  tasks: Task[];
  events: Event[];
  contacts: Contact[];
  behavior_patterns: BehaviorPattern[];
  recent_actions: RecentAction[];
  built_at: string;
};

export type DecisionSignals = {
  needs_activation: boolean;
  needs_correction: boolean;
  goal_at_risk: boolean;
  has_overdue_tasks: boolean;
};

export type Insight = {
  insight_id: string;
  summary: string;
  key_observations: string[];
  goal_alignment: string;
  behavior_flags: string[];
  opportunity_areas: string[];
  decision_signals: DecisionSignals;
};

export type Nudge = {
  type: string;
  message: string;
  priority: string;
  timing: string;
};

export type NudgeAction = "acknowledged_nudge" | "snoozed_nudge" | "ignored_nudge";
