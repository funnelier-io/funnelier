"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiGet } from "./api-client";

interface UseApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(path: string | null): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(!!path);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    apiGet<T>(path).then((res) => {
      if (cancelled) return;
      if (res.ok) {
        setData(res.data);
      } else {
        setError((res.data as Record<string, string>)?.detail || "خطا در دریافت داده");
      }
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  return { data, isLoading, error, refetch };
}

export function useDebounce(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    timerRef.current = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timerRef.current);
  }, [value, delay]);

  return debounced;
}

