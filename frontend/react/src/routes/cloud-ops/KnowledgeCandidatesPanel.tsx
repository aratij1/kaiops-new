import { useState } from "react";
import { BookOpen } from "lucide-react";

import { useSession } from "../../app/SessionContext";
import { fetchKnowledgeCandidates, submitKnowledgeDraft, type KnowledgeCandidate } from "./cloudOpsApi";

/** Lets an operator preview resolved tickets/knowledge articles pulled live from a
 * validated ITSM connection and submit chosen ones into the existing knowledge-draft
 * approval workflow (POST /rag/knowledge-drafts). Nothing here writes to the knowledge
 * base directly - every submission still needs the normal human review and approval. */
export function KnowledgeCandidatesPanel({ connectionId }: { connectionId: string }) {
  const { accessToken } = useSession();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [candidates, setCandidates] = useState<KnowledgeCandidate[]>([]);
  const [submitted, setSubmitted] = useState<Set<string>>(new Set());

  async function loadCandidates() {
    setOpen(true);
    setLoading(true);
    setError("");
    try {
      setCandidates(await fetchKnowledgeCandidates(accessToken, connectionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load knowledge base candidates");
    } finally {
      setLoading(false);
    }
  }

  async function submit(candidate: KnowledgeCandidate) {
    try {
      await submitKnowledgeDraft(accessToken, candidate);
      setSubmitted((current) => new Set(current).add(candidate.source_ref));
    } catch (err) {
      setError(err instanceof Error ? err.message : `Unable to submit ${candidate.title}`);
    }
  }

  if (!open) {
    return (
      <button type="button" className="button-secondary" onClick={() => void loadCandidates()}>
        <BookOpen size={16} /> Preview knowledge base candidates
      </button>
    );
  }

  return (
    <div className="cloud-ops-knowledge-candidates">
      <header>
        <strong>Resolved tickets available for the knowledge base</strong>
        <button type="button" className="icon-button" title="Refresh candidates" aria-label="Refresh candidates" onClick={() => void loadCandidates()} disabled={loading}>↻</button>
      </header>
      {error ? <div className="cloud-ops-error" role="alert">{error}</div> : null}
      {loading ? <p className="cloud-ops-empty">Fetching candidates…</p> : null}
      {!loading && !candidates.length && !error ? <p className="cloud-ops-empty">No resolved tickets found yet.</p> : null}
      <ul>
        {candidates.map((candidate) => (
          <li key={candidate.source_ref}>
            <div>
              <strong>{candidate.title}</strong>
              <p>{candidate.content.slice(0, 160)}{candidate.content.length > 160 ? "…" : ""}</p>
            </div>
            <button
              type="button"
              className="button-secondary"
              disabled={submitted.has(candidate.source_ref)}
              onClick={() => void submit(candidate)}
            >
              {submitted.has(candidate.source_ref) ? "Submitted for review" : "Add to knowledge base"}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
