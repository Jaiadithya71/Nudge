// sw.js — Nudge Service Worker
// Handles Web Push notifications received from the backend.

// Read API URL from query param passed during SW registration, fall back to localhost
const _swParams = new URL(self.location.href).searchParams;
const API_BASE = _swParams.get("api") || "http://localhost:8000/api";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

// Push event — show a notification when the backend sends a push
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data?.json() ?? {};
  } catch {
    data = { title: "Nudge", body: event.data?.text() ?? "" };
  }

  const title   = data.title || "Nudge";
  const options = {
    body:    data.body || "",
    icon:    "/icon-192.png",
    badge:   "/icon-192.png",
    tag:     data.nudge_id || "nudge",   // replaces previous nudge with same id
    renotify: true,
    data:    { nudge_id: data.nudge_id },
    actions: [
      { action: "ack",   title: "Done" },
      { action: "snooze", title: "Later" },
    ],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click — log the action and open or focus the app
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const nudgeId = event.notification.data?.nudge_id || "unknown";
  const action = event.action; // "ack" or "snooze", empty string if body clicked

  // Map service worker actions to backend action types
  const actionMap = {
    "ack":    "acknowledged_nudge",
    "snooze": "snoozed_nudge",
  };

  const mappedAction = actionMap[action] || null;

  // Log the action to the backend if a button was pressed
  if (mappedAction) {
    const logPromise = fetch(`${API_BASE}/sw-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: mappedAction,
        metadata: {
          nudge_id: nudgeId,
          source: "web_push",
        },
      }),
    }).catch(() => {
      // Silent fail — user may be offline
    });
    event.waitUntil(logPromise);
  }

  // Always open/focus the app
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow("/");
    })
  );
});
