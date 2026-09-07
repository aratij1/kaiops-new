export function IncidentStatusExplanation({ blocker, reason }: { blocker: string; reason: string }) {
  if (blocker) return <details className="incident-blocker-details"><summary>Review resolution blockers</summary><p>{blocker}</p></details>;
  return <small className="incident-status-note" title={reason}>{reason}</small>;
}
