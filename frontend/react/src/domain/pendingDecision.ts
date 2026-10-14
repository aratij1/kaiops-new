const PENDING_APPROVAL_STATES = new Set([
  "awaiting_approval",
  "pending_approval",
  "approval_required",
  "pending",
  "queued",
  "draft",
  "standby",
  "required",
]);

const RESOLVED_APPROVAL_STATES = new Set([
  "approved",
  "rejected",
  "closed",
  "resolved",
  "completed",
  "cancelled",
]);

function normalizeState(value: unknown): string {
  return String(value ?? "").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
}

export function hasPendingDecision(row: any): boolean {
  if (!row) return false;
  const approvalStatus = normalizeState(row.approval_status || row.approvalStatus);
  if (PENDING_APPROVAL_STATES.has(approvalStatus)) return true;
  const status = normalizeState(row.status);
  if (PENDING_APPROVAL_STATES.has(status)) return true;
  if ([...PENDING_APPROVAL_STATES].some((s) => status.includes(s) || approvalStatus.includes(s))) return true;
  const mode = normalizeState(row.execution_mode || row.executionMode);
  if ((mode === "human_approval" || mode === "human-approval") && !RESOLVED_APPROVAL_STATES.has(status)) {
    return true;
  }
  return false;
}
