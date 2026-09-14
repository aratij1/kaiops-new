import { OPERATIONAL_UPDATE_EVENT } from "../../services/operationalEvents";
import { useCallback, useEffect, useState } from "react";

/** Keep the visible queue current without overlapping requests or stale filter responses. */
export function useInboxFeed<T>(url: string, token: string, empty: T, errorMessage: (payload: any, fallback: string) => string) {
  const scope = `${token}\n${url}`;
  const [loadedScope, setLoadedScope] = useState("");
  const [errorScope, setErrorScope] = useState("");
  const [data, setData] = useState<T>(empty);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!token) { setData(empty); setLoading(false); setError(""); return; }
    const controller = new AbortController();
    let pending = false;
    let liveTimer: number | undefined;
    let liveDirty = false;
    let lastStarted = 0;
    const load = async (initial = false) => {
      if (pending || controller.signal.aborted) return;
      pending = true;
      lastStarted = Date.now();
      const requestController = new AbortController();
      const abort = () => requestController.abort();
      controller.signal.addEventListener("abort", abort, { once: true });
      const deadline = window.setTimeout(abort, 45_000);
      if (initial) setLoading(true);
      try {
        const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: requestController.signal });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (!controller.signal.aborted && [401, 403].includes(response.status)) { setData(empty); setLoadedScope(scope); }
          throw new Error(errorMessage(payload, `Unified inbox failed (${response.status})`));
        }
        const result = payload?.data && typeof payload.data === "object" ? payload.data : payload;
        if (!result || !Array.isArray(result.rows)) throw new Error("Unified inbox returned an invalid page. Please retry.");
        if (!controller.signal.aborted) {
          setLoadedScope(scope);
          setData({ ...empty, ...result, rows: Array.isArray(result?.rows) ? result.rows : [] });
          setError("");
        }
      } catch (failure) {
        if (!controller.signal.aborted) {
          setErrorScope(scope);
          setError(requestController.signal.aborted ? "The inbox request timed out. Please retry." : String((failure as Error).message || failure));
        }
      } finally {
        window.clearTimeout(deadline);
        controller.signal.removeEventListener("abort", abort);
        pending = false;
        if (!controller.signal.aborted) {
          setLoading(false);
          if (liveDirty) { liveDirty = false; scheduleLiveRefresh(); }
        }
      }
    };
    const refreshVisible = () => { if (document.visibilityState === "visible") void load(); };
    const scheduleLiveRefresh = () => {
      if (liveTimer !== undefined) return;
      liveTimer = window.setTimeout(() => {
        liveTimer = undefined;
        if (pending) { liveDirty = true; return; }
        refreshVisible();
      }, Math.max(250, 5_000 - (Date.now() - lastStarted)));
    };
    const onOperationalUpdate = (event: Event) => {
      if (["alert.created", "incident.status", "approval.state", "remediation.progress"].includes((event as CustomEvent).detail?.type)) scheduleLiveRefresh();
    };
    window.addEventListener(OPERATIONAL_UPDATE_EVENT, onOperationalUpdate);
    void load(true);
    const timer = window.setInterval(refreshVisible, 30_000);
    window.addEventListener("focus", refreshVisible);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      controller.abort();
      window.clearTimeout(liveTimer);
      window.removeEventListener(OPERATIONAL_UPDATE_EVENT, onOperationalUpdate);
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshVisible);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [url, token, empty, errorMessage, revision, scope]);
  return { data: loadedScope === scope && token ? data : empty, loading, error: errorScope === scope ? error : "", refresh };
}
