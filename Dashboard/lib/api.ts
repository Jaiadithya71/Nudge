import axios from "axios";
import { getToken } from "./auth";
import { Context, Insight, Nudge, Task, Goal } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const authHeaders = () => ({
  Authorization: `Bearer ${getToken()}`,
});

export const isUnauthorized = (e: unknown): boolean =>
  axios.isAxiosError(e) && e.response?.status === 401;

export const login = async (
  userId: string,
  password: string
): Promise<string> => {
  const res = await axios.post(`${BASE_URL}/auth/login`, {
    user_id: userId,
    password,
  });
  return res.data.access_token;
};

export const syncData = async (): Promise<void> => {
  await axios.post(`${BASE_URL}/sync`, {}, { headers: authHeaders() });
};

export const getContext = async (): Promise<Context> => {
  const res = await axios.get(`${BASE_URL}/context`, {
    headers: authHeaders(),
  });
  return res.data;
};

export const getInsight = async (): Promise<Insight> => {
  const res = await axios.get(`${BASE_URL}/insight`, {
    headers: authHeaders(),
    params: { mode: "real" },
  });
  return res.data;
};

export const getNudges = async (): Promise<Nudge[]> => {
  const res = await axios.get(`${BASE_URL}/nudges`, {
    headers: authHeaders(),
    params: { mode: "real" },
  });
  return res.data.nudges ?? [];
};

export const logAction = async (payload: {
  action: string;
  metadata?: Record<string, unknown>;
}): Promise<void> => {
  await axios.post(`${BASE_URL}/log-action`, payload, {
    headers: authHeaders(),
  });
};

export const runCycle = async (
  jobType: "morning" | "midday" | "evening" | "event" = "morning",
  mode: "mock" | "real" = "mock"
): Promise<void> => {
  await axios.post(
    `${BASE_URL}/run-cycle`,
    { job_type: jobType, mode },
    { headers: authHeaders() }
  );
};

export const createTask = async (payload: {
  title: string;
  due_date?: string;
  goal_id?: string;
  nudge_message?: string;
}): Promise<Task> => {
  const res = await axios.post(`${BASE_URL}/tasks`, payload, {
    headers: authHeaders(),
  });
  return res.data;
};

export const updateTask = async (
  taskId: string,
  updates: {
    title?: string;
    status?: string;
    due_date?: string;
    goal_id?: string | null;
    nudge_message?: string;
    nudge_time?: string;
    nudge_enabled?: number;
  }
): Promise<Task> => {
  const res = await axios.patch(`${BASE_URL}/tasks/${taskId}`, updates, {
    headers: authHeaders(),
  });
  return res.data;
};

export const deleteTask = async (taskId: string): Promise<void> => {
  await axios.delete(`${BASE_URL}/tasks/${taskId}`, { headers: authHeaders() });
};

export type Preferences = {
  user_id: string;
  morning_time: string;
  midday_time: string;
  evening_time: string;
  max_nudges_per_day: number;
  min_gap_hours: number;
  strictness: number;
};

export const getPreferences = async (): Promise<Preferences> => {
  const res = await axios.get(`${BASE_URL}/preferences`, { headers: authHeaders() });
  return res.data;
};

export const savePreferences = async (updates: Partial<Omit<Preferences, "user_id">>): Promise<Preferences> => {
  const res = await axios.post(`${BASE_URL}/preferences`, updates, { headers: authHeaders() });
  return res.data;
};

export const createGoal = async (payload: {
  title: string;
  description?: string;
  priority?: string;
}): Promise<Goal> => {
  const res = await axios.post(`${BASE_URL}/goals`, payload, {
    headers: authHeaders(),
  });
  return res.data;
};

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

export const getVapidPublicKey = async (): Promise<string> => {
  const res = await axios.get(`${BASE_URL}/push/vapid-public-key`, {
    headers: authHeaders(),
  });
  return res.data.publicKey;
};

export const savePushSubscription = async (subscription: PushSubscriptionJSON): Promise<void> => {
  await axios.post(
    `${BASE_URL}/push/subscribe`,
    {
      endpoint: subscription.endpoint,
      keys: subscription.keys,
    },
    { headers: authHeaders() }
  );
};

export const removePushSubscription = async (endpoint: string): Promise<void> => {
  await axios.post(
    `${BASE_URL}/push/unsubscribe`,
    { endpoint },
    { headers: authHeaders() }
  );
};
