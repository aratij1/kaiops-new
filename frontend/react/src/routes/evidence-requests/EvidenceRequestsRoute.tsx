import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Clock, RefreshCw, UserRound } from "lucide-react";

import { useSession } from "../../app/SessionContext";
import { formatUtcTimestamp } from "../../utils/presentation";
import { fetchEvidenceRequestQueue, type EvidenceRequest } from "./evidenceRequestsApi";
import "./EvidenceRequestsRoute.css";

const STATUS_LABEL: Record<string, string> = { pending: "Waiting for your answer", assignment_blocked: "No responder found" };

export default function EvidenceRequestsRoute() {
  const { accessToken } = useSession();
  const [responder, setResponder] = useState("");
  const [requests, setRequests] = useState<EvidenceRequest[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const controllerRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    setError("");
    try {
      const rows = await fetchEvidenceRequestQueue(accessToken, responder, controller.signal);
      if (!controller.signal.aborted) setRequests(rows);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Unable to load the evidence request queue");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }, [accessToken, responder]);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 200);
    return () => { window.clearTimeout(timer); controllerRef.current?.abort(); };
  }, [refresh]);

  const overdue = (dueAt: string | null) => Boolean(dueAt && new Date(dueAt).getTime() < Date.now());

  return (
    <section className="evidence-queue-route" aria-labelledby="evidence-queue-title">
      <article className="evidence-queue-panel">
        <header>
          <div>
            <h2 id="evidence-queue-title">Evidence requests</h2>
            <p>Investigations across every incident that are waiting on a verified human answer, in one place - so nothing sits blocked out of sight.</p>
          </div>
          <button type="button" className="button-secondary" onClick={() => void refresh()} disabled={busy}>
            <RefreshCw className={busy ? "spin" : ""} size={16} /> {busy ? "Refreshing…" : "Refresh"}
          </button>
        </header>
        <div className="evidence-queue-toolbar">
          <label>
            <span>Filter by responder</span>
            <input
              value={responder}
              onChange={(event) => setResponder(event.target.value)}
              placeholder="e.g. platform-ops@kaims.local (leave blank for everyone)"
            />
          </label>
          <span className="evidence-queue-count">{requests.length} open request{requests.length === 1 ? "" : "s"}</span>
        </div>
      </article>

      {error ? <div className="evidence-queue-error" role="alert">{error}</div> : null}

      {!busy && !requests.length && !error ? (
        <div className="evidence-queue-empty">
          <strong>Nothing waiting{responder.trim() ? ` for ${responder.trim()}` : ""}.</strong>
          <span>Every evidence gap either collected automatically or already has an answer.</span>
        </div>
      ) : null}

      <ul className="evidence-queue-list">
        {requests.map((request) => (
          <li key={request.request_id} className={`evidence-queue-card ${request.status === "assignment_blocked" ? "is-blocked" : ""}`}>
            <div className="evidence-queue-card-main">
              <header>
                <span className="evidence-queue-category">{(request.category || "evidence").replaceAll("_", " ")}</span>
                <span className={`evidence-queue-status status-${request.status}`}>
                  {request.status === "assignment_blocked" ? <AlertTriangle size={13} /> : <Clock size={13} />}
                  {STATUS_LABEL[request.status] || request.status.replaceAll("_", " ")}
                </span>
              </header>
              <p className="evidence-queue-question">{request.question || "Provide a verified observation for this incident."}</p>
              {request.reason ? <p className="evidence-queue-reason">{request.reason}</p> : null}
              <div className="evidence-queue-meta">
                <span><strong>{request.incident_title || "Incident"}</strong> {request.incident_service ? `· ${request.incident_service}` : ""}</span>
                <span><UserRound size={13} aria-hidden="true" /> {request.expected_responder || "Unassigned"}</span>
                {request.due_at ? (
                  <span className={overdue(request.due_at) ? "is-overdue" : ""}>
                    <Clock size={13} aria-hidden="true" /> Due {formatUtcTimestamp(request.due_at)}
                  </span>
                ) : null}
              </div>
              {/* This field is reused for unrelated Jira-sync errors once a request is
                  successfully assigned, so only surface it while it actually means
                  "no responder was found" - otherwise an answerable, assigned request
                  would show a confusing sync-error line instead of its real state. */}
              {request.status === "assignment_blocked" && request.assignment_failure_reason ? (
                <p className="evidence-queue-failure" role="status">{request.assignment_failure_reason.replaceAll("_", " ")}</p>
              ) : null}
            </div>
            <Link className="button-primary" to={`/incidents?incident_id=${encodeURIComponent(request.incident_id)}`}>
              Open incident
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
