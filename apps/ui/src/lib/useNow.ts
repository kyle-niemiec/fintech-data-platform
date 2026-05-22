import { useSyncExternalStore } from "react";

/**
 * Shared 1-second clock. A single interval drives every subscriber so relative
 * timestamps advance on their own, independent of data refetches (react-query
 * structural sharing skips re-renders when the polled payload is unchanged).
 */
let listeners: (() => void)[] = [];
let intervalId: ReturnType<typeof setInterval> | null = null;
let now = Date.now();

function subscribe(listener: () => void): () => void {
  listeners.push(listener);
  if (intervalId === null) {
    intervalId = setInterval(() => {
      now = Date.now();
      for (const l of listeners) l();
    }, 1000);
  }
  return () => {
    listeners = listeners.filter((l) => l !== listener);
    if (listeners.length === 0 && intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  };
}

function getSnapshot(): number {
  return now;
}

export function useNow(): number {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
