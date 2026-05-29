"use client";
import { useEffect } from "react";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
      navigator.serviceWorker
        .register(`${base}/sw.js`, { scope: `${base}/` })
        .catch(() => {});
    }
  }, []);
  return null;
}
