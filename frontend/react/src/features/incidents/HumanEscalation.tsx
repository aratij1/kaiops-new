import { useState, type FormEvent } from "react";

interface Props {
  incidentId: string;
  service: string;
  severity: string;
  accessToken: string;
  onEscalated: () => void | Promise<void>;
}

export default function HumanEscalation({ incidentId, service, severity, accessToken, onEscalated }: Props) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || message || !accessToken || reason.trim().length < 10 || reason.trim().length > 4000) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api-gateway/incidents/${encodeURIComponent(incidentId)}/escalate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
        body: JSON.stringify({ comment: reason.trim(), service, severity, resource_names: service ? [service] : [] }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail;
        throw new Error(typeof detail === "string" ? detail : detail?.message || payload.message || `Escalation failed (${response.status}).`);
      }
      const assignee = payload.assignment?.assignee;
      if (payload.status !== "escalated" || !assignee) throw new Error("The server did not confirm a human assignment. Refresh the incident before trying again.");
      setMessage(`Assigned to ${assignee}. Human handoff recorded; technical recovery has not been verified.`);
      setReason("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Human escalation failed.");
      setBusy(false);
      return;
    }
    setBusy(false);
    // A refresh failure must not invite resubmission of an accepted handoff.
    try { await onEscalated(); } catch { /* The recorded success remains visible. */ }
  };
  return <section className="ic-section ic-manual-close" aria-label="Human escalation">
    <header><div><span>Human assistance</span><h3>Escalate to human agent</h3></div></header>
    <p>Assign this incident to an on-duty responder for investigation. A successful handoff administratively closes this automation incident; it does not confirm recovery. If no responder is available, the incident remains open.</p>
    <form onSubmit={(event) => void submit(event)}>
      <label htmlFor="human-escalation-reason">Reason for escalation</label>
      <textarea id="human-escalation-reason" rows={3} minLength={10} maxLength={4000} required value={reason} disabled={busy || Boolean(message)} onChange={(event) => setReason(event.target.value)} placeholder="Describe the blocker and what the human responder should investigate." />
      <p>Administrator or HITL Approver access is required. Include at least 10 characters.</p>
      <button type="submit" className="button-primary" disabled={busy || Boolean(message) || !accessToken || reason.trim().length < 10}>{busy ? "Assigning human responder?" : "Escalate to human agent"}</button>
    </form>
    {message ? <p role="status">{message}</p> : null}
    {error ? <p className="error" role="alert">{error}</p> : null}
  </section>;
}
