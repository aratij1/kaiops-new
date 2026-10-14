import type { InvestigationFindings } from "./incidentTruth";

export function RecordedInvestigationFindings({ findings }: { findings: InvestigationFindings }) {
  if (!findings || (!findings.observations.length && !findings.limitations)) {
    return null;
  }

  return (
    <div className="ic-investigation-findings">
      {findings.observations.length ? (
        <article className="ic-context-findings">
          <h4>Recorded observations</h4>
          <ul>
            {findings.observations.map((obs, idx) => (
              <li key={idx}>{obs}</li>
            ))}
          </ul>
        </article>
      ) : null}
      {findings.limitations ? (
        <article className="ic-context-findings">
          <h4>Investigation limitations</h4>
          <p>{findings.limitations}</p>
        </article>
      ) : null}
    </div>
  );
}

export function InvestigationAlternatives({ findings }: { findings: InvestigationFindings }) {
  if (!findings || !findings.alternatives.length) {
    return null;
  }

  return (
    <article className="ic-context-findings ic-alternatives">
      <h4>Alternative hypotheses evaluated</h4>
      <ul>
        {findings.alternatives.map((alt, idx) => {
          const label = typeof alt === "string" ? alt : String(alt?.hypothesis || alt?.name || alt?.description || JSON.stringify(alt));
          return <li key={idx}>{label}</li>;
        })}
      </ul>
    </article>
  );
}
