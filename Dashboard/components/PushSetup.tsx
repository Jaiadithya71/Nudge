"use client";

import { useEffect, useState } from "react";
import { getVapidPublicKey, savePushSubscription } from "@/lib/api";

type Status = "idle" | "requesting" | "subscribed" | "denied" | "unsupported" | "error";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export default function PushSetup() {
  const [status, setStatus] = useState<Status>("idle");

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setStatus("unsupported");
      return;
    }
    if (Notification.permission === "denied") {
      setStatus("denied");
      return;
    }
    // Check if there's actually an active push subscription registered
    navigator.serviceWorker.ready.then((reg) => {
      reg.pushManager.getSubscription().then((sub) => {
        if (sub) setStatus("subscribed");
        // else stay "idle" — show the button
      });
    }).catch(() => {});
  }, []);

  const enable = async () => {
    setStatus("requesting");
    try {
      console.log("[push] Registering service worker…");
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
      const registration = await navigator.serviceWorker.register(`/sw.js?api=${encodeURIComponent(apiUrl)}`);
      console.log("[push] SW registered, waiting for ready…");
      await navigator.serviceWorker.ready;

      // Get VAPID public key from backend
      console.log("[push] Fetching VAPID public key…");
      const publicKey = await getVapidPublicKey();
      console.log("[push] Got VAPID key:", publicKey.slice(0, 20) + "…");
      const applicationServerKey = urlBase64ToUint8Array(publicKey);

      // Unsubscribe any stale subscription first, then re-subscribe
      const existing = await registration.pushManager.getSubscription();
      if (existing) {
        console.log("[push] Unsubscribing stale subscription…");
        await existing.unsubscribe();
      }

      console.log("[push] Subscribing to push…");
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey,
      });
      console.log("[push] Subscribed! Saving to backend…", subscription.endpoint.slice(0, 60) + "…");

      // Save to backend
      await savePushSubscription(subscription.toJSON() as PushSubscriptionJSON);
      console.log("[push] Saved to backend. All done.");
      setStatus("subscribed");
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "NotAllowedError") {
        console.warn("[push] Permission denied by user");
        setStatus("denied");
      } else {
        console.error("[push] Setup failed:", e);
        setStatus("error");
      }
    }
  };

  if (status === "unsupported") return null;

  if (status === "subscribed") {
    return (
      <span className="text-xs text-green-500">🔔 notifications on</span>
    );
  }

  if (status === "denied") {
    return (
      <span className="text-xs text-gray-400">notifications blocked</span>
    );
  }

  if (status === "error") {
    return (
      <button
        onClick={enable}
        className="text-xs px-3 py-1.5 border border-red-200 text-red-400 rounded hover:border-red-400 transition-colors"
      >
        retry notifications
      </button>
    );
  }

  return (
    <button
      onClick={enable}
      disabled={status === "requesting"}
      className="text-xs px-3 py-1.5 border border-gray-200 rounded hover:border-black transition-colors disabled:opacity-40"
    >
      {status === "requesting" ? "Setting up…" : "Enable notifications"}
    </button>
  );
}
