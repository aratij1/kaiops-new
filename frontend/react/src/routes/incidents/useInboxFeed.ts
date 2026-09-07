import { useCallback, useEffect, useState } from "react";

/** Keep the visible queue current without overlapping requests or stale filter responses. */
export function useInboxFeed<T>(url: string, token: string, empty: T, errorMessage: (payload: any, fallback: string) => string) {
  const [data, setData] = useState<T>(empty);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!token) { setData(empty); setLoading(false); setError(""); return; }
    const controller = new AbortController();
    let pending = false;
    const load = async (initial = false) => {
      if (pending || controller.signal.aborted) return;
      pending = true;
      if (initial) setLoading(true);
      try {
        const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(errorMessage(payload, `Unified inbox failed (${response.status})`));
        const result = payload?.data && typeof payload.data === "object" ? payload.data : payload;
        if (!controller.signal.aborted) {
          setData({ ...empty, ...result, rows: Array.isArray(result?.rows) ? result.rows : [] });
          setError("");
        }
      } catch (failure) {
        if (!controller.signal.aborted) setError(String((failure as Error).message || failure));
      } finally {
        pending = false;
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    const refreshVisible = () => { if (document.visibilityState === "visible") void load(); };
    void load(true);
    const timer = window.setInterval(refreshVisible, 30_000);
    window.addEventListener("focus", refreshVisible);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshVisible);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [url, token, empty, errorMessage, revision]);
  return { data, loading, error, refresh };
}
