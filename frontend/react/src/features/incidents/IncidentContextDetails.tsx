import { TechnicalDetails } from "../../components/design-system";

export function IncidentContextDetails({
  context = {},
  source = {},
  snapshot = {},
}: {
  context?: Record<string, any>;
  source?: Record<string, any>;
  snapshot?: Record<string, any>;
}) {
  const hasContext = Boolean(context && Object.keys(context).length > 0);
  const hasSource = Boolean(source && Object.keys(source).length > 0);
  const hasSnapshot = Boolean(snapshot && Object.keys(snapshot).length > 0);

  if (!hasContext && !hasSource && !hasSnapshot) {
    return null;
  }

  return (
    <section id="incident-detailed-context" className="ic-section ic-detailed-context">
      <header>
        <div>
          <span>Context Provenance</span>
          <h3>Detailed Incident Context</h3>
        </div>
      </header>
      {hasSource ? (
        <TechnicalDetails summary="Signal & Alert Source Data">
          <pre>{JSON.stringify(source, null, 2)}</pre>
        </TechnicalDetails>
      ) : null}
      {hasContext ? (
        <TechnicalDetails summary="Enriched Diagnostic Context">
          <pre>{JSON.stringify(context, null, 2)}</pre>
        </TechnicalDetails>
      ) : null}
      {hasSnapshot ? (
        <TechnicalDetails summary="Context Snapshot & Telemetry State">
          <pre>{JSON.stringify(snapshot, null, 2)}</pre>
        </TechnicalDetails>
      ) : null}
    </section>
  );
}
