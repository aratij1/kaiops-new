export type EvidenceRequest = {
  request_id: string;
  incident_id: string;
  requirement_id: string;
  status: string;
  expected_responder: string | null;
  assignment_source: string | null;
  assignment_failure_reason: string | null;
  due_at: string | null;
  created_at: string | null;
  category: string | null;
  question: string | null;
  reason: string | null;
  incident_title: string | null;
  incident_service: string | null;
  incident_status: string | null;
};

export async function fetchEvidenceRequestQueue(accessToken: string, responder?: string, signal?: AbortSignal) {
  const token = accessToken.trim();
  if (!token) throw new Error("Not authenticated");
  const params = new URLSearchParams();
  if (responder?.trim()) params.set("responder", responder.trim());
  const query = params.toString();
  const response = await fetch(`/api-gateway/incidents/evidence-requests${query ? `?${query}` : ""}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }
  const payload = await response.json() as { requests: EvidenceRequest[]; count: number };
  return payload.requests;
}
