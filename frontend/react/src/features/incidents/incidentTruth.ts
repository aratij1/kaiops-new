export interface CausalPresentationResult {
  statement: string;
  hasCausalStatement: boolean;
  confidence: number | null;
  rawObservation: string | null;
  unsupported: boolean;
}

export interface InvestigationFindings {
  observations: string[];
  supportingSignals: string[];
  contradictions: string[];
  alternatives: any[];
  limitations: string | null;
}

export function causalPresentation(
  statementText?: string | null,
  confidenceVal?: unknown,
  hasSupportingEvidence = true
): CausalPresentationResult {
  const statement = String(statementText || "").trim();
  const numConfidence = typeof confidenceVal === "number" ? confidenceVal : Number(confidenceVal);
  const confidence = Number.isFinite(numConfidence) ? numConfidence : null;

  if (!statement) {
    return {
      statement: "",
      hasCausalStatement: false,
      confidence,
      rawObservation: null,
      unsupported: false,
    };
  }

  return {
    statement,
    hasCausalStatement: true,
    confidence,
    rawObservation: null,
    unsupported: !hasSupportingEvidence,
  };
}

export function investigationFindings(canonicalRca?: Record<string, any> | null): InvestigationFindings {
  const rca = canonicalRca || {};
  const arrayOfText = (val: unknown): string[] => {
    if (!Array.isArray(val)) return [];
    return val
      .map((item) => (typeof item === "string" ? item : String((item as any)?.title || (item as any)?.name || (item as any)?.statement || "")))
      .map((text) => text.trim())
      .filter(Boolean);
  };

  const supportingSignals = [
    ...arrayOfText(rca.supporting_signals),
    ...arrayOfText(rca.evidence_used),
    ...arrayOfText(rca.evidence),
    ...arrayOfText(rca.supporting_evidence),
  ];

  const contradictions = [
    ...arrayOfText(rca.contradictions),
    ...arrayOfText(rca.ruled_out),
    ...arrayOfText(rca.alternative_causes),
  ];

  const observations = [
    ...arrayOfText(rca.observations),
    ...arrayOfText(rca.findings),
  ];

  const alternatives = Array.isArray(rca.alternatives)
    ? rca.alternatives
    : Array.isArray(rca.alternative_hypotheses)
    ? rca.alternative_hypotheses
    : [];

  const limitations = typeof rca.limitations === "string"
    ? rca.limitations
    : typeof rca.analysis_limitations === "string"
    ? rca.analysis_limitations
    : null;

  return {
    observations,
    supportingSignals,
    contradictions,
    alternatives,
    limitations,
  };
}

export function isRcaGrounded(canonicalRca?: Record<string, any> | null): boolean {
  if (!canonicalRca) return false;
  if (canonicalRca.grounded === true) return true;
  const status = String(canonicalRca.status || canonicalRca.conclusion_status || "").trim().toLowerCase();
  return ["grounded", "confirmed", "conclusive"].includes(status);
}
