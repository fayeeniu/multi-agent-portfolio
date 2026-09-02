"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ApiError, apiGet } from "./api";

export interface Resource<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  refresh: () => Promise<void>;
  /** Replace the cached payload with one returned by a mutation. */
  set: (next: T) => void;
}

/**
 * Read one API resource. Polling is opt-in and exists only to follow work that
 * is genuinely executing; an idle screen makes no repeat requests.
 */
export function useResource<T>(path: string | null, pollMs = 0): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Initial read. State is written from the promise callback, never from the
  // effect body, so the first paint is not a cascading render.
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    apiGet<T>(path).then(
      (next) => {
        if (!cancelled) {
          setData(next);
          setError(null);
        }
      },
      (caught: unknown) => {
        if (!cancelled) setError(caught as ApiError);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [path]);

  /** Re-read quietly: a failed poll must not blank a screen already showing state. */
  const refresh = useCallback(async () => {
    if (!path) return;
    try {
      const next = await apiGet<T>(path);
      if (mounted.current) {
        setData(next);
        setError(null);
      }
    } catch {
      // A quiet refresh keeps the last known good state on screen.
    }
  }, [path]);

  useEffect(() => {
    if (!pollMs || !path) return;
    const timer = window.setInterval(() => void refresh(), pollMs);
    return () => window.clearInterval(timer);
  }, [refresh, pollMs, path]);

  return { data, error, loading: data === null && error === null, refresh, set: setData };
}

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeToMotionPreference(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** Honour the operating-system reduced-motion preference at runtime. */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeToMotionPreference,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );
}

/**
 * Milliseconds elapsed since `since`, ticking only while `active`. The clock is
 * read inside the interval callback so render stays pure.
 */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · Research control room`;
    return () => {
      document.title = "Research control room";
    };
  }, [title]);
}

export function useElapsed(active: boolean, since: number | null): number {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    if (!active || since === null) return;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [active, since]);
  if (!active || since === null || now === null) return 0;
  return Math.max(0, now - since);
}
