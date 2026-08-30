"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, onUpdate } from "./api";

interface State<T> { data: T | null; error: string | null; loading: boolean; live: boolean }

/**
 * Fetch once, then refetch whenever the server says `.longhaul/` changed.
 *
 * The `live` flag reflects whether the change stream is actually connected,
 * rather than whether we hope it is — a page that claims to be live while the
 * orchestrator has stopped is worse than one that admits it is a snapshot.
 */
export function useData<T>(load: () => Promise<T>, deps: unknown[] = []): State<T> & {
  reload: () => void;
} {
  const [state, setState] = useState<State<T>>({
    data: null, error: null, loading: true, live: false,
  });
  const mounted = useRef(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);

  const reload = useCallback(() => {
    run()
      .then((data) => {
        if (mounted.current) setState((s) => ({ ...s, data, error: null, loading: false }));
      })
      .catch((err: unknown) => {
        if (!mounted.current) return;
        const message =
          err instanceof ApiError ? err.message : "Something went wrong loading this.";
        setState((s) => ({ ...s, error: message, loading: false, live: false }));
      });
  }, [run]);

  useEffect(() => {
    mounted.current = true;
    reload();
    const stop = onUpdate(() => {
      setState((s) => ({ ...s, live: true }));
      reload();
    });
    return () => {
      mounted.current = false;
      stop();
    };
  }, [reload]);

  return { ...state, reload };
}
